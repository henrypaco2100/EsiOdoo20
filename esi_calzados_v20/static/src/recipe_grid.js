import { Component, useProps } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { standardFieldProps } from '@web/views/fields/standard_field_props';
import { Many2OneField, buildM2OFieldDescription } from '@web/views/fields/many2one/many2one_field';
import { BooleanField, booleanField } from '@web/views/fields/boolean/boolean_field';
import { ProductMatrixDialog } from '@product_matrix/js/product_matrix_dialog';

export class RecipeSelectionDialog extends ProductMatrixDialog {
    static template = 'esi_calzados_v20.RecipeSelectionDialog';

    selectCell(event) {
        // One row fixes color/model/material. Talla varies across columns.
        if (event.target.checked) {
            for (const input of this.productMatrixRef().querySelectorAll('.o_matrix_input')) {
                if (input.dataset.row !== event.target.dataset.row) {
                    input.checked = false;
                }
            }
        }
    }

    async _onConfirm() {
        const inputs = [...this.productMatrixRef().querySelectorAll('.o_matrix_input')];
        const selected = inputs.filter(input => input.checked);
        if (!selected.length) {
            inputs[0]?.setCustomValidity('Seleccione al menos una talla.');
            inputs[0]?.reportValidity();
            return;
        }
        for (const input of inputs) { input.setCustomValidity(''); }
        if (new Set(selected.map(input => input.dataset.row)).size !== 1) {
            return; // Backend also rejects mixed combinations on save.
        }
        // Do not save an old dialog into a different template after navigation.
        const record = this.props.record;
        if (record.data.product_tmpl_id?.id !== this.props.product_template_id || !record.data.esi_multi_variant) {
            this.props.close();
            return;
        }
        await record.data.esi_allowed_variant_ids.set(selected.map(input => Number(input.dataset.product)));
        this.props.close();
    }
}

const opened = new WeakSet();
export async function openRecipeGrid(record, orm, dialog) {
    const template = record.data.product_tmpl_id;
    if (!template?.id || !record.data.esi_multi_variant || opened.has(record)) { return; }
    opened.add(record);
    let delegated = false;
    try {
        const grid = await orm.call('product.template', 'esi_get_recipe_selection_grid',
            [[template.id], record.data.esi_allowed_variant_ids.currentIds]);
        if (record.data.product_tmpl_id?.id !== template.id || !record.data.esi_multi_variant) { return; }
        dialog.add(RecipeSelectionDialog, {
            header: grid.header, rows: grid.matrix, dialogTitle: template.display_name,
            editedCellAttributes: '', product_template_id: template.id, record,
        }, { onClose: () => opened.delete(record) });
        delegated = true;
    } finally {
        if (!delegated) { opened.delete(record); }
    }
}

export class RecipeProductField extends Many2OneField {
    setup() {
        this.orm = useService('orm');
        this.dialog = useService('dialog');
    }
    get m2oProps() {
        const props = super.m2oProps;
        return { ...props, update: async value => {
            await props.update(value);
            if (value && !this.props.readonly) {
                await openRecipeGrid(this.props.record, this.orm, this.dialog);
            }
        }};
    }
}

export class RecipeSharedField extends BooleanField {
    setup() {
        super.setup();
        this.orm = useService('orm');
        this.dialog = useService('dialog');
    }
    async onChange(value) {
        this.state.value = value;
        await this.props.record.update({[this.props.name]: value});
        if (value && !this.props.readonly) {
            await openRecipeGrid(this.props.record, this.orm, this.dialog);
        }
    }
}

export class RecipeVariantsField extends Component {
    static template = 'esi_calzados_v20.RecipeVariantsField';
    props = useProps(standardFieldProps);
    setup() {
        this.orm = useService('orm');
        this.dialog = useService('dialog');
    }
    get selected() { return this.props.record.data[this.props.name].records; }
    async open() {
        if (!this.props.readonly) {
            await openRecipeGrid(this.props.record, this.orm, this.dialog);
        }
    }
}
registry.category('fields').add('esi_recipe_product', buildM2OFieldDescription(RecipeProductField));
registry.category('fields').add('esi_recipe_shared', {...booleanField, component: RecipeSharedField});
registry.category('fields').add('esi_recipe_variants', {
    component: RecipeVariantsField, supportedTypes: ['many2many'],
    relatedFields: () => [{ name: 'display_name', type: 'char' }],
});

