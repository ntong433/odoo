#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deployment Startup & Log Redirection Test Harness.

Validates:
1. POSIX shell syntax validity (`sh -n scripts/start_odoo.sh`).
2. Single upgrade command invocation in `start_odoo.sh`.
3. `--logfile=/dev/stdout` and `--log-level` flag presence on upgrade invocation.
4. Preserved runtime config usage on server startup (`exec python3 "$odoo_bin" server -c "$runtime_config"`).
5. Execution under mock odoo-bin (success flow & failure flow).
6. Exit status preservation and failure delay.
7. Web server is never started after upgrade failure.
8. Docker/Coolify health check inspection.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
START_SCRIPT = REPO_ROOT / "scripts" / "start_odoo.sh"


def test_shell_syntax():
    """Verify POSIX shell syntax."""
    res = subprocess.run(["sh", "-n", str(START_SCRIPT)], capture_output=True, text=True)
    assert res.returncode == 0, f"Shell syntax error in start_odoo.sh: {res.stderr}"
    print("PASS: POSIX shell syntax validation (sh -n)")


def test_script_structure():
    """Verify structural constraints on start_odoo.sh."""
    content = START_SCRIPT.read_text(encoding="utf-8")

    # Single upgrade invocation check
    upgrade_occurrences = content.count("-u \"$auto_upgrade_modules\"")
    assert upgrade_occurrences == 1, f"Expected 1 upgrade invocation, found {upgrade_occurrences}"

    # Logfile stdout check on upgrade command
    assert "--logfile=/dev/stdout" in content, "Missing --logfile=/dev/stdout on upgrade command"
    assert "--log-level=" in content, "Missing --log-level= parameter on upgrade command"

    # Temporary set +e check
    assert "set +e" in content, "Missing set +e around upgrade command"
    assert "upgrade_status=$?" in content, "Missing upgrade_status=$? capture"
    assert "set -e" in content, "Missing set -e after upgrade status capture"

    # Failure delay check
    assert "LHI_UPGRADE_FAILURE_DELAY_SECONDS" in content, "Missing LHI_UPGRADE_FAILURE_DELAY_SECONDS variable"
    assert "sleep" in content, "Missing sleep call on failure"

    # Server startup check
    assert "exec python3 \"$odoo_bin\" server -c \"$runtime_config\"" in content, "Missing server startup line"
    print("PASS: Script structure & flag checks")


