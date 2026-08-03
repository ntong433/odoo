#!/bin/sh
set -eu

runtime_config="${ODOO_RUNTIME_CONFIG:-/tmp/lhi-odoo.conf}"
odoo_bin="${ODOO_BIN_PATH:-/opt/odoo/odoo-bin}"
server_start_marker="${LHI_SERVER_START_MARKER:-/tmp/lhi-odoo-normal-server-started}"

# A container restart reuses its writable layer.  Remove a stale marker before
# any configuration, migration, or registry work so the health check cannot
# probe a server that has not reached the final exec in this invocation.
rm -f "$server_start_marker"

# The immutable staging image copies the repository's `odoo/` contents to
# /opt/odoo, while the development Compose file bind-mounts them one directory
# lower. Resolve both layouts explicitly and fail closed on an invalid image.
if [ ! -f "$odoo_bin" ] && [ -f /opt/odoo/odoo/odoo-bin ]; then
    odoo_bin=/opt/odoo/odoo/odoo-bin
fi
if [ ! -f "$odoo_bin" ]; then
    echo "Odoo startup failed: odoo-bin was not found in the deployed image." >&2
    exit 1
fi

python3 - "$runtime_config" <<'PY'
import configparser
import os
import re
import sys


runtime_config = sys.argv[1]
required = (
    "ODOO_MASTER_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)
missing = [name for name in required if not os.environ.get(name)]
if missing:
    print(
        "Odoo startup failed: required protected variables are missing: "
        + ", ".join(missing),
        file=sys.stderr,
    )
    raise SystemExit(1)

single_line_names = (
    *required,
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "ODOO_WORKERS",
    "ODOO_MAX_CRON_THREADS",
)
for name in single_line_names:
    value = os.environ.get(name, "")
    if "\n" in value or "\r" in value:
        print(
            f"Odoo startup failed: {name} must be a single-line value.",
            file=sys.stderr,
        )
        raise SystemExit(1)

database = os.environ["POSTGRES_DB"]
workers = int(os.environ.get("ODOO_WORKERS", "0"))
max_cron_threads = int(os.environ.get("ODOO_MAX_CRON_THREADS", "2"))
if workers < 0 or max_cron_threads < 0:
    print(
        "Odoo startup failed: worker counts cannot be negative.",
        file=sys.stderr,
    )
    raise SystemExit(1)

config = configparser.ConfigParser(interpolation=None)
config.optionxform = str
config["options"] = {
    "admin_passwd": os.environ["ODOO_MASTER_PASSWORD"],
    "db_host": os.environ.get("POSTGRES_HOST", "db"),
    "db_port": os.environ.get("POSTGRES_PORT", "5432"),
    "db_user": os.environ["POSTGRES_USER"],
    "db_password": os.environ["POSTGRES_PASSWORD"],
    "db_name": database,
    "dbfilter": f"^{re.escape(database)}$",
    "list_db": "False",
    "proxy_mode": "True",
    "addons_path": "/opt/odoo/odoo/addons,/opt/odoo/custom-addons",
    "data_dir": "/var/lib/odoo",
    "log_level": os.environ.get("ODOO_LOG_LEVEL", "info"),
    "log_handler": ":INFO,odoo.addons.lhi_audit:DEBUG",
    "workers": str(workers),
    "max_cron_threads": str(max_cron_threads),
    "limit_memory_soft": "1610612736" if workers > 0 else "0",
    "limit_memory_hard": "2147483648" if workers > 0 else "0",
    "limit_time_cpu": os.environ.get("ODOO_LIMIT_TIME_CPU", "600"),
    "limit_time_real": os.environ.get("ODOO_LIMIT_TIME_REAL", "1200"),
}
old_umask = os.umask(0o077)
try:
    with open(runtime_config, "w", encoding="utf-8") as stream:
        config.write(stream)
finally:
    os.umask(old_umask)
os.chmod(runtime_config, 0o600)
PY

echo "Startup phase: protected environment validation"
/opt/odoo/scripts/validate_microsoft_env.sh --configuration-only

echo "Startup phase: PostgreSQL readiness"
readiness_attempt=0
until PGPASSWORD="$POSTGRES_PASSWORD" pg_isready \
    --host="${POSTGRES_HOST:-db}" \
    --port="${POSTGRES_PORT:-5432}" \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" >/dev/null 2>&1
do
    readiness_attempt=$((readiness_attempt + 1))
    if [ "$readiness_attempt" -ge "${LHI_POSTGRES_READY_ATTEMPTS:-30}" ]; then
        echo "Odoo startup failed: PostgreSQL did not become ready within the bounded startup window." >&2
        exit 1
    fi
    sleep "${LHI_POSTGRES_READY_INTERVAL_SECONDS:-2}"
done
echo "PostgreSQL readiness: success"

database_initialized="$(
    PGPASSWORD="$POSTGRES_PASSWORD" \
        psql \
        --host="${POSTGRES_HOST:-db}" \
        --port="${POSTGRES_PORT:-5432}" \
        --username="$POSTGRES_USER" \
        --dbname="$POSTGRES_DB" \
        --no-password \
        --tuples-only \
        --no-align \
        --command="SELECT to_regclass('public.ir_module_module') IS NOT NULL"
)"

