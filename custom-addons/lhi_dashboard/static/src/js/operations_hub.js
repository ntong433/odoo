/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class OperationsHub extends Component {
    setup() {
        this.actionService = useService("action");
        this.menuService = useService("menu");
        this.rpc = useService("rpc");

        this.state = useState({
            modules: []
        });

        onWillStart(async () => {
            this.state.modules = await this.rpc("/web/dataset/call_kw/lhi.dashboard.widget/get_accessible_operations", {
                model: "lhi.dashboard.widget",
                method: "get_accessible_operations",
                args: [],
                kwargs: {}
            });
        });
    }

    onModuleClick(module) {
        if (module.menu_id) {
            this.menuService.selectMenu(module.menu_id);
        }
    }
}

OperationsHub.template = "lhi_dashboard.OperationsHub";

registry.category("actions").add("lhi_dashboard.operations_hub", OperationsHub);
