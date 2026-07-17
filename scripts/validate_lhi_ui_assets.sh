#!/usr/bin/env bash
# =============================================================================
# LHI UI Asset Validator
# scripts/validate_lhi_ui_assets.sh
#
# Validates all LHI-specific SCSS assets to catch common issues before deploy.
# Exits with non-zero status if any validation fails.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CUSTOM_ADDONS="${REPO_ROOT}/custom-addons"
FAILED=0

echo "=== LHI UI Asset Validator ==="
echo "Scanning: ${CUSTOM_ADDONS}"
echo ""

# ── 1. Collect all defined $lhi-* SCSS variables ─────────────────────────────
defined_vars_file=$(mktemp)
grep -RInE '^\s*\$lhi-[A-Za-z0-9_-]+\s*:' "${CUSTOM_ADDONS}" \
    --include='*.scss' 2>/dev/null \
    | grep -oP '\$lhi-[A-Za-z0-9_-]+' \
    | sort -u > "${defined_vars_file}"

# ── 2. Collect all referenced $lhi-* SCSS variables ──────────────────────────
referenced_vars_file=$(mktemp)
grep -RIn '\$lhi-' "${CUSTOM_ADDONS}" \
    --include='*.scss' 2>/dev/null \
    | grep -v '^\s*//' \
    | grep -oP '\$lhi-[A-Za-z0-9_-]+' \
    | sort -u > "${referenced_vars_file}"

# ── 3. Find undefined variables (referenced but not defined) ──────────────────
echo "--- Check 1: Undefined SCSS variables ---"
undefined_vars=$(comm -23 "${referenced_vars_file}" "${defined_vars_file}")
if [[ -n "${undefined_vars}" ]]; then
    echo "FAIL: The following \$lhi-* variables are referenced but never defined:"
    echo "${undefined_vars}" | while read -r varname; do
        echo "  ${varname}"
        grep -Rn "${varname}" "${CUSTOM_ADDONS}" --include='*.scss' | head -3 | sed 's/^/    → /'
    done
    FAILED=1
else
    echo "PASS: All referenced \$lhi-* variables are defined."
fi
echo ""

# ── 4. Check for duplicate variable declarations ──────────────────────────────
echo "--- Check 2: Duplicate variable declarations ---"
duplicate_vars=$(grep -RInE '^\s*\$lhi-[A-Za-z0-9_-]+\s*:' "${CUSTOM_ADDONS}" \
    --include='*.scss' 2>/dev/null \
    | grep -oP '\$lhi-[A-Za-z0-9_-]+' \
    | sort | uniq -d)
if [[ -n "${duplicate_vars}" ]]; then
    echo "WARN: The following \$lhi-* variables are declared multiple times (use !default to prevent conflicts):"
    echo "${duplicate_vars}" | while read -r varname; do
        echo "  ${varname}"
        grep -Rn "^\s*${varname}\s*:" "${CUSTOM_ADDONS}" --include='*.scss' | sed 's/^/    → /'
    done
    # Warn only — duplicates with !default are valid SCSS
else
    echo "PASS: No duplicate \$lhi-* declarations found."
fi
echo ""

# ── 5. Detect malformed/truncated data: URLs ─────────────────────────────────
echo "--- Check 3: Malformed data: URLs ---"
malformed_data_urls=$(grep -RInE \
    "data:image/[a-z]+;base[0-9]+,\s*\.\.\." \
    "${CUSTOM_ADDONS}" \
    --include='*.js' --include='*.xml' --include='*.scss' --include='*.py' 2>/dev/null || true)
if [[ -n "${malformed_data_urls}" ]]; then
    echo "FAIL: Truncated/malformed data: URLs found:"
    echo "${malformed_data_urls}" | sed 's/^/  /'
    FAILED=1
else
    echo "PASS: No truncated data: URLs found."
fi
echo ""

# ── 6. Detect references to icon.png that may 404 ────────────────────────────
echo "--- Check 4: Static icon.png references ---"
icon_refs=$(grep -RIn "icon\.png" "${CUSTOM_ADDONS}" \
    --include='*.js' --include='*.xml' --include='*.scss' --include='*.py' 2>/dev/null || true)
if [[ -n "${icon_refs}" ]]; then
    echo "INFO: Found icon.png references (verify each returns HTTP 200):"
    echo "${icon_refs}" | sed 's/^/  /'
    # Verify the files actually exist
    while IFS= read -r reference_line; do
        if echo "${reference_line}" | grep -qE '/[a-z_]+/static/'; then
            module_path=$(echo "${reference_line}" | grep -oP '/[a-z_]+/static/[^"'"'"']+')
            potential_file="${REPO_ROOT}/custom-addons${module_path}"
            if [[ -n "${module_path}" && ! -f "${potential_file}" ]]; then
                echo "  WARN: File may not exist at: ${potential_file}"
            fi
        fi
    done <<< "${icon_refs}"
else
    echo "PASS: No icon.png references found."
fi
echo ""

# ── 7. Validate manifest asset declarations ───────────────────────────────────
echo "--- Check 5: Manifest SCSS file existence ---"
manifest_files=$(grep -RIn "\.scss'" "${CUSTOM_ADDONS}" \
    --include='__manifest__.py' 2>/dev/null | grep -v '#')
while IFS= read -r manifest_line; do
    scss_path=$(echo "${manifest_line}" | grep -oP "'[^']+\.scss'" | tr -d "'")
    if [[ -n "${scss_path}" ]]; then
        # Convert module-relative path to filesystem path
        module_name=$(echo "${scss_path}" | cut -d'/' -f1)
        rest_path=$(echo "${scss_path}" | cut -d'/' -f2-)
        actual_path="${CUSTOM_ADDONS}/${module_name}/${rest_path}"
        if [[ ! -f "${actual_path}" ]]; then
            echo "FAIL: SCSS file declared in manifest but missing on disk:"
            echo "  Manifest path: ${scss_path}"
            echo "  Expected at:   ${actual_path}"
            FAILED=1
        fi
    fi
done <<< "${manifest_files}"
if [[ ${FAILED} -eq 0 ]]; then
    echo "PASS: All manifest-declared SCSS files exist on disk."
fi
echo ""

# ── 8. Verify tokens.scss is in _assets_primary_variables ────────────────────
echo "--- Check 6: Token loading order ---"
primary_vars_declaration=$(grep -A5 "_assets_primary_variables" \
    "${CUSTOM_ADDONS}/lhi_web_shell/__manifest__.py" 2>/dev/null || true)
if echo "${primary_vars_declaration}" | grep -q "tokens.scss"; then
    echo "PASS: tokens.scss is declared in web._assets_primary_variables."
else
    echo "FAIL: tokens.scss NOT found in web._assets_primary_variables! Variables will be undefined."
    FAILED=1
fi
echo ""

# ── Summary ───────────────────────────────────────────────────────────────────
echo "=== Validation Complete ==="
if [[ ${FAILED} -eq 1 ]]; then
    echo "RESULT: FAILED — Fix the issues above before deploying."
    exit 1
else
    echo "RESULT: PASSED — All checks passed."
    exit 0
fi

# Cleanup
rm -f "${defined_vars_file}" "${referenced_vars_file}"
