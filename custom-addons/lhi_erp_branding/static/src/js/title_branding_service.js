/** @odoo-module **/

import { registry } from "@web/core/registry";
import { titleService } from "@web/core/browser/title_service";
import { Dialog } from "@web/core/dialog/dialog";

// Default title for Owl dialogs
if (Dialog && Dialog.defaultProps) {
    Dialog.defaultProps.title = "LHI ERP";
}

const lhiErpTitleBrandingService = {
    dependencies: ["title"],

    start(env, { title }) {
        title.setParts({
            odoo: null,
            zopenerp: null,
            lhi_erp_brand: "LHI ERP",
        });

        return {};
    },
};

registry
    .category("services")
    .add("lhi_erp_title_branding", lhiErpTitleBrandingService);

// Ensure title service strips Odoo and formats titles consistently across all views
const originalTitleServiceStart = titleService.start;
export const lhiErpTitleServiceOverride = {
    ...titleService,
    start(env, ...args) {
        const titleObj = originalTitleServiceStart.call(this, env, ...args);
        const originalSetParts = titleObj.setParts;
        titleObj.setParts = function (parts) {
            if (parts && typeof parts === "object") {
                if ("odoo" in parts) {
                    delete parts.odoo;
                }
                if ("zopenerp" in parts) {
                    delete parts.zopenerp;
                }
            }
            return originalSetParts.call(this, parts);
        };
        titleObj.setParts({
            odoo: null,
            zopenerp: null,
            lhi_erp_brand: "LHI ERP",
        });
        return titleObj;
    },
};

registry.category("services").add("title", lhiErpTitleServiceOverride, { force: true });