def test_execution_flows():
    """Test start_odoo.sh execution using mock environments."""
    temp_dir = Path(tempfile.mkdtemp(prefix="lhi_start_test_"))
    try:
        # Create mock binaries and scripts
        bin_dir = temp_dir / "bin"
        bin_dir.mkdir()

        mock_odoo_bin = bin_dir / "odoo-bin"
        mock_psql = bin_dir / "psql"
        mock_validate = temp_dir / "validate_microsoft_env.sh"

        # Mock psql: return 't' for database initialized, 'f' for bootstrap required
        mock_psql.write_text("""#!/bin/sh
case "$*" in
    *"module.state IS DISTINCT FROM"*)
        echo 'f'
        ;;
    *)
        echo 't'
        ;;
esac
""", encoding="utf-8")
        mock_psql.chmod(0o755)

        # Mock validate_microsoft_env.sh
        mock_validate.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        mock_validate.chmod(0o755)

        # Environment setup for mock run
        base_env = os.environ.copy()
        base_env["PATH"] = f"{bin_dir}:{base_env.get('PATH', '')}"
        base_env["ODOO_MASTER_PASSWORD"] = "test_master_pwd"
        base_env["POSTGRES_DB"] = "lhi_test_db"
        base_env["POSTGRES_USER"] = "odoo"
        base_env["POSTGRES_PASSWORD"] = "odoo_pwd"
        base_env["ODOO_BIN_PATH"] = str(mock_odoo_bin)
        base_env["ODOO_RUNTIME_CONFIG"] = str(temp_dir / "lhi-odoo.conf")
        base_env["LHI_BOOTSTRAP_MODULES"] = ""
        base_env["LHI_UPGRADE_FAILURE_DELAY_SECONDS"] = "1"

        # --- Test 1: Successful Upgrade Flow ---
        mock_odoo_bin.write_text("""#!/usr/bin/env python3
import sys, os

args_str = " ".join(sys.argv)
if "-u" in args_str or "--stop-after-init" in args_str:
    if os.environ.get("TEST_FAIL_MODE") == "1":
        sys.stderr.write("CRITICAL_ERROR: Failed to load view lhi_asset_management.lhi_asset_view\\n")
        sys.exit(42)
    else:
        sys.stdout.write("MOCK_ODOO_BIN: Upgrading modules successfully...\\n")
        sys.exit(0)

sys.stdout.write("MOCK_ODOO_BIN: Web server running...\\n")
sys.exit(0)
""", encoding="utf-8")
        mock_odoo_bin.chmod(0o755)

        # Replace script path references dynamically for mock test run
        run_script = temp_dir / "start_odoo.sh"
        script_text = START_SCRIPT.read_text(encoding="utf-8").replace(
            "/opt/odoo/scripts/validate_microsoft_env.sh", str(mock_validate)
        )
        run_script.write_text(script_text, encoding="utf-8")
        run_script.chmod(0o755)

        res_success = subprocess.run([str(run_script)], env=base_env, capture_output=True, text=True)
        assert res_success.returncode == 0, f"Success flow failed: {res_success.stderr}"
        assert "Container Hostname:" in res_success.stdout, "Missing metadata header in success flow"
        assert "UTC Timestamp:" in res_success.stdout, "Missing timestamp in success flow"
        assert "Deployment schema and view upgrade completed successfully." in res_success.stdout, "Missing success log"
        assert "MOCK_ODOO_BIN: Web server running..." in res_success.stdout, "Web server did not start after upgrade success"
        print("PASS: Execution test - Successful upgrade continues to web server startup")

        # --- Test 2: Failed Upgrade Flow ---
        fail_env = base_env.copy()
        fail_env["TEST_FAIL_MODE"] = "1"

        res_fail = subprocess.run([str(run_script)], env=fail_env, capture_output=True, text=True)
        assert res_fail.returncode == 42, f"Expected returncode 42, got {res_fail.returncode}"
        assert "CRITICAL_ERROR: Failed to load view" in res_fail.stderr, f"Odoo error traceback missing from stderr: {res_fail.stderr}"
        assert "exit code 42" in res_fail.stderr or "exit code 42" in res_fail.stdout, f"Missing exit code in failure message. stderr: '{res_fail.stderr}', stdout: '{res_fail.stdout}'"
        assert "Waiting 1 seconds to ensure logs are captured..." in res_fail.stderr or "Waiting 1 seconds to ensure logs are captured..." in res_fail.stdout, "Missing delay log"
        assert "MOCK_ODOO_BIN: Web server running..." not in res_fail.stdout, "Web server MUST NOT start after upgrade failure"
        print("PASS: Execution test - Failed upgrade preserves exit code 42, logs error, delays, and stops web server start")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_healthcheck_configuration():
    """Verify Docker Compose / Dockerfile health checks do not execute module upgrades."""
    compose_staging = REPO_ROOT / "docker-compose.staging.yml"
    if compose_staging.exists():
        text = compose_staging.read_text(encoding="utf-8")
        assert "healthcheck:" in text, "Missing healthcheck in docker-compose.staging.yml"
        # Extract healthcheck block under odoo service
        odoo_section = text.split("odoo:")[1] if "odoo:" in text else text
        healthcheck_block = odoo_section.split("healthcheck:")[1].split("volumes:")[0]
        assert "/web/health" in healthcheck_block, "Healthcheck should query /web/health readiness endpoint"
        assert "start_odoo.sh" not in healthcheck_block, "Healthcheck MUST NOT execute start_odoo.sh"
        assert "-u" not in healthcheck_block, "Healthcheck MUST NOT execute module upgrade (-u)"
    print("PASS: Healthcheck configuration audit")


def main():
    test_shell_syntax()
    test_script_structure()
    test_execution_flows()
    test_healthcheck_configuration()
    print("\nALL DEPLOYMENT STARTUP TESTS PASSED SUCCESSFULLY.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
