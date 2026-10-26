# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class UpdateProductQtyWizard(models.TransientModel):
    _name = 'update.product.qty.wizard'
    _description = 'Update Product Quantity Wizard'

    product_id = fields.Many2one(
        'product.product',
        required=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        readonly=True,
    )
    current_qty = fields.Float(
        string='Current Quantity on Hand',
        related='product_id.qty_available',
        readonly=True,
    )
    new_quantity = fields.Integer(
        string='New Quantity on Hand',
        required=True,
        default=0,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')
        if active_model == 'product.product' and active_id:
            product = self.env['product.product'].browse(active_id)
            res['product_id'] = product.id
            res['new_quantity'] = int(product.qty_available)
        elif active_model == 'product.template' and active_id:
            tmpl = self.env['product.template'].browse(active_id)
            product = tmpl.product_variant_id or tmpl.product_variant_ids[:1]
            if product:
                res['product_id'] = product.id
                res['new_quantity'] = int(product.qty_available)
        return res

    def action_update_quantity(self):
        self.ensure_one()
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(_("Only inventory managers can update on-hand quantities."))
        if self.new_quantity < 0:
            raise UserError(_("Quantity cannot be negative."))
        product_company = self.product_id.product_tmpl_id.company_id
        if product_company and product_company != self.env.company:
            raise UserError(_("This product belongs to a different company."))

        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        location = warehouse.lot_stock_id
        if not location:
            raise UserError(_("No internal stock location is configured for this company."))

        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product_id.id,
            'location_id': location.id,
            'inventory_quantity': self.new_quantity,
        })._apply_inventory()

        self._notify_warehouse_and_admin()
        return {'type': 'ir.actions.act_window_close'}

    def _notify_warehouse_and_admin(self):
        """Send notification to other admins and warehouse managers that stock was updated."""
        warehouse_group = self.env.ref('stock.group_stock_manager', raise_if_not_found=False)
        recipients = warehouse_group.users if warehouse_group else self.env['res.users']
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        if admin_user:
            recipients = recipients | admin_user

        # Filter out current user from recipients to notify 'other' admins/managers
        other_recipients = recipients.filtered(lambda u: u.id != self.env.user.id)
        if not other_recipients:
            other_recipients = recipients

        subject = _("Product Quantity Updated: %s", self.product_id.display_name)
        body = _(
            "Product Quantity Update Notification:\n"
            "- Product: %s\n"
            "- Updated by: %s\n"
            "- New Quantity on Hand: %s units",
            self.product_id.display_name,
            self.env.user.name,
            self.new_quantity
        )
        notification_body = _(
            "Product '%s' was updated to %s units by %s.",
            self.product_id.display_name,
            self.new_quantity,
            self.env.user.name,
        )

        for partner in other_recipients.mapped('partner_id'):
            partner.message_post(
                body=body,
                subject=subject,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
                partner_ids=[partner.id],
            )
            # Instant in-app notification (systray toast) for the other admins.
            self.env['bus.bus']._sendone(
                partner,
                'simple_notification',
                {
                    'title': _("Warehouse Stock Updated"),
                    'message': notification_body,
                    'sticky': False,
                    'warning': False,
                },
            )
        _logger.info("Sent quantity update notification for product %s to %s", self.product_id.display_name, other_recipients.mapped('name'))
        return other_recipients
