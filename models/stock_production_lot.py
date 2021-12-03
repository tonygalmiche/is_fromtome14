# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _


class ProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    is_type_tracabilite = fields.Selection(string='Traçabilité', related="product_id.is_type_tracabilite")
    product_qty         = fields.Float(digits="Product Unit of Measure")
