# -*- coding: utf-8 -*-
import logging
from odoo import api, models, _

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        fields_to_add = ['qty_available', 'type', 'has_rop', 'rop_count']
        for field in fields_to_add:
            if field not in result['search_params']['fields']:
                result['search_params']['fields'].append(field)
        return result

    def _get_pos_ui_res_partner(self, params):
        partner_ids = [
            partner[0] for partner in self.config_id.get_limited_partners_loading()
        ]
        admin = self.env.ref('base.user_admin', raise_if_not_found=False)
        admin_partner_id = admin.partner_id.id if admin and admin.partner_id else False
        if admin_partner_id:
            partner_ids.append(admin_partner_id)
        params['search_params']['domain'] = [('id', 'in', partner_ids)]
        partners = self.env['res.partner'].search_read(**params['search_params'])
        for partner in partners:
            partner['is_admin'] = partner['id'] == admin_partner_id
        return partners

    @api.model
    def notify_warehouse_rop(self, product_ids):
        """
        Notify warehouse administrators when product quantity <= 5 is encountered during POS payment attempt.
        """
        if not product_ids:
            return []
        products = self.env['product.product'].browse(product_ids).exists()
        if not products:
            return []
        products = products.filtered(
            lambda product: product.type == 'product' and product.qty_available <= 5
        )
        if not products:
            return []

        warehouse_group = self.env.ref('stock.group_stock_manager', raise_if_not_found=False)
        if not warehouse_group:
            warehouse_group = self.env.ref('stock.group_stock_user', raise_if_not_found=False)

        recipients = warehouse_group.users if warehouse_group else self.env['res.users']
        # Also include system admin
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        if admin_user:
            recipients = recipients | admin_user

        partners = recipients.mapped('partner_id')
        if not partners:
            return products.ids

        product_names = ", ".join(products.mapped('display_name'))
        subject = _("ROP Alert: Low Stock Warning in POS")
        body = _(
            "POS Alert: The following product(s) have stock under the Re-Order Point measure (<= 5 units):\n- %s",
            product_names
        )

        for partner in partners:
            partner.message_post(
                body=body,
                subject=subject,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
                partner_ids=[partner.id],
            )

        # Send in-app notify to users in stock.group_stock_manager
        if warehouse_group:
            manager_users = self.env['res.users'].search([
                ('groups_id', 'in', [warehouse_group.id]),
                ('active', '=', True),
            ])
            if manager_users:
                for user in manager_users:
                    self.env['bus.bus']._sendone(
                        user.partner_id,
                        'simple_notification',
                        {
                            'title': subject,
                            'message': body,
                            'sticky': False,
                            'warning': True,
                        },
                    )

        _logger.info("Sent ROP low stock notification for products: %s to warehouse managers.", product_names)
        return products.ids
