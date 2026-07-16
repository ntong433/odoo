/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PowerBIViewer extends Component {
    setup() {
        this.actionService = useService("action");
        this.state = useState({
            reportParams: this.props.action.params || {},
            isLoading: false, // In a real implementation, we'd fetch an embed token here via Entra
        });
    }
}

PowerBIViewer.template = "lhi_powerbi.ReportViewer";
registry.category("actions").add("lhi_powerbi.report_viewer", PowerBIViewer);
