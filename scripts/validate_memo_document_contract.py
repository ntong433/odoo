#!/usr/bin/env python3
"""
validate_memo_document_contract.py
===================================
CI contract gate: reject any code in lhi_memo_management or
lhi_memo_integration that directly accesses protected lhi.document.item
fields outside the MemoDocumentGateway.

Exit codes:
    0 = All patterns safe
    1 = Violations found (blocks CI)

Usage::

    python3 scripts/validate_memo_document_contract.py
    python3 scripts/validate_memo_document_contract.py --report-only

Arguments::

    --report-only   Print violations but exit 0 (for informational CI steps)
"""
import argparse
import ast
import os
import re
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
MEMO_MANAGEMENT_ROOT = WORKSPACE_ROOT / "custom-addons" / "lhi_memo_management"
MEMO_INTEGRATION_ROOT = WORKSPACE_ROOT / "custom-addons" / "lhi_memo_integration"

# Exempt files — the gateway itself is allowed to access document fields
GATEWAY_FILE = MEMO_MANAGEMENT_ROOT / "services" / "memo_document_gateway.py"
EXEMPT_FILES = {
    str(GATEWAY_FILE),
    str(MEMO_MANAGEMENT_ROOT / "tests" / "test_memo_document_gateway.py"),
    str(MEMO_MANAGEMENT_ROOT / "migrations" / "19.0.2.0.0" / "post_migrate.py"),
    # Existing tests access document items with admin context — permit
    str(MEMO_MANAGEMENT_ROOT / "tests" / "test_memo_management.py"),
    str(MEMO_MANAGEMENT_ROOT / "tests" / "test_memo_template.py"),
    str(MEMO_MANAGEMENT_ROOT / "tests" / "test_webhook_controller.py"),
}

# The lhi_memo_integration module has pre-existing patterns that predate the gateway.
# Violations in that module are reported but do not block CI in this sprint.
REPORT_ONLY_FILES = {
    str(MEMO_INTEGRATION_ROOT),  # prefix match below
}

# Protected lhi.document.item fields that must not be accessed directly in Memo code
PROTECTED_FIELDS = frozenset(
    {
        "storage_state",
        "sharepoint_drive_id",
        "sharepoint_item_id",
        "sharepoint_site_id",
        "sharepoint_web_url",
        "sharepoint_etag",
        "sharepoint_version",
        "graph_connection_id",
        "upload_state",
        "last_error",
        "upload_url",
        "spool_path",
    }
)

# Attribute access patterns (Python source): <doc_item_field>.<protected_field>
# These are the Many2one fields on lhi.memo that link to lhi.document.item
SOURCE_LINK_FIELDS = frozenset(
    {
        "source_docx_item_id",
        "source_pdf_item_id",
        "signed_pdf_item_id",
        "certificate_item_id",
    }
)

# Regex for chained attribute access: <link_field>.<protected_field>
# Sudo-guard detection is handled in _line_has_sudo_guard(), not here.
CHAINED_ATTR_PATTERN = re.compile(
    r"\b("
    + "|".join(re.escape(f) for f in sorted(SOURCE_LINK_FIELDS))
    + r")"
    r"\."
    r"("
    + "|".join(re.escape(f) for f in sorted(PROTECTED_FIELDS))
    + r")\b"
)


# Direct env["lhi.document.item"] access without .sudo() before gateway was introduced
DIRECT_MODEL_ACCESS_PATTERN = re.compile(
    r'env\["lhi\.document\.item"\](?!\.sudo\(\))'
)


def _collect_python_files(directory):
    """Yield all .py files in directory, excluding __pycache__."""
    if not directory.exists():
        return
    for path in sorted(directory.rglob("*.py")):
        if "__pycache__" not in str(path):
            yield path


def _is_in_report_only_scope(filepath):
    """Return True if filepath is in a report-only directory (non-blocking)."""
    absolute = str(filepath)
    for prefix in REPORT_ONLY_FILES:
        if absolute.startswith(prefix):
            return True
    return False


