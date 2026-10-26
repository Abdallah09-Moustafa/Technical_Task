# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.constrains('picking_type_id', 'scheduled_date')
    def _check_outgoing_scheduled_date(self):
        for picking in self:
            if picking.picking_type_id and picking.picking_type_id.code == 'outgoing' and picking.scheduled_date:
                today = fields.Date.context_today(picking)
                scheduled_date = fields.Date.to_date(picking.scheduled_date)
                if scheduled_date < today:
                    raise ValidationError(_(
                        "For outgoing transfers, the Scheduled Date (%s) must be greater than or equal to today (%s).",
                        scheduled_date, today
                    ))