case "$database_initialized" in
    t)
        ;;
    f)
        case "${ODOO_INITIALIZE_DATABASE_IF_EMPTY:-true}" in
            true|TRUE|1|yes|YES)
                echo "Odoo database schema is absent; initializing the base module."
                set +e
                python3 "$odoo_bin" server \
                    -c "$runtime_config" \
                    --init=base \
                    --without-demo \
                    --stop-after-init \
                    --no-http \
                    --log-level="${ODOO_LOG_LEVEL:-info}"
                base_init_status=$?
                set -e
                if [ "$base_init_status" -ne 0 ]; then
                    echo "Odoo startup failed: base database initialization returned exit code $base_init_status" >&2
                    exit "$base_init_status"
                fi
                ;;
            *)
                echo \
                    "Odoo startup failed: the configured database is empty and automatic initialization is disabled." \
                    >&2
                exit 1
                ;;
        esac
        ;;
    *)
        echo \
            "Odoo startup failed: unable to determine whether the configured database is initialized." \
            >&2
        exit 1
        ;;
esac

validate_module_list() {
    module_variable="$1"
    module_list="$2"
    case "$module_list" in
        *[!A-Za-z0-9_,]*|,*|*,|*,,*)
            echo "Odoo startup failed: $module_variable must be a comma-separated list of module technical names." >&2
            exit 1
            ;;
    esac
}

run_odoo_module_phase() {
    phase_name="$1"
    phase_modules="$2"
    shift 2

    echo "=========================================================="
    echo "Startup phase: $phase_name"
    echo "Module list: $phase_modules"
    echo "UTC timestamp: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo "Logs: stdout/stderr"
    echo "=========================================================="

    set +e
    "$@"
    phase_status=$?
    set -e
    if [ "$phase_status" -ne 0 ]; then
        echo "Odoo startup failed during $phase_name; exit code $phase_status; modules: $phase_modules" >&2
        exit "$phase_status"
    fi
}

echo "Startup phase: Odoo module-list refresh"
set +e
python3 "$odoo_bin" shell \
    -c "$runtime_config" \
    --log-level="${ODOO_LOG_LEVEL:-info}" <<'PY'
updated, added = env["ir.module.module"].update_list()
env.cr.commit()
print(f"Odoo module-list refresh complete: updated={updated}, added={added}")
PY
module_refresh_status=$?
set -e
if [ "$module_refresh_status" -ne 0 ]; then
    echo "Odoo startup failed during module-list refresh; exit code $module_refresh_status" >&2
    exit "$module_refresh_status"
fi

bootstrap_modules="${LHI_BOOTSTRAP_MODULES:-lhi_base,lhi_security,lhi_audit,lhi_approval_matrix,lhi_feature_control,lhi_web_shell,lhi_dashboard}"
if [ -n "$bootstrap_modules" ]; then
    validate_module_list "LHI_BOOTSTRAP_MODULES" "$bootstrap_modules"

    bootstrap_required="$(
        PGPASSWORD="$POSTGRES_PASSWORD" \
            psql \
            --host="${POSTGRES_HOST:-db}" \
            --port="${POSTGRES_PORT:-5432}" \
            --username="$POSTGRES_USER" \
            --dbname="$POSTGRES_DB" \
            --no-password \
            --tuples-only \
            --no-align \
            --command="
                SELECT EXISTS (
                    SELECT 1
                    FROM unnest(string_to_array('$bootstrap_modules', ',')) AS requested(name)
                    LEFT JOIN ir_module_module AS module
                        ON module.name = requested.name
                    WHERE module.state IS DISTINCT FROM 'installed'
                )
            "
    )"

    case "$bootstrap_required" in
        t)
            run_odoo_module_phase \
                "approved foundation-module installation" \
                "$bootstrap_modules" \
                python3 "$odoo_bin" server \
                -c "$runtime_config" \
                --init="$bootstrap_modules" \
                --without-demo \
                --stop-after-init \
                --no-http \
                --log-level="${ODOO_LOG_LEVEL:-info}"
            ;;
        f)
            echo "Approved LHI foundation modules are already installed."
            ;;
        *)
            echo \
                "Odoo startup failed: unable to determine the LHI foundation module state." \
                >&2
            exit 1
            ;;
    esac
fi

