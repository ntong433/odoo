/** @odoo-module **/

const DEFAULT_APP_ICON = "/web/static/img/default_icon_app.png";

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
        value.startsWith("/") ||
        value.startsWith("http://") ||
        value.startsWith("https://")
    ) {
        return value;
    }

    return `data:${mimeType};base64,${value}`;
}
