# -*- coding: utf-8 -*-
import os
import xml.etree.ElementTree as ET
from pathlib import Path
import unittest
try:
    from odoo.tests.common import TransactionCase
    from odoo.tools import config
    BaseTestCase = TransactionCase
except (ImportError, KeyError):
    BaseTestCase = unittest.TestCase
    config = {}


class TestXmlCompatibility(BaseTestCase):

    def test_xml_structural_compatibility(self):
        """Validate custom addon XML files against Odoo 19 structural rules."""
        custom_addons = Path(config.get("addons_path", "")).glob("lhi_*")
        addon_paths = [p for p in custom_addons if p.is_dir()]
        if not addon_paths:
            # Fallback to local custom-addons path
            addon_paths = [Path(__file__).resolve().parent.parent.parent]

        valid_app_keys = {
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
        }

        errors = []
        for addon_path in addon_paths:
            for root_dir, _, files in os.walk(addon_path):
                for file_name in files:
                    if not file_name.endswith(".xml"):
                        continue
                    xml_file = Path(root_dir) / file_name
                    try:
                        tree = ET.parse(str(xml_file))
                    except Exception as exc:
                        errors.append(f"{xml_file}: XML parse error: {exc}")
                        continue

                    root = tree.getroot()

                    def inspect_element(elem, ancestors=None):
                        if ancestors is None:
                            ancestors = []
                        tag = elem.tag

                        if tag == "record" and elem.attrib.get("model") == "res.groups":
                            rec_id = elem.attrib.get("id", "unknown")
                            for child in elem.findall("field"):
                                if child.attrib.get("name") == "category_id":
                                    errors.append(
                                        f"{xml_file}: record '{rec_id}' (model='res.groups') contains obsolete field 'category_id'."
                                    )

                        if tag == "record" and elem.attrib.get("model") == "ir.ui.menu":
                            rec_id = elem.attrib.get("id", "unknown")
                            for child in elem.findall("field"):
                                if child.attrib.get("name") == "groups_id":
                                    errors.append(
                                        f"{xml_file}: record '{rec_id}' (model='ir.ui.menu') uses obsolete field 'groups_id' instead of 'group_ids'."
                                    )

                        if tag == "group" and "expand" in elem.attrib:
                            if "search" in [a.tag for a in ancestors] or any(
                                a.tag == "record" and a.attrib.get("model") == "ir.ui.view" for a in ancestors
                            ):
                                errors.append(
                                    f"{xml_file}: <group> element contains obsolete 'expand' attribute inside search view."
                                )

                        if tag == "xpath" and "expr" in elem.attrib:
                            expr = elem.attrib.get("expr", "")
                            if "@string=" in expr:
                                errors.append(
                                    f"{xml_file}: fragile <xpath> selector uses @string attribute: '{expr}'."
                                )

                        if tag == "field" and elem.attrib.get("name") == "lhi_app_key":
                            key = (elem.text or "").strip()
                            if key and key not in valid_app_keys:
                                errors.append(
                                    f"{xml_file}: invalid lhi_app_key '{key}'. Allowed: {sorted(valid_app_keys)}"
                                )

                        if tag == "record" and elem.attrib.get("model") in ("ir.module.category", "res.groups.privilege"):
                            rec_id = elem.attrib.get("id", "unknown")
                            model = elem.attrib.get("model")
                            for child in elem.findall("field"):
                                fname = child.attrib.get("name")
                                if fname in ("name", "placeholder"):
                                    val = (child.text or "").strip()
                                    if any(c in val for c in ["&", "<", ">"]):
                                        errors.append(
                                            f"{xml_file}: record '{rec_id}' ({model}) field '{fname}' contains unsafe character: '{val}'"
                                        )

                        curr_ancestors = ancestors + [elem]
                        for child in elem:
                            inspect_element(child, curr_ancestors)

                    inspect_element(root)

        self.assertFalse(errors, "\n".join(errors))
