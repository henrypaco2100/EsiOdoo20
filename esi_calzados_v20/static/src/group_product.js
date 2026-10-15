import { Many2OneField, buildM2OFieldDescription } from '@web/views/fields/many2one/many2one_field';
import { ProductMatrixDialog } from '@product_matrix/js/product_matrix_dialog';
import { useService } from '@web/core/utils/hooks';
import { registry } from '@web/core/registry';

class GroupMatrixDialog extends ProductMatrixDialog {
    async _onConfirm() {
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
        await this.props.record.update({esi_grid_changes: JSON.stringify({
            template_id: this.props.product_template_id, changes,
        })});
        this.props.close();
    }
}

class GroupProductField extends Many2OneField {
    setup() {
        this.orm = useService('orm');
        this.dialog = useService('dialog');
    }
    get m2oProps() {
        return {...super.m2oProps, update: async (value) => {
            if (!value) { return; }
            const root = this.props.record.model.root;
            if (root.data.esi_grid_template_id?.id === value.id) {
                await root.update({esi_grid_template_id: false});
            }
            await root.update({esi_grid_template_id: value});
            const matrix = JSON.parse(root.data.esi_grid_data);
            this.dialog.add(GroupMatrixDialog, {
                header: matrix.header, rows: matrix.matrix, dialogTitle: value.display_name,
                editedCellAttributes: '', product_template_id: value.id, record: root,
            });
            // Like the native sales matrix, the selector row is only a placeholder.
            if (!this.props.record.data.product_id) {
                await root.data.line_ids.delete(this.props.record);
            }
        }};
    }
}
registry.category('fields').add('esi_group_product', buildM2OFieldDescription(GroupProductField));
