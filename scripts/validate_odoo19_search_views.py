#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Odoo 19 Structural Search-View Group Validator.

Validates that no <group> element inside a <search> view architecture
in custom_addons contains unsupported Odoo 19 attributes such as 'string' or 'expand'.
Distinguishes search-view groups from form, list, and kanban view groups.
"""

import os
import sys
from pathlib import Path
from lxml import etree

UNSUPPORTED_SEARCH_GROUP_ATTRS = {"string", "expand"}


def validate_xml_file(file_path):
    errors = []
    try:
        parser = etree.XMLParser(remove_comments=False)
        tree = etree.parse(str(file_path), parser)
    except Exception as exc:
        return [f"{file_path}: XML parse error: {exc}"]

    root = tree.getroot()

    for elem in root.iter():
        if elem.tag != "group":
            continue

        # Check if this <group> is inside a <search> view architecture
        ancestors = list(elem.iterancestors())
        is_search_group = False

        if any(a.tag == "search" for a in ancestors):
            is_search_group = True
        else:
            # Check if inside ir.ui.view record with <search> arch
            for a in ancestors:
                if a.tag == "record" and a.attrib.get("model") == "ir.ui.view":
                    arch_elem = a.find("field[@name='arch']")
                    if arch_elem is not None and arch_elem.find(".//search") is not None:
                        is_search_group = True
                    break

        if not is_search_group:
            continue

        line_num = elem.sourceline or 0
        found_attrs = [attr for attr in UNSUPPORTED_SEARCH_GROUP_ATTRS if attr in elem.attrib]

        for attr in found_attrs:
            val = elem.attrib[attr]
            errors.append(
                f"{file_path}:{line_num}: <group> inside <search> view contains unsupported attribute {attr}=\"{val}\"."
            )

    return errors


def main():
    repo_root = Path(__file__).resolve().parent.parent
    custom_addons = repo_root / "custom-addons"
    if not custom_addons.exists():
        custom_addons = Path.cwd() / "custom-addons"

    all_errors = []
    xml_count = 0

    for root, dirs, files in os.walk(custom_addons):
        # Ignore backup and version control directories
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]

        for f in files:
            if not f.endswith(".xml"):
                continue
            if any(f.endswith(ext) for ext in (".before_*", ".bak", "~")):
                continue

            file_path = Path(root) / f
            xml_count += 1
            errors = validate_xml_file(file_path)
            all_errors.extend(errors)

    print(f"Scanned {xml_count} custom XML files for search-view structural compatibility.")
    if all_errors:
        print(f"\nFound {len(all_errors)} invalid search-view group attribute(s):")
        for err in all_errors:
            print(f"  ERROR: {err}")
        return 1

    print("All custom search views passed Odoo 19 structural group validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
