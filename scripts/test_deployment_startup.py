#!/usr/bin/env python3
"""Regression harness for deterministic Odoo deployment startup."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
START_SCRIPT = REPO_ROOT / "scripts" / "start_odoo.sh"


def test_shell_syntax():
    result = subprocess.run(
        ["sh", "-n", str(START_SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    print("PASS: POSIX shell syntax validation")


def test_script_structure():
    content = START_SCRIPT.read_text(encoding="utf-8")

    assert content.count('-u "$installed_upgrade_modules"') == 1
    ordered_markers = (
        "Startup phase: Odoo module-list refresh",
        '"approved foundation-module installation"',
        '"required-module installation"',
        '"approved installed-module upgrade"',
        "Startup phase: registry and required-field validation",
        "Startup phase: normal Odoo server",
    )
    positions = [content.index(marker) for marker in ordered_markers]
    assert positions == sorted(positions), "Startup phases are not ordered"

    assert "phase_status=$?" in content
    assert 'exit "$phase_status"' in content
    assert "LHI_UPGRADE_FAILURE_DELAY_SECONDS" not in content
    assert "Waiting " not in content
    assert "|| true" not in content
    assert 'touch "$server_start_marker"' in content
    assert 'exec python3 "$odoo_bin" server -c "$runtime_config"' in content
    print("PASS: Deterministic phase ordering and failure semantics")


def _write_mock_environment(temp_dir):
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir()

    mock_psql = bin_dir / "psql"
    mock_psql.write_text(
        """#!/bin/sh
case "$*" in
    *"string_agg(requested.name"*) echo 'lhi_test_upgrade' ;;
    *) echo 't' ;;
esac
""",
        encoding="utf-8",
    )
    mock_psql.chmod(0o755)

    mock_pg_isready = bin_dir / "pg_isready"
    mock_pg_isready.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    mock_pg_isready.chmod(0o755)

    mock_validate = temp_dir / "validate_microsoft_env.sh"
    mock_validate.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    mock_validate.chmod(0o755)

    mock_odoo_bin = bin_dir / "odoo-bin"
    mock_odoo_bin.write_text(
        """#!/usr/bin/env python3
import os
import sys

args_str = " ".join(sys.argv)
with open(os.environ["TEST_INVOCATION_LOG"], "a", encoding="utf-8") as stream:
    stream.write(args_str + "\\n")

if " shell " in f" {args_str} ":
    print("MOCK_ODOO_BIN: Registry shell phase complete.")
    raise SystemExit(0)

if "-u" in args_str:
    if os.environ.get("TEST_FAIL_MODE") == "upgrade":
        print(
            "CRITICAL_ERROR: Failed to load view lhi_asset_management.lhi_asset_view",
            file=sys.stderr,
        )
        raise SystemExit(42)
    print("MOCK_ODOO_BIN: Upgrading modules successfully...")
    raise SystemExit(0)

if "--stop-after-init" in args_str:
    print("MOCK_ODOO_BIN: Module installation phase complete.")
    raise SystemExit(0)

