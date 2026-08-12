import {
    Component,
    onWillStart,
    useState,
} from "@odoo/owl";

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";


export class LhiProjectDashboard extends Component {
    static template =
        "lhi_project_dashboard.ProjectDashboard";

    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            year: null,
            quarter: "all",
            years: [],
            sections: [],
            projectName: "",
            startDate: null,
            endDate: null,
            metadata: [],
            canConfigure: false,
            currencyCode: "NGN",
        });

        onWillStart(
            async () => {
                await this.loadDashboard();
            }
        );
    }

    async loadDashboard() {
        if (!this.props.record.resId) {
            this.state.loading = false;
            return;
        }

        this.state.loading = true;

        try {
            const result = await this.orm.call(
                this.props.record.resModel,
                "lhi_project_dashboard_data",
                [
                    [this.props.record.resId],
                    this.state.year || false,
                    this.state.quarter,
                ]
            );

            this.state.year = result.year;
            this.state.quarter = result.quarter;
            this.state.years = result.years || [];
            this.state.sections = result.sections || [];
            this.state.projectName =
                result.project_name || "";
            this.state.startDate =
                result.start_date || null;
            this.state.endDate =
                result.end_date || null;
            this.state.metadata =
                result.metadata || [];
            this.state.canConfigure =
                Boolean(result.can_configure);
            this.state.currencyCode =
                result.currency_code || "NGN";
        } catch (error) {
            this.notification.add(
                error?.message ||
                    "The project dashboard could not be loaded.",
                {
                    type: "danger",
                    title: "Project Dashboard",
                    sticky: true,
                }
            );
        } finally {
            this.state.loading = false;
        }
    }

    async onYearChange(event) {
        this.state.year =
            Number.parseInt(event.target.value, 10);

        await this.loadDashboard();
    }

    async onQuarterChange(event) {
        this.state.quarter =
            event.target.value;

        await this.loadDashboard();
    }

    async configureMetrics() {
        const result = await this.orm.call(
            this.props.record.resModel,
            "action_configure_project_dashboard",
            [
                [this.props.record.resId],
            ]
        );

        await this.action.doAction(result);
    }

    formatValue(metric) {
        if (
            metric.value === null ||
            metric.value === undefined
        ) {
            return "—";
        }

        const value = Number(metric.value);

        if (metric.unit === "percentage") {
            return `${value.toLocaleString(
                undefined,
                {
                    maximumFractionDigits: 1,
                }
            )}%`;
        }

        if (metric.unit === "currency") {
            return new Intl.NumberFormat(
                undefined,
                {
                    style: "currency",
                    currency:
                        this.state.currencyCode,
                    maximumFractionDigits: 0,
                }
            ).format(value);
        }

        return value.toLocaleString(
            undefined,
            {
                maximumFractionDigits:
                    metric.unit === "decimal"
                        ? 2
                        : 0,
            }
        );
    }

    progressValue(metric) {
        if (
            metric.unit !== "percentage" ||
            metric.value === null ||
            metric.value === undefined
        ) {
            return 0;
        }

        return Math.max(
            0,
            Math.min(
                100,
                Number(metric.value)
            )
        );
    }
}


registry.category("fields").add(
    "lhi_project_dashboard",
    {
        component: LhiProjectDashboard,
        supportedTypes: ["char"],
    }
);
