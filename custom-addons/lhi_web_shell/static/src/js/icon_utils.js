/** @odoo-module **/

const ICON_ROOT = "/lhi_web_shell/static/src/img/module_icons";
const DEFAULT_APP_ICON = `${ICON_ROOT}/default.svg`;

const APP_ICONS_BY_XMLID = Object.freeze({
    "lhi_dashboard.menu_lhi_dashboard_root": `${ICON_ROOT}/dashboard.svg`,
    "lhi_funding_opportunity.menu_lhi_funding_root": `${ICON_ROOT}/pipeline.svg`,
    "lhi_purchase_request.menu_lhi_procurement_root": `${ICON_ROOT}/procurement.svg`,
    "lhi_base.menu_lhi_operations": `${ICON_ROOT}/operations.svg`,
    "lhi_asset_management.menu_lhi_operations_root": `${ICON_ROOT}/operations.svg`,
    "lhi_asset_management.menu_lhi_asset": `${ICON_ROOT}/assets.svg`,
    "account.menu_finance": `${ICON_ROOT}/accounting.svg`,
    "lhi_results_framework.menu_lhi_meal_root": `${ICON_ROOT}/meal.svg`,
    "stock.menu_stock_root": `${ICON_ROOT}/inventory.svg`,
    "fleet.fleet_menu_root": `${ICON_ROOT}/fleet.svg`,
    "lhi_approval_matrix.menu_lhi_approvals_root": `${ICON_ROOT}/approvals.svg`,
    "lhi_base.menu_lhi_project_root": `${ICON_ROOT}/projects.svg`,
    "hr.menu_hr_root": `${ICON_ROOT}/hr.svg`,
    "lhi_signature_bridge.menu_lhi_opensign": `${ICON_ROOT}/signatures.svg`,
    "base.menu_administration": `${ICON_ROOT}/settings.svg`,
});

export function resolveAppIcon(iconValue, mimeType = "image/png") {
    if (!iconValue || typeof iconValue !== "string") {
        return DEFAULT_APP_ICON;
    }

    const value = iconValue.trim();

    if (!value) {
        return DEFAULT_APP_ICON;
    }

    if (
        value.startsWith("data:") ||
        value.startsWith("/")
    ) {
        return value;
    }

    return `data:${mimeType};base64,${value}`;
}

export function getAppIconProps(app = {}) {
    const mappedIcon = APP_ICONS_BY_XMLID[app.xmlid];
    if (mappedIcon) {
        return { type: "image", src: mappedIcon };
    }

    if (app.webIconData && typeof app.webIconData === "string" && app.webIconData.length > 64) {
        return { type: "image", src: resolveAppIcon(app.webIconData) };
    }

    if (typeof app.webIcon === "string") {
        const webIcon = app.webIcon.trim();
        if (webIcon.includes(",")) {
            const [moduleName, iconPath] = webIcon.split(",", 2).map((part) => part.trim());
            if (moduleName && iconPath) {
                return { type: "image", src: resolveAppIcon(`/${moduleName}/${iconPath}`) };
            }
        }
        if (webIcon.startsWith("fa-")) {
            return { type: "fa", class: `fa ${webIcon}` };
        }
        if (webIcon.startsWith("fa ")) {
            return { type: "fa", class: webIcon };
        }
        if (webIcon.startsWith("/")) {
            return { type: "image", src: resolveAppIcon(webIcon) };
        }
    }

    return { type: "image", src: DEFAULT_APP_ICON };
}
