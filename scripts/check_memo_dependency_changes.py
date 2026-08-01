#!/usr/bin/env python3
import subprocess
import sys

MEMO_DEPENDENCY_MODULES = [
    "custom-addons/lhi_approval_matrix",
    "custom-addons/lhi_sharepoint_storage",
    "custom-addons/lhi_signature_bridge",
    "custom-addons/lhi_entra_identity_sync",
    "custom-addons/lhi_memo_management",
    "custom-addons/lhi_memo_integration",
]


def check_dependency_changes():
    try:
        output = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD~1"], text=True
        )
    except Exception:
        try:
            output = subprocess.check_output(["git", "status", "--porcelain"], text=True)
        except Exception as err:
            print(f"WARNING: Could not determine git status: {err}")
            return

    changed_files = [line.strip().split()[-1] for line in output.splitlines() if line.strip()]
    affected = set()

    for filepath in changed_files:
        for mod in MEMO_DEPENDENCY_MODULES:
            if filepath.startswith(mod):
                affected.add(mod)

    if affected:
        print(f"NOTICE: Memo dependency modules changed: {', '.join(sorted(affected))}")
        print("Enforcing mandatory Memo contract validation...")
        res = subprocess.call([sys.executable, "scripts/validate_memo_contracts.py"])
        if res != 0:
            print("FAIL: Contract validation failed for changed Memo dependencies!")
            sys.exit(1)
        print("PASS: Memo contract validation gate satisfied.")
    else:
        print("PASS: No Memo dependency changes detected.")


if __name__ == "__main__":
    check_dependency_changes()