def _line_has_sudo_guard(line_content, match_start):
    """
    Return True if the chained field access is guarded by a sudo() call
    on the same line.

    The CHAINED_ATTR_PATTERN match starts at the link_field name.
    The text immediately before that position is the dot separator preceded
    by the object reference.

    Examples:
        ``sudo_memo.source_docx_item_id.storage_state``
            → prefix ends with ``sudo_memo.`` → guarded
        ``self.sudo().source_docx_item_id.storage_state``
            → prefix ends with ``.sudo().`` → guarded
        ``memo.source_docx_item_id.storage_state``
            → prefix ends with ``memo.`` → NOT guarded
    """
    prefix = line_content[:match_start]
    # self.sudo().field or obj.sudo().field
    if re.search(r"\.sudo\(\)\.$", prefix):
        return True
    # sudo_xxx.field  (local variable named sudo_something)
    if re.search(r"\bsudo_\w+\.$", prefix):
        return True
    return False



def _check_file(filepath, violations, report_only_violations):
    """Check a single Python file for contract violations."""
    absolute = str(filepath)
    if absolute in EXEMPT_FILES:
        return

    is_report_only = _is_in_report_only_scope(filepath)

    try:
        source = filepath.read_text(encoding="utf-8")
    except OSError:
        return

    relative = filepath.relative_to(WORKSPACE_ROOT)

    for line_number, line_content in enumerate(source.splitlines(), start=1):
        # Skip comments
        stripped = line_content.strip()
        if stripped.startswith("#"):
            continue

        # Check chained attribute access: source_docx_item_id.storage_state etc.
        for match in CHAINED_ATTR_PATTERN.finditer(line_content):
            link_field = match.group(1)
            protected_field = match.group(2)
            # Skip if guarded by sudo on same line
            if _line_has_sudo_guard(line_content, match.start()):
                continue

            entry = {
                "file": str(relative),
                "line": line_number,
                "content": line_content.strip(),
                "rule": "DIRECT_FIELD_ACCESS",
                "detail": (
                    f"Direct access to lhi.document.item field '{protected_field}' "
                    f"through '{link_field}'. Use MemoDocumentGateway instead."
                ),
            }
            if is_report_only:
                report_only_violations.append(entry)
            else:
                violations.append(entry)

        # Check env["lhi.document.item"] without sudo()
        for match in DIRECT_MODEL_ACCESS_PATTERN.finditer(line_content):
            entry = {
                "file": str(relative),
                "line": line_number,
                "content": line_content.strip(),
                "rule": "UNSUDOED_MODEL_ACCESS",
                "detail": (
                    'Direct env["lhi.document.item"] access without .sudo(). '
                    "Use MemoDocumentGateway or .sudo() for service operations."
                ),
            }
            if is_report_only:
                report_only_violations.append(entry)
            else:
                violations.append(entry)


def main():
    parser = argparse.ArgumentParser(
        description="Validate Memo document contract isolation."
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print violations but exit 0 (non-blocking CI step).",
    )
    arguments = parser.parse_args()

    violations = []
    report_only_violations = []

    search_directories = [MEMO_MANAGEMENT_ROOT]
    if MEMO_INTEGRATION_ROOT.exists():
        search_directories.append(MEMO_INTEGRATION_ROOT)

    total_files = 0
    for directory in search_directories:
        for filepath in _collect_python_files(directory):
            _check_file(filepath, violations, report_only_violations)
            total_files += 1

    if report_only_violations:
        print(
            f"ℹ️   Non-blocking violations in report-only scope "
            f"({len(report_only_violations)}):"
        )
        for violation in report_only_violations:
            print(
                f"  [{violation['rule']}] {violation['file']}:{violation['line']}\n"
                f"    Code:   {violation['content']}\n"
                f"    Reason: {violation['detail']}\n"
            )

    if not violations:
        print(
            f"✅  Memo document contract validation passed. "
            f"Scanned {total_files} files."
        )
        sys.exit(0)

    print(
        f"❌  Memo document contract: {len(violations)} violation(s) found.\n"
    )
    for violation in violations:
        print(
            f"  [{violation['rule']}] {violation['file']}:{violation['line']}\n"
            f"    Code:   {violation['content']}\n"
            f"    Reason: {violation['detail']}\n"
        )

    if arguments.report_only:
        print("ℹ️  --report-only mode: violations reported but exit code is 0.")
        sys.exit(0)

    sys.exit(1)


if __name__ == "__main__":
    main()
