import { Component, useProps } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { standardFieldProps } from '@web/views/fields/standard_field_props';

export class EsiVariantGrid extends Component {
    static template = 'esi_calzados_v20.VariantGrid';
    props = useProps(standardFieldProps);
    get grid() {
        try { const value = JSON.parse(this.props.record.data[this.props.name] || '{}'); return value && typeof value === 'object' ? value : {}; }
        catch { return {}; }
    }
    async change(rowIndex, cellIndex, event) {
        if (this.props.readonly) { return; }
        const qty = Number(event.target.value || 0);
        if (!Number.isFinite(qty) || qty < 0) {
            event.target.setCustomValidity('Introduzca una cantidad positiva o cero.');
            event.target.reportValidity();
            return;
        }
        event.target.setCustomValidity('');
        const grid = this.grid;
        grid.matrix[rowIndex][cellIndex].qty = qty;
        await this.props.record.update({ [this.props.name]: JSON.stringify(grid) });
    }
}
registry.category('fields').add('esi_variant_grid', { component: EsiVariantGrid, supportedTypes: ['text'] });
