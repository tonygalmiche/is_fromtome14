# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    is_dlc_ddm = fields.Date('DLC / DDM', related="lot_id.is_dlc_ddm")



#TODO : A revoir

# class StockQuant(models.Model):
#     _inherit = 'stock.quant'
#     weight = fields.Float(string='Poids', related="package_id.weight", store=True)
#     weight_uom_id = fields.Many2one('uom.uom', 'UM Poids', related="package_id.weight_uom_id", store=True)
#     life_use_date = fields.Datetime('DLC/DDM', related="package_id.life_use_date", store=True)


# class StockQuantPackage(models.Model):
#     _inherit = "stock.quant.package"

#     @api.one
#     @api.depends('quant_ids')
#     def _compute_weight(self):
#         weight = 0.0
#         current_picking_move_line_ids = self.env['stock.move.line'].search(
#             [('result_package_id', '=', self.id)])
#         print('pppppppp',current_picking_move_line_ids)
#         if current_picking_move_line_ids:
#             for ml in current_picking_move_line_ids:
#                 weight +=  ml.weight
#             self.weight = weight
#             self.weight_uom_id = current_picking_move_line_ids[0].weight_uom_id.id
#             self.life_use_date = current_picking_move_line_ids[0].life_use_date


#     weight = fields.Float('Poids',compute='_compute_weight',
#                           help="Weight computed based on the sum of the weights of the products.", store=True)
#     weight_uom_id = fields.Many2one('uom.uom', 'UM Poids',compute='_compute_weight', store=True)
#     life_use_date = fields.Datetime('DLC/DDM',compute='_compute_weight', store=True)



