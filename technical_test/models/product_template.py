# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    has_rop = fields.Boolean(
        string="Has ROP",
        default=False,
        help="Check this if the product uses Re-Order Point measure.",
    )
    rop_count = fields.Integer(
        string="ROP Count",
        default=0,
        help="The Re-Order Point count value for this product.",
    )
    same_rop_count = fields.Integer(
        string="Products with Same ROP",
        compute='_compute_same_rop_count',
        help="Count of other products that share the same ROP count value.",
    )

    @api.depends('has_rop', 'rop_count')
    def _compute_same_rop_count(self):
        rop_counts = {
            rop_count: count
            for rop_count, count in self._read_group(
                [('has_rop', '=', True), ('rop_count', '>', 0)],
                ['rop_count'],
                ['__count'],
            )
        }
        for record in self:
            if record.has_rop and record.rop_count:
                count = rop_counts.get(record.rop_count, 0)
                record.same_rop_count = count - int(isinstance(record.id, int))
            else:
                record.same_rop_count = 0

    def action_view_same_rop_products(self):
        self.ensure_one()
        return {
            'name': _('Products with ROP Count %s', self.rop_count),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'tree,form,kanban',
            'domain': [
                ('has_rop', '=', True),
                ('rop_count', '=', self.rop_count),
                ('id', '!=', self.id),
            ],
            'context': {'default_has_rop': True, 'default_rop_count': self.rop_count},
        }
