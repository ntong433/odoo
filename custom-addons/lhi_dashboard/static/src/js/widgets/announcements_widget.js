/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";

export class AnnouncementsWidget extends Component {
    static template = "lhi_dashboard.AnnouncementsWidget";
    
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            announcements: [],
            loading: true,
        });

        onWillStart(async () => {
            try {
                this.state.announcements = await this.orm.call(
                    "lhi.announcement", 
                    "get_active_announcements", 
                    []
                );
            } catch (e) {
                console.error("Failed to load announcements", e);
            } finally {
                this.state.loading = false;
            }
        });
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.announcements", AnnouncementsWidget);
