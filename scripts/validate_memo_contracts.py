#!/usr/bin/env python3
import json
import os
import sys

MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "deploy",
    "contracts",
    "memo_integration_contracts.json",
)


def validate_contracts_manifest():
    if not os.path.exists(MANIFEST_PATH):
        print(f"FAIL: Contract manifest not found at {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    expected_orch_version = 1
    if data.get("orchestration_contract_version") != expected_orch_version:
        print(
            f"FAIL: Expected orchestration_contract_version {expected_orch_version}, got {data.get('orchestration_contract_version')}"
        )
        sys.exit(1)

    contracts = data.get("service_contracts", {})
    required_services = ["approval", "storage", "signature", "identity"]
    for svc in required_services:
        if svc not in contracts:
            print(f"FAIL: Missing required service contract entry for '{svc}'")
            sys.exit(1)
        if contracts[svc].get("version") != 1:
            print(f"FAIL: Service contract '{svc}' version is not 1")
            sys.exit(1)

    print("PASS: Contract manifest validation successful.")
    return True


if __name__ == "__main__":
    validate_contracts_manifest()
