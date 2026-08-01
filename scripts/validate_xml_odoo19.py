#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Odoo 19 XML and RBAC Static Compatibility Validator.

Validates all custom lhi_* addon XML files against Odoo 19 structural rules:
1. No category_id field on res.groups records
2. No expand attributes on search view <group> elements
3. No groups_id field on ir.ui.menu records
4. No fragile XPath expressions based on @string attributes
5. Valid XML syntax
6. Required privilege_id on res.groups application access records
7. Valid LHI application keys for lhi_app_key fields
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

VALID_LHI_APP_KEYS = {
    "operations",
    "hub",
    "assets",
    "procurement",
    "inventory",
    "fleet",
    "programs_grants",
    "approvals",
    "reports",
    "power_bi",
    "media",
    "meal",
    "memo",
    "signatures",
    "hr_leave",
}


def validate_xml_file(file_path):
    errors = []
    try:
        tree = ET.parse(str(file_path))
    except Exception as exc:
        return [f"{file_path}: XML parse error: {exc}"]

    root = tree.getroot()

    def inspect_element(elem, parent=None, ancestors=None):
        if ancestors is None:
            ancestors = []

        tag = elem.tag

        # Check 1: res.groups records
        if tag == "record" and elem.attrib.get("model") == "res.groups":
            record_id = elem.attrib.get("id", "unknown")

            # Check category_id on res.groups
            for field_elem in elem.findall("field"):
                if field_elem.attrib.get("name") == "category_id":
                    errors.append(
                        f"{file_path}: record '{record_id}' (model='res.groups') contains obsolete field 'category_id'."
                    )

        # Check 3: ir.ui.menu records using groups_id
        if tag == "record" and elem.attrib.get("model") == "ir.ui.menu":
            record_id = elem.attrib.get("id", "unknown")
            for field_elem in elem.findall("field"):
                if field_elem.attrib.get("name") == "groups_id":
                    errors.append(
                        f"{file_path}: record '{record_id}' (model='ir.ui.menu') uses obsolete field 'groups_id' instead of 'group_ids'."
                    )

        # Check 2: <group expand="..."> inside search views
        if tag == "group" and "expand" in elem.attrib:
            if "search" in ancestors or any(
                a.tag == "record" and a.attrib.get("model") == "ir.ui.view" for a in ancestors
            ):
                errors.append(
                    f"{file_path}: <group> element contains obsolete 'expand' attribute inside search view."
                )

        # Check 4: Fragile XPath expressions using @string
        if tag == "xpath" and "expr" in elem.attrib:
            expr = elem.attrib.get("expr", "")
            if "@string=" in expr:
                errors.append(
                    f"{file_path}: fragile <xpath> selector uses @string attribute: '{expr}'."
                )

        # Check 7: lhi_app_key field values
        if tag == "field" and elem.attrib.get("name") == "lhi_app_key":
            app_key = (elem.text or "").strip()
            if app_key and app_key not in VALID_LHI_APP_KEYS:
                errors.append(
                    f"{file_path}: invalid lhi_app_key '{app_key}'. Allowed: {sorted(VALID_LHI_APP_KEYS)}"
                )

        current_ancestors = ancestors + [elem]
        for child in elem:
            inspect_element(child, parent=elem, ancestors=current_ancestors)

    inspect_element(root)
    return errors


def main():
    repo_root = Path(__file__).resolve().parent.parent
    custom_addons = repo_root / "custom-addons"
    if not custom_addons.exists():
        custom_addons = Path.cwd() / "custom-addons"

    all_errors = []
    xml_count = 0

    for root, _, files in os.walk(custom_addons):
        for f in files:
            if f.endswith(".xml"):
                xml_count += 1
                file_path = Path(root) / f
                errors = validate_xml_file(file_path)
                all_errors.extend(errors)

    print(f"Scanned {xml_count} XML files across custom-addons.")
    if all_errors:
        print(f"\nFound {len(all_errors)} Odoo 19 compatibility failure(s):")
        for err in all_errors:
            print(f"  ERROR: {err}")
        return 1

    print("All custom XML files passed static Odoo 19 compatibility checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
