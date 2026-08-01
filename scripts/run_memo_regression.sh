#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR"

echo "=========================================================="
echo "Running LHI Memo Subsystem Contract & Regression Suite"
echo "=========================================================="

PYTHON="${PYTHON:-$REPO_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
    PYTHON="python3"
fi

"$PYTHON" "$SCRIPT_DIR/validate_memo_contracts.py"
"$PYTHON" "$SCRIPT_DIR/check_memo_dependency_changes.py"
"$PYTHON" "$SCRIPT_DIR/validate_odoo19_search_views.py"
"$PYTHON" "$SCRIPT_DIR/validate_owl_xml_templates.py"
sh -n "$SCRIPT_DIR/start_odoo.sh"

echo "=========================================================="
echo "ALL MEMO REGRESSION AND CONTRACT CHECKS PASSED"
echo "=========================================================="