export class RecipeButtonField extends RecipeVariantsField {
    static template = 'esi_calzados_v20.SelectionButton';
}

export class OutputSelectionDialog extends ProductMatrixDialog {
    async _onConfirm() {
        const record = this.props.record;
        // product_template_id is the recipe ID for this dialog (native numeric prop).
        if (record.data.state !== 'draft' || !record.data.esi_variant_line_mode ||
            record.data.esi_plan_bom_id?.id !== this.props.product_template_id) {
            this.props.close();
            return;
        }
        const byAttributes = new Map(this.props.rows.flatMap(row => row.slice(1))
            .filter(cell => cell.is_possible_combination)
            .map(cell => [cell.ptav_ids.join(','), cell.product_id]));
        const inputs = [...this.productMatrixRef().querySelectorAll('.o_matrix_input')];
        const quantities = [];
        for (const input of inputs) {
            const qty = Number(input.value || 0);
            input.setCustomValidity('');
            if (!Number.isFinite(qty) || qty < 0) {
                input.setCustomValidity('Introduzca cero o una cantidad positiva.');
                input.reportValidity();
                return;
            }
            quantities.push({product_id: byAttributes.get(input.getAttribute('ptav_ids')), qty});
        }
        if (!quantities.some(cell => cell.qty > 0)) {
            inputs[0]?.setCustomValidity('Indique al menos una cantidad positiva.');
            inputs[0]?.reportValidity();
            return;
        }
        await record.update({esi_output_grid_changes: JSON.stringify({
            bom_id: this.props.product_template_id, quantities,
        })});
        this.props.close();
    }
}

export class OutputSelectorField extends Component {
    static template = 'esi_calzados_v20.SelectionButton';
    props = useProps(standardFieldProps);
    setup() {
        this.orm = useService('orm');
        this.dialog = useService('dialog');
        this.notification = useService('notification');
        this.opened = false;
    }
    async open() {
        const record = this.props.record;
        if (this.props.readonly || record.data.state !== 'draft' || !record.data.esi_variant_line_mode || this.opened) { return; }
        const bom = record.data.esi_plan_bom_id;
        if (!bom?.id) {
            this.notification.add('Seleccione primero una receta compartida.', {type:'warning'});
            return;
        }
        this.opened = true;
        let delegated = false;
        try {
            const grid = await this.orm.call('mrp.bom', 'esi_get_output_selection_grid', [[bom.id]]);
            if (record.data.esi_plan_bom_id?.id !== bom.id || record.data.state !== 'draft') { return; }
            const current = JSON.parse(record.data.esi_output_selection_json || '[]');
            const quantities = new Map(current.map(line => [line.product_id, line.quantity]));
            let count = 0;
            for (const row of grid.matrix) {
                for (const cell of row.slice(1)) {
                    cell.qty = quantities.get(cell.product_id) || 0;
                    if (cell.is_possible_combination) { count++; }
                }
            }
            if (!count) {
                this.notification.add('La receta no tiene tallas activas disponibles.', {type:'warning'});
                return;
            }
            this.dialog.add(OutputSelectionDialog, {
                header:grid.header, rows:grid.matrix, dialogTitle:'Seleccionar tallas y cantidades',
                editedCellAttributes:'', product_template_id:bom.id, record,
            }, {onClose:()=>{this.opened=false;}});
            delegated=true;
        } finally {
            if (!delegated) {this.opened=false;}
        }
    }
}
registry.category('fields').add('esi_recipe_button', {component:RecipeButtonField, supportedTypes:['boolean']});
registry.category('fields').add('esi_output_selector', {component:OutputSelectorField, supportedTypes:['boolean']});
