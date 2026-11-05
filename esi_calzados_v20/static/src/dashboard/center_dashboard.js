import { Component, onWillStart, proxy, useProps, types as t } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { useChart } from "@web/core/utils/chart_hook";

const colors = ["#072955", "#009846", "#4296b5", "#e59d32", "#865aa6", "#c85866"];

class CenterChart extends Component {
    static template = "esi_calzados_v20.CenterChart";
    props = useProps({ config: t.any() });
    chart = useChart(() => this.props.config);
}

export class CenterDashboard extends Component {
    static template = "esi_calzados_v20.CenterDashboard";
    static components = { CenterChart };
    props = useProps({ ...standardActionServiceProps });

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({ data: null, filters: {}, loading: false, error: "" });
        this.request = 0;
        onWillStart(() => this.load());
    }

    async load() {
        const request = ++this.request;
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("esi.center.advance.report", "get_center_dashboard", [this.state.filters]);
            if (request === this.request) {
                this.state.data = data;
                this.state.filters = { ...data.filters };
            }
        } catch (error) {
            if (request === this.request) {
                this.state.error = error.data?.message || error.message || "No se pudo cargar el tablero.";
            }
        } finally {
            if (request === this.request) this.state.loading = false;
        }
    }

    changeFilter(name, event) {
        this.state.filters[name] = event.target.value;
    }

    async quickRange(event) {
        const days = Number(event.target.value);
        if (!days) return;
        // Local calendar; the server converts the inclusive dates in the user's timezone.
        const end = luxon.DateTime.now();
        this.state.filters.date_to = end.toISODate();
        this.state.filters.date_from = end.minus({ days: days - 1 }).toISODate();
        await this.load();
    }

    format(value) {
        return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value || 0);
    }

    config(kind) {
        const data = this.state.data;
        const base = { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: { y: { beginAtZero: true } } };
        if (kind === "trend") {
            return { type: "line", data: { labels: [...data.periods],
                datasets: data.series.map((s, index) => ({
                    label: s.name, data: [...s.values], borderColor: colors[index % colors.length],
                    backgroundColor: colors[index % colors.length], tension: 0.2, fill: false,
                })) }, options: base };
        }
        const pending = kind === "pending";
        return { type: pending ? "doughnut" : "bar", data: {
            labels: data.centers.map(c => c.name),
            datasets: [{ label: pending ? "Pendiente actual" : "Avances registrados",
                data: data.centers.map(c => pending ? c.pending : c.advanced),
                backgroundColor: data.centers.map((c, index) => colors[index % colors.length]),
            }],
        }, options: pending ? { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } } } : base };
    }

    openMatrix() {
        return this.action.doAction("esi_calzados_v20.center_advance_report_action");
    }

    async openAnalysis(mode) {
        const filters = this.state.data.filters;
        if (!filters.uom_id) return;
        const id = await this.orm.create("esi.center.advance.report", [{
            company_id: filters.company_id, date_from: filters.date_from,
            date_to: filters.date_to, grouping: filters.grouping, uom_id: filters.uom_id,
        }]);
        const result = await this.orm.call("esi.center.advance.report", "action_pivot", [id]);
        if (mode === "graph") {
            result.views = [[false, "graph"], [false, "pivot"]];
            result.view_mode = "graph,pivot";
            result.context = { ...result.context, graph_groupbys: ["workcenter_id"],
                graph_measure: "quantity", graph_mode: "bar" };
        }
        return this.action.doAction(result);
    }
}
registry.category("actions").add("esi_center_dashboard", CenterDashboard);
