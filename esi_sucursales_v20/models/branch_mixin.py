from copy import deepcopy

from lxml import etree

from odoo import api, fields, models


class BranchMixin(models.AbstractModel):
    _name = 'esi.branch.mixin'
    _description = 'Presentación de sucursal nativa Odoo 20'

    # IMPORTANT:
    # This field contains only the companies/branches currently selected in the
    # native Odoo company selector (allowed_company_ids in the session).  The
    # previous revision exposed every company assigned to the user and then
    # warned when an inactive one was selected.  That was technically safe but
    # confusing and is exactly what produced the popup reported by the user.
    esi_show_branch = fields.Boolean(compute='_compute_branch_selector')
    esi_branch_company_ids = fields.Many2many(
        'res.company',
        compute='_compute_branch_selector',
        string='Sucursales activas en la sesión',
    )

    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_branch_selector(self):
        active_companies = self.env.companies
        show_selector = len(active_companies) > 1
        for record in self:
            record.esi_show_branch = show_selector
            record.esi_branch_company_ids = active_companies

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type not in ('form', 'list', 'search') or 'company_id' not in self._fields:
            return arch, view

        arch = deepcopy(arch)
        # Never modify nested relational subviews or the cached native architecture.
        nodes = arch.xpath(".//field[@name='company_id' and not(ancestor::field)]")

        if view_type in ('form', 'list'):
            for name in ('esi_show_branch', 'esi_branch_company_ids'):
                if not arch.xpath(".//field[@name='%s' and not(ancestor::field)]" % name):
                    helper = etree.Element('field', name=name, invisible='1')
                    if view_type == 'list':
                        helper.set('column_invisible', 'True')
                    arch.insert(0, helper)

            if not nodes and view_type == 'form':
                targets = arch.xpath('./sheet/group') or arch.xpath('./sheet') or [arch]
                node = etree.Element('field', name='company_id')
                targets[0].insert(0, node)
                nodes = [node]

            for node in nodes:
                node.set('string', 'Sucursal / Compañía')
                old_invisible = node.get('invisible', 'False')
                node.set('invisible', '(not esi_show_branch) or (%s)' % old_invisible)
                # Only session-active companies are offered.  This avoids the old
                # "active la sucursal seleccionada" warning and keeps the normal
                # Odoo multi-company security/context intact.
                node.set('domain', "[('id', 'in', esi_branch_company_ids)]")
                node.set('options', "{'no_create': True}")
                if self._name == 'account.journal':
                    node.set('readonly', 'id')
                # Visibility depends on the current session, not merely on the
                # technical multi-company group.
                if node.get('groups') == 'base.group_multi_company':
                    node.attrib.pop('groups')
        else:
            for node in nodes:
                node.set('string', 'Sucursal / Compañía')
            if not nodes:
                arch.append(etree.Element('field', name='company_id', string='Sucursal / Compañía'))
            if not arch.xpath(".//filter[@name='esi_group_company']"):
                arch.append(etree.Element('separator'))
                arch.append(
                    etree.Element(
                        'filter',
                        name='esi_group_company',
                        string='Por sucursal / compañía',
                        context="{'group_by': 'company_id'}",
                    )
                )
        return arch, view

    def _esi_validate_ready_pickings(self, code):
        """Validate only already picked operations; never invent done quantities."""
        self.ensure_one()
        for picking in self.picking_ids.filtered(
            lambda p: p.picking_type_id.code == code and p.state not in ('done', 'cancel')
        ):
            picking.check_access('write')
            moves = picking.move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel') and m.product_uom_qty
            )
            if (
                picking.state != 'assigned'
                or not moves
                or any(not m.picked or m.quantity <= 0 for m in moves)
            ):
                self.message_post(
                    body='Transferencia pendiente: registre y marque las cantidades realizadas antes de validar.'
                )
                continue
            result = picking.button_validate()
            if isinstance(result, dict):
                return result
        return False
