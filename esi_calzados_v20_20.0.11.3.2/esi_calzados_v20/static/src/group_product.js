import { Many2OneField, buildM2OFieldDescription } from '@web/views/fields/many2one/many2one_field';
import { ProductMatrixDialog } from '@product_matrix/js/product_matrix_dialog';
import { useService } from '@web/core/utils/hooks';
import { registry } from '@web/core/registry';

export class GroupMatrixDialog extends ProductMatrixDialog {
    async _onConfirm() {
        if (this.confirming) { return; }
        const record = this.props.record;
        if (record.data.state !== 'draft' ||
            record.data.esi_grid_template_id?.id !== this.props.product_template_id) {
            this.props.close();
            return;
        }
        const inputs = this.productMatrixRef()?.querySelectorAll('.o_matrix_input') || [];
        const changes = [];
        for (const input of inputs) {
            const qty = Number(input.value || 0);
            if (!Number.isFinite(qty) || qty < 0) {
                input.setCustomValidity('Introduzca cero o una cantidad positiva.');
                input.reportValidity();
                return;
            }
            input.setCustomValidity('');
            changes.push({ qty, ptav_ids: input.getAttribute('ptav_ids').split(',').filter(Boolean).map(Number) });
        }
        this.confirming = true;
        try {
            await record.update({esi_grid_changes: JSON.stringify({
                template_id: this.props.product_template_id, changes,
            })});
            this.props.close();
        } finally {
            this.confirming = false;
        }
    }
}

const opened = new WeakSet();
export async function openGroupGrid(line, value, dialog, notification) {
    const root = line.model.root;
    if (!value?.id || root.data.state !== 'draft' || opened.has(root)) { return; }
    opened.add(root);
    let delegated = false;
    try {
        if (root.data.esi_grid_template_id?.id === value.id) {
            await root.update({esi_grid_template_id: false});
        }
        await root.update({esi_grid_template_id: value});
        if (root.data.state !== 'draft' || root.data.esi_grid_template_id?.id !== value.id) { return; }
        let matrix;
        try { matrix = JSON.parse(root.data.esi_grid_data || 'null'); } catch { matrix = null; }
        if (!Array.isArray(matrix?.header) || !Array.isArray(matrix?.matrix) ||
            !matrix.matrix.some(row => row.slice(1).some(cell => cell.is_possible_combination))) {
            notification.add('No hay una cuadrícula de variantes disponible para este producto.', {type: 'warning'});
            return;
        }
        dialog.add(GroupMatrixDialog, {
            header: matrix.header, rows: matrix.matrix, dialogTitle: value.display_name,
            editedCellAttributes: '', product_template_id: value.id, record: root,
        }, {onClose: () => opened.delete(root)});
        delegated = true;
        // Native sales behavior: discard the temporary selector row. Confirming
        // creates persistent product.product lines through the parent onchange.
        if (!line.data.product_id) {
            await root.data.line_ids.delete(line);
        }
    } finally {
        if (!delegated) { opened.delete(root); }
    }
}

export class GroupProductField extends Many2OneField {
    setup() {
        this.dialog = useService('dialog');
        this.notification = useService('notification');
    }
    get m2oProps() {
        return {...super.m2oProps, update: async value => {
            if (!this.props.readonly) {
                await openGroupGrid(this.props.record, value, this.dialog, this.notification);
            }
        }};
    }
}
registry.category('fields').add('esi_group_product', buildM2OFieldDescription(GroupProductField));