required_modules="${LHI_REQUIRED_MODULES:-lhi_memo_integration}"
if [ -n "$required_modules" ]; then
    validate_module_list "LHI_REQUIRED_MODULES" "$required_modules"

    uninstalled_required="$(
        PGPASSWORD="$POSTGRES_PASSWORD" \
            psql \
            --host="${POSTGRES_HOST:-db}" \
            --port="${POSTGRES_PORT:-5432}" \
            --username="$POSTGRES_USER" \
            --dbname="$POSTGRES_DB" \
            --no-password \
            --tuples-only \
            --no-align \
            --command="
                SELECT COALESCE(string_agg(requested.name, ','), '')
                FROM unnest(string_to_array('$required_modules', ',')) AS requested(name)
                LEFT JOIN ir_module_module AS module
                    ON module.name = requested.name
                WHERE module.state IS NULL OR module.state IS DISTINCT FROM 'installed';
            "
    )"

    if [ -n "$uninstalled_required" ]; then
        run_odoo_module_phase \
            "required-module installation" \
            "$uninstalled_required" \
            python3 "$odoo_bin" server \
            -c "$runtime_config" \
            -i "$uninstalled_required" \
            --without-demo \
            --stop-after-init \
            --no-http \
            --log-level="${ODOO_LOG_LEVEL:-info}"
        echo "Mandatory module installation completed successfully."
    else
        echo "All mandatory LHI addons are already installed."
    fi
fi

auto_upgrade_modules="${LHI_AUTO_UPGRADE_MODULES:-lhi_base,lhi_security,lhi_approval_matrix,lhi_dashboard,lhi_asset_management,lhi_hub_management,lhi_purchase_request,lhi_memo_management,lhi_entra_identity_sync,lhi_signature_bridge,lhi_memo_integration,lhi_accounting_base}"

if [ -n "$auto_upgrade_modules" ]; then
    validate_module_list "LHI_AUTO_UPGRADE_MODULES" "$auto_upgrade_modules"
    installed_upgrade_modules="$(
        PGPASSWORD="$POSTGRES_PASSWORD" \
            psql \
            --host="${POSTGRES_HOST:-db}" \
            --port="${POSTGRES_PORT:-5432}" \
            --username="$POSTGRES_USER" \
            --dbname="$POSTGRES_DB" \
            --no-password \
            --tuples-only \
            --no-align \
            --command="
                SELECT COALESCE(string_agg(requested.name, ',' ORDER BY requested.ordinality), '')
                FROM unnest(string_to_array('$auto_upgrade_modules', ',')) WITH ORDINALITY AS requested(name, ordinality)
                JOIN ir_module_module AS module
                    ON module.name = requested.name
                   AND module.state = 'installed';
            "
    )"

    if [ -n "$installed_upgrade_modules" ]; then
        echo "Approved upgrade request: $auto_upgrade_modules"
        run_odoo_module_phase \
            "approved installed-module upgrade" \
            "$installed_upgrade_modules" \
            python3 "$odoo_bin" server \
            -c "$runtime_config" \
            -u "$installed_upgrade_modules" \
            --stop-after-init \
            --no-http \
            --log-level="${ODOO_LOG_LEVEL:-info}"
        echo "Deployment schema and view upgrade completed successfully."
    else
        echo "No approved upgrade modules are currently installed; upgrade phase skipped."
    fi
fi

echo "Startup phase: registry and required-field validation"
registry_required_modules="$bootstrap_modules"
if [ -n "$required_modules" ]; then
    if [ -n "$registry_required_modules" ]; then
        registry_required_modules="$registry_required_modules,$required_modules"
    else
        registry_required_modules="$required_modules"
    fi
fi

set +e
LHI_REGISTRY_REQUIRED_MODULES="$registry_required_modules" \
python3 "$odoo_bin" shell \
    -c "$runtime_config" \
    --log-level="${ODOO_LOG_LEVEL:-info}" <<'PY'
import os

required_modules = {
    name
    for name in os.environ.get("LHI_REGISTRY_REQUIRED_MODULES", "").split(",")
    if name
}
module_records = env["ir.module.module"].search([("name", "in", sorted(required_modules))])
states = {module.name: module.state for module in module_records}
missing_modules = sorted(
    module for module in required_modules if states.get(module) != "installed"
)
if missing_modules:
    raise RuntimeError(
        "Required modules are not installed: " + ", ".join(missing_modules)
    )

if "lhi_memo_integration" in required_modules:
    model_name = "lhi.memo.integration.operation"
    if model_name not in env:
        raise RuntimeError(f"Required registry model is missing: {model_name}")
    required_fields = {
        "memo_id",
        "company_id",
        "correlation_id",
        "operation_type",
        "idempotency_key",
        "state",
        "current_step",
        "requested_by_id",
        "started_at",
        "completed_at",
        "retry_count",
        "failure_code",
        "safe_failure_message",
        "technical_failure_reference",
        "outcome_uncertain",
        "requires_reconciliation",
    }
    missing_fields = sorted(required_fields - set(env[model_name]._fields))
    if missing_fields:
        raise RuntimeError(
            f"Required fields are missing from {model_name}: "
            + ", ".join(missing_fields)
        )

print("Registry validation complete: required modules, model, and fields are present")
PY
registry_validation_status=$?
set -e
if [ "$registry_validation_status" -ne 0 ]; then
    echo "Odoo startup failed during registry validation; exit code $registry_validation_status" >&2
    exit "$registry_validation_status"
fi

echo "Startup phase: normal Odoo server"
touch "$server_start_marker"
exec python3 "$odoo_bin" server -c "$runtime_config"
