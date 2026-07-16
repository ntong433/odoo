#!/usr/bin/env python3
# lint-checks.py
# Automated lint checks for LHI Odoo custom addons.

import os
import sys
import ast
import xml.etree.ElementTree as ET
import py_compile

ADDONS_DIR = "./custom-addons"

def get_custom_modules():
    if not os.path.exists(ADDONS_DIR):
        return []
    return [d for d in os.listdir(ADDONS_DIR) if os.path.isdir(os.path.join(ADDONS_DIR, d)) and d.startswith("lhi_")]

def check_python_syntax(module_dir):
    errors = []
    for root, _, files in os.walk(module_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                try:
                    py_compile.compile(path, doraise=True)
                except Exception as e:
                    errors.append(f"Python syntax error in {path}: {str(e)}")
    return errors

def check_xml_validity(module_dir):
    errors = []
    for root, _, files in os.walk(module_dir):
        for f in files:
            if f.endswith(".xml"):
                path = os.path.join(root, f)
                try:
                    ET.parse(path)
                except ET.ParseError as e:
                    errors.append(f"XML structure error in {path}: {str(e)}")
    return errors

def check_manifest(module_name, module_dir):
    errors = []
    manifest_path = os.path.join(module_dir, "__manifest__.py")
    if not os.path.exists(manifest_path):
        errors.append(f"Missing __manifest__.py in module {module_name}")
        return errors

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
            manifest_dict = ast.literal_eval(content)
            
            # Check mandatory keys
            required_keys = ['name', 'version', 'license', 'depends']
            for key in required_keys:
                if key not in manifest_dict:
                    errors.append(f"__manifest__.py of {module_name} is missing key: '{key}'")
            
            # Check license configuration
            if manifest_dict.get('license') != 'LGPL-3':
                errors.append(f"__manifest__.py of {module_name} has invalid license: {manifest_dict.get('license')} (Must be LGPL-3)")
                
            # Verify version pattern (standard Odoo format: 19.0.x.y.z)
            version = manifest_dict.get('version', '')
            if not version.startswith('19.0.'):
                errors.append(f"__manifest__.py of {module_name} must target 19.0 (current version: {version})")
    except Exception as e:
        errors.append(f"Failed to parse __manifest__.py of {module_name}: {str(e)}")
        
    return errors

def check_security_rules(module_name, module_dir):
    errors = []
    has_models = os.path.exists(os.path.join(module_dir, 'models'))
    access_csv = os.path.join(module_dir, 'security', 'ir.model.access.csv')
    
    if has_models and not os.path.exists(access_csv):
        errors.append(f"Module {module_name} contains models/ directory but is missing security/ir.model.access.csv")
    return errors

def main():
    modules = get_custom_modules()
    if not modules:
        print("No custom modules starting with 'lhi_' found in custom-addons.")
        sys.exit(0)
        
    total_errors = []
    print(f"Analyzing {len(modules)} custom modules...")
    
    for mod in modules:
        mod_dir = os.path.join(ADDONS_DIR, mod)
        print(f"Checking module: {mod} ...")
        
        total_errors.extend(check_python_syntax(mod_dir))
        total_errors.extend(check_xml_validity(mod_dir))
        total_errors.extend(check_manifest(mod, mod_dir))
        total_errors.extend(check_security_rules(mod, mod_dir))

    if total_errors:
        print("\n--- Lint Errors Found ---")
        for err in total_errors:
            print(f"[ERROR] {err}")
        sys.exit(1)
        
    print("\nAll validation checks passed successfully!")
    sys.exit(0)

if __name__ == "__main__":
    main()
