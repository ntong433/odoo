#!/bin/sh
set -eu

runtime_config="${ODOO_RUNTIME_CONFIG:-/tmp/lhi-odoo.conf}"
odoo_bin="${ODOO_BIN_PATH:-/opt/odoo/odoo-bin}"

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
if os.environ.get("ODOO_LOGFILE"):
    config["options"]["logfile"] = os.environ["ODOO_LOGFILE"]


old_umask = os.umask(0o077)
try:
    with open(runtime_config, "w", encoding="utf-8") as stream:
        config.write(stream)
finally:
    os.umask(old_umask)
os.chmod(runtime_config, 0o600)
PY

/opt/odoo/scripts/validate_microsoft_env.sh --configuration-only

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
                    --without-demo=all \
                    --stop-after-init \
                    --no-http \
                    --logfile=/dev/stdout \
                    --log-level="${ODOO_LOG_LEVEL:-info}"
                base_init_status=$?
                set -e
                if [ "$base_init_status" -ne 0 ]; then
                    echo "Odoo startup failed: base database initialization returned exit code $base_init_status" >&2
                    echo "Waiting ${LHI_UPGRADE_FAILURE_DELAY_SECONDS:-10} seconds to ensure logs are captured..." >&2
                    sleep "${LHI_UPGRADE_FAILURE_DELAY_SECONDS:-10}"
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

bootstrap_modules="${LHI_BOOTSTRAP_MODULES:-lhi_base,lhi_security,lhi_audit,lhi_approval_matrix,lhi_feature_control,lhi_web_shell,lhi_dashboard}"
if [ -n "$bootstrap_modules" ]; then
    case "$bootstrap_modules" in
        *[!A-Za-z0-9_,]*|,*|*,|*,,*)
            echo \
                "Odoo startup failed: LHI_BOOTSTRAP_MODULES must be a comma-separated list of module technical names." \
                >&2
            exit 1
            ;;
    esac

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
            echo "Installing the approved LHI foundation module set."
            set +e
            python3 "$odoo_bin" server \
                -c "$runtime_config" \
                --init="$bootstrap_modules" \
                --without-demo=all \
                --stop-after-init \
                --no-http \
                --logfile=/dev/stdout \
                --log-level="${ODOO_LOG_LEVEL:-info}"
            bootstrap_status=$?
            set -e
            if [ "$bootstrap_status" -ne 0 ]; then
                echo "Odoo startup failed: LHI foundation module initialization returned exit code $bootstrap_status for modules: $bootstrap_modules" >&2
                echo "Waiting ${LHI_UPGRADE_FAILURE_DELAY_SECONDS:-10} seconds to ensure logs are captured..." >&2
                sleep "${LHI_UPGRADE_FAILURE_DELAY_SECONDS:-10}"
                exit "$bootstrap_status"
            fi
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
    case "$required_modules" in
        *[!A-Za-z0-9_,]*|,*|*,|*,,*)
            echo "Odoo startup failed: LHI_REQUIRED_MODULES must be a comma-separated list of module technical names." >&2
            exit 1
            ;;
    esac

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
        echo "=========================================================="
        echo "Installing Uninstalled Mandatory LHI Addons: $uninstalled_required"
        echo "Container Hostname: $(hostname)"
        echo "UTC Timestamp: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
        echo "=========================================================="

        set +e
        python3 "$odoo_bin" server \
            -c "$runtime_config" \
            -i "$uninstalled_required" \
            --without-demo=all \
            --stop-after-init \
            --no-http \
            --logfile=/dev/stdout \
            --log-level="${ODOO_LOG_LEVEL:-info}"
        install_status=$?
        set -e

        if [ "$install_status" -ne 0 ]; then
            echo "Odoo deployment startup failed: installation of required modules returned exit code $install_status for modules: $uninstalled_required" >&2
            echo "Waiting ${LHI_UPGRADE_FAILURE_DELAY_SECONDS:-10} seconds to ensure logs are captured..." >&2
            sleep "${LHI_UPGRADE_FAILURE_DELAY_SECONDS:-10}"
            exit "$install_status"
        fi
        echo "Mandatory module installation completed successfully."
    else
        echo "All mandatory LHI addons are already installed."
    fi
fi

auto_upgrade_modules="${LHI_AUTO_UPGRADE_MODULES:-lhi_security,lhi_dashboard,lhi_asset_management,lhi_hub_management,lhi_memo_management,lhi_entra_identity_sync,lhi_signature_bridge,lhi_memo_integration,lhi_accounting_base}"

if [ -n "$auto_upgrade_modules" ]; then
    echo "=========================================================="
    echo "Starting LHI Odoo Deployment Module Upgrade"
    echo "Container Hostname: $(hostname)"
    echo "UTC Timestamp: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo "Module List: $auto_upgrade_modules"
    echo "=========================================================="

    set +e
    python3 "$odoo_bin" server \
        -c "$runtime_config" \
        -u "$auto_upgrade_modules" \
        --stop-after-init \
        --no-http \
        --logfile=/dev/stdout \
        --log-level="${ODOO_LOG_LEVEL:-info}"
    upgrade_status=$?
    set -e

    if [ "$upgrade_status" -ne 0 ]; then
        echo "Odoo deployment startup failed: module upgrade returned exit code $upgrade_status for modules: $auto_upgrade_modules" >&2
        echo "Waiting ${LHI_UPGRADE_FAILURE_DELAY_SECONDS:-10} seconds to ensure logs are captured..." >&2
        sleep "${LHI_UPGRADE_FAILURE_DELAY_SECONDS:-10}"
        exit "$upgrade_status"
    fi

    echo "Deployment schema and view upgrade completed successfully."
fi

exec python3 "$odoo_bin" server -c "$runtime_config"
