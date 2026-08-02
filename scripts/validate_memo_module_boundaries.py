#!/usr/bin/env python3
"""
Pre-deployment contract validator for Memo module boundaries.

Validates that:
1. Exactly one Python file declares `_name = "lhi.memo.integration.operation"`.
2. The owner is `custom-addons/lhi_memo_integration/models/lhi_memo_integration_operation.py`.
3. The owner file is imported in `custom-addons/lhi_memo_integration/models/__init__.py`.
4. Core Memo module (`lhi_memo_management`) has ZERO references to `lhi.memo.integration.operation` or `lhi_memo_integration`.
5. No circular dependency exists between `lhi_memo_management` and `lhi_memo_integration`.
6. `lhi_memo_integration` depends on `lhi_memo_management`.
7. Required security CSV (`custom-addons/lhi_memo_integration/security/ir.model.access.csv`) exists and is non-empty.
8. Mandatory required addon `lhi_memo_integration` is present in `scripts/start_odoo.sh`.
"""
import ast
import os
import re
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CUSTOM_ADDONS = WORKSPACE_ROOT / "custom-addons"
MANAGEMENT_DIR = CUSTOM_ADDONS / "lhi_memo_management"
INTEGRATION_DIR = CUSTOM_ADDONS / "lhi_memo_integration"


def check_single_operation_model_declaration():
    """Verify exactly one model declares _name = 'lhi.memo.integration.operation'."""
    pattern = re.compile(r'_name\s*=\s*["\']lhi\.memo\.integration\.operation["\']')
    declarations = []

    for path in CUSTOM_ADDONS.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        try:
            content = path.read_text(encoding="utf-8")
            if pattern.search(content):
                declarations.append(path.relative_to(WORKSPACE_ROOT))
        except OSError:
            pass

    print(f"Checking operation model declarations: found {len(declarations)}")
    for decl in declarations:
        print(f"  - {decl}")

    if len(declarations) != 1:
        print(
            f"❌  FAILURE: Expected exactly 1 declaration of 'lhi.memo.integration.operation', "
            f"found {len(declarations)}: {declarations}",
            file=sys.stderr,
        )
        return False

    expected_owner = Path("custom-addons/lhi_memo_integration/models/lhi_memo_integration_operation.py")
    if declarations[0] != expected_owner:
        print(
            f"❌  FAILURE: Operation model owner must be '{expected_owner}', "
            f"found '{declarations[0]}'",
            file=sys.stderr,
        )
        return False

    return True


def check_owner_imported():
    """Verify the operation model file is imported in lhi_memo_integration/models/__init__.py."""
    init_path = INTEGRATION_DIR / "models" / "__init__.py"
    if not init_path.exists():
        print(f"❌  FAILURE: Missing {init_path}", file=sys.stderr)
        return False

    content = init_path.read_text(encoding="utf-8")
    if "lhi_memo_integration_operation" not in content:
        print(
            f"❌  FAILURE: 'lhi_memo_integration_operation' is not imported in {init_path}",
            file=sys.stderr,
        )
        return False

    return True


def check_no_reverse_dependency_in_core():
    """Verify lhi_memo_management has no references to lhi.memo.integration.operation or lhi_memo_integration."""
    forbidden_terms = [
        'lhi.memo.integration.operation',
        'lhi_memo_integration',
    ]

    violations = []
    for path in MANAGEMENT_DIR.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        content = path.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for term in forbidden_terms:
                if term in line:
                    violations.append(
                        f"{path.relative_to(WORKSPACE_ROOT)}:{line_num} -> {line.strip()}"
                    )

    if violations:
        print("❌  FAILURE: Reverse dependency / direct integration references found in lhi_memo_management:", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        return False

    return True


def check_manifest_dependencies():
    """Verify manifest dependency direction: integration -> management, NOT management -> integration."""
    m_manifest_path = MANAGEMENT_DIR / "__manifest__.py"
    i_manifest_path = INTEGRATION_DIR / "__manifest__.py"

    m_manifest = ast.literal_eval(m_manifest_path.read_text(encoding="utf-8"))
    i_manifest = ast.literal_eval(i_manifest_path.read_text(encoding="utf-8"))

    m_depends = m_manifest.get("depends", [])
    i_depends = i_manifest.get("depends", [])

    if "lhi_memo_integration" in m_depends:
        print(
            "❌  FAILURE: Circular/reverse dependency: lhi_memo_management depends on lhi_memo_integration!",
            file=sys.stderr,
        )
        return False

    if "lhi_memo_management" not in i_depends:
        print(
            "❌  FAILURE: lhi_memo_integration must depend on lhi_memo_management!",
            file=sys.stderr,
        )
        return False

    return True


def check_security_and_startup_bundle():
    """Verify security CSV exists and start_odoo.sh includes lhi_memo_integration."""
    access_path = INTEGRATION_DIR / "security" / "ir.model.access.csv"
    if not access_path.exists() or access_path.stat().st_size == 0:
        print(f"❌  FAILURE: {access_path} is missing or empty!", file=sys.stderr)
        return False

    start_script = WORKSPACE_ROOT / "scripts" / "start_odoo.sh"
    if not start_script.exists():
        print(f"❌  FAILURE: {start_script} does not exist!", file=sys.stderr)
        return False

    script_content = start_script.read_text(encoding="utf-8")
    if "lhi_memo_integration" not in script_content:
        print(
            "❌  FAILURE: scripts/start_odoo.sh does not include 'lhi_memo_integration'!",
            file=sys.stderr,
        )
        return False

    return True


def main():
    print("==========================================================")
    print("Validating Memo Module Boundaries & Architectural Invariants")
    print("==========================================================")

    checks = [
        ("Single Operation Model Declaration", check_single_operation_model_declaration),
        ("Owner Imported in Integration Module", check_owner_imported),
        ("No Reverse Dependency in Core Module", check_no_reverse_dependency_in_core),
        ("Manifest Dependencies & No Circularity", check_manifest_dependencies),
        ("Security CSV & Startup Script Bundle", check_security_and_startup_bundle),
    ]

    failed = False
    for name, check_func in checks:
        print(f"\n[CHECK] {name}...")
        if not check_func():
            print(f"❌ {name} FAILED")
            failed = True
        else:
            print(f"✅ {name} PASSED")

    print("\n==========================================================")
    if failed:
        print("❌  MODULE BOUNDARY VALIDATION FAILED")
        sys.exit(1)
    else:
        print("✅  ALL MEMO MODULE BOUNDARY CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
