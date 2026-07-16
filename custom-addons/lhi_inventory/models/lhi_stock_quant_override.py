# -*- coding: utf-8 -*-
from odoo import models, fields, api

class StockQuantOverride(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def _update_available_quantity(self, product_id, location_id, quantity, lot_id=None, package_id=None, owner_id=None, in_date=None, **kwargs):
        # Odoo native kwargs could be used to pass custom fields if patched correctly
        # Alternatively, stock moves could update quant directly after _action_done
        return super(StockQuantOverride, self)._update_available_quantity(product_id, location_id, quantity, lot_id=lot_id, package_id=package_id, owner_id=owner_id, in_date=in_date, **kwargs)

class StockMoveOverride(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        res = super(StockMoveOverride, self)._action_done(cancel_backorder=cancel_backorder)
        # Custom logic: Stamp the destination quants with project/donor info
        for move in self:
            if move.lhi_project_id or move.lhi_donor_id:
                for move_line in move.move_line_ids.filtered(lambda ml: ml.state == 'done'):
                    quant = self.env['stock.quant'].search([
                        ('product_id', '=', move_line.product_id.id),
                        ('location_id', '=', move_line.location_dest_id.id),
                        ('lot_id', '=', move_line.lot_id.id if move_line.lot_id else False)
                    ], limit=1)
                    if quant:
                        quant.write({
                            'lhi_project_id': move.lhi_project_id.id if move.lhi_project_id else quant.lhi_project_id.id,
                            'lhi_donor_id': move.lhi_donor_id.id if move.lhi_donor_id else quant.lhi_donor_id.id
                        })
        return res