print("MOCK_ODOO_BIN: Web server running...")
""",
        encoding="utf-8",
    )
    mock_odoo_bin.chmod(0o755)

    run_script = temp_dir / "start_odoo.sh"
    run_script.write_text(
        START_SCRIPT.read_text(encoding="utf-8").replace(
            "/opt/odoo/scripts/validate_microsoft_env.sh", str(mock_validate)
        ),
        encoding="utf-8",
    )
    run_script.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{bin_dir}:{environment.get('PATH', '')}",
            "ODOO_MASTER_PASSWORD": "test_master_pwd",
            "POSTGRES_DB": "lhi_test_db",
            "POSTGRES_USER": "odoo",
            "POSTGRES_PASSWORD": "test_database_password",
            "ODOO_BIN_PATH": str(mock_odoo_bin),
            "ODOO_RUNTIME_CONFIG": str(temp_dir / "lhi-odoo.conf"),
            "LHI_BOOTSTRAP_MODULES": "",
            "LHI_REQUIRED_MODULES": "",
            "LHI_AUTO_UPGRADE_MODULES": "lhi_test_upgrade",
            "LHI_SERVER_START_MARKER": str(temp_dir / "normal-server-started"),
            "TEST_INVOCATION_LOG": str(temp_dir / "odoo-invocations.log"),
        }
    )
    return run_script, environment


def test_execution_flows():
    temp_dir = Path(tempfile.mkdtemp(prefix="lhi_start_test_"))
    try:
        run_script, environment = _write_mock_environment(temp_dir)

        success = subprocess.run(
            [str(run_script)], env=environment, capture_output=True, text=True
        )
        assert success.returncode == 0, success.stderr
        assert "Startup phase: Odoo module-list refresh" in success.stdout
        assert "Startup phase: approved installed-module upgrade" in success.stdout
        assert "MOCK_ODOO_BIN: Web server running..." in success.stdout
        assert Path(environment["LHI_SERVER_START_MARKER"]).exists()
        print("PASS: Successful startup reaches the normal server exactly once")

        Path(environment["TEST_INVOCATION_LOG"]).write_text("", encoding="utf-8")
        failed_environment = environment.copy()
        failed_environment["TEST_FAIL_MODE"] = "upgrade"
        failure = subprocess.run(
            [str(run_script)],
            env=failed_environment,
            capture_output=True,
            text=True,
        )
        assert failure.returncode == 42
        assert "CRITICAL_ERROR: Failed to load view" in failure.stderr
        assert "exit code 42" in failure.stderr + failure.stdout
        assert "Waiting " not in failure.stderr + failure.stdout
        assert "MOCK_ODOO_BIN: Web server running..." not in failure.stdout
        assert not Path(environment["LHI_SERVER_START_MARKER"]).exists()
        invocations = Path(environment["TEST_INVOCATION_LOG"]).read_text(
            encoding="utf-8"
        ).splitlines()
        assert sum(" -u " in f" {line} " for line in invocations) == 1
        print("PASS: Failed upgrade exits once with its exact status and no server start")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_healthcheck_configuration():
    for compose_name in ("docker-compose.yml", "docker-compose.staging.yml"):
        text = (REPO_ROOT / compose_name).read_text(encoding="utf-8")
        db_section = text.split("\n  db:", 1)[1].split("\n  odoo:", 1)[0]
        odoo_section = text.split("\n  odoo:", 1)[1]
        healthcheck = odoo_section.split("healthcheck:", 1)[1].split(
            "\nvolumes:", 1
        )[0]
        assert "restart: always" in db_section
        assert 'restart: "no"' in odoo_section.split("healthcheck:", 1)[0]
        assert "/web/health" in healthcheck
        assert "lhi-odoo-normal-server-started" in healthcheck
        assert "start_odoo.sh" not in healthcheck
        assert "-u" not in healthcheck
    dockerfile = (REPO_ROOT / "Dockerfile.staging").read_text(encoding="utf-8")
    assert "lhi-odoo-normal-server-started" in dockerfile
    print("PASS: Restart and healthcheck configuration")


def test_lhi_base_clean_install_xml_order():
    menus = (
        REPO_ROOT / "custom-addons" / "lhi_base" / "views" / "menus.xml"
    ).read_text(encoding="utf-8")
    master_views = (
        REPO_ROOT
        / "custom-addons"
        / "lhi_base"
        / "views"
        / "lhi_master_data_views.xml"
    ).read_text(encoding="utf-8")
    declaration = '<record id="action_lhi_project" model="ir.actions.act_window">'
    first_reference = 'action="action_lhi_project"'
    assert declaration in menus
    assert menus.index(declaration) < menus.index(first_reference)
    assert '<field name="search_view_id" ref="view_lhi_project_search"/>' in master_views
    print("PASS: lhi_base action resolves before clean-install menu references")


def main():
    test_shell_syntax()
    test_script_structure()
    test_execution_flows()
    test_healthcheck_configuration()
    test_lhi_base_clean_install_xml_order()
    print("\nALL DEPLOYMENT STARTUP TESTS PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
