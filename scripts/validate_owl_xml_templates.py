#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Owl XML Template Validator.

Scans custom addon QWeb/Owl XML templates for forbidden direct calls to
global JavaScript constructors and functions inside template expressions:
- Number(...)
- parseInt(...)
- parseFloat(...)

Where numeric conversion or formatting is needed, a component JavaScript method
must be used instead (e.g. this.displaySegmentValue(val)).
"""

import os
import re
import sys
from pathlib import Path
from lxml import etree

FORBIDDEN_CALL_PATTERN = re.compile(r"\b(Number|parseInt|parseFloat)\s*\(")


def validate_owl_template_file(file_path):
    errors = []
    try:
        parser = etree.XMLParser(remove_comments=True)
        tree = etree.parse(str(file_path), parser)
    except Exception as exc:
        return [f"{file_path}: XML parse error: {exc}"]

    root = tree.getroot()

    for elem in root.iter():
        line_num = elem.sourceline or 0
        for attr_name, attr_val in elem.attrib.items():
            # Check QWeb/Owl expression attributes
            if attr_name.startswith("t-") or attr_name in ("owl", "t-esc", "t-out", "t-if", "t-elif", "t-set"):
                match = FORBIDDEN_CALL_PATTERN.search(attr_val)
                if match:
                    func_name = match.group(1)
                    errors.append(
                        f"{file_path}:{line_num}: direct call '{func_name}(...)' in attribute {attr_name}=\"{attr_val}\". "
                        "Move conversion logic into a component method."
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
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]

        for f in files:
            if not f.endswith(".xml"):
                continue
            if any(f.endswith(ext) for ext in (".before_*", ".bak", "~")):
                continue

            file_path = Path(root) / f
            xml_count += 1
            errors = validate_owl_template_file(file_path)
            all_errors.extend(errors)

    print(f"Scanned {xml_count} custom XML files for direct Owl template function calls.")
    if all_errors:
        print(f"\nFound {len(all_errors)} forbidden direct template call(s):")
        for err in all_errors:
            print(f"  ERROR: {err}")
        return 1

    print("All custom Owl XML templates passed static expression validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
