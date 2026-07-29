/** @odoo-module **/

import {
    Component,
    useState,
    onWillStart,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class OperationsHub extends Component {
    setup() {
        this.actionService = useService("action");
        this.menuService = useService("menu");
        this.orm = useService("orm");

        this.state = useState({
            modules: [],
            loading: true,
            error: false,
        });

        onWillStart(async () => {
            try {
                const result = await this.orm.call(
                    "lhi.dashboard.widget",
                    "get_accessible_operations",
                    []
                );
                if (result && !Array.isArray(result) && result.modules) {
                    this.state.modules = result.modules;
                    if (result.warnings && result.warnings.length > 0) {
                        for (const warning of result.warnings) {
                            this.env.services.notification.add(warning, { type: "warning", sticky: true, title: "Configuration Warning" });
                        }
                    }
                } else {
                    this.state.modules = result || [];
                }
            } catch (error) {
                console.error(
                    "[LHI Operations] Unable to load accessible modules",
                    error
                );
                this.state.error = true;
            } finally {
                this.state.loading = false;
            }
        });
    }

    async onModuleClick(module) {
        if (module.menu_id) {
            try {
                await this.menuService.selectMenu(module.menu_id);
            } catch (error) {
                console.error("[LHI Operations] Unable to select menu", error);
            }
        }
    }
}

OperationsHub.template = "lhi_dashboard.OperationsHub";

registry.category("actions").add(
    "lhi_dashboard.operations_hub",
    OperationsHub
);
