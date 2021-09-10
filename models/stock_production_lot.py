# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _


class ProductionLot(models.Model):
    _inherit = 'stock.production.lot'


    # TODO : A revoir
    # @api.model_create_multi
    # def create(self, vals_list):
    #     print('kkkkkkkkkk',vals_list)
    #     active_id = self.env.context.get('active_ids', [])
    #     print('activvv --', self._context)
    #     life_use_date = False
    #     if 'default_life_use_date' in self._context:
    #         print('default_life_use_date------',self._context['default_life_use_date'])
    #         life_use_date = self._context['default_life_use_date']
    #     for values in vals_list:
    #         print('product---',values['product_id'])
    #         product = self.env['product.product'].browse(values['product_id'])
    #         print('product-0---',product)
    #         if product.type_traçabilite == 'ddm' and life_use_date:
    #             print('ddddm')
    #             values['use_date'] = life_use_date
    #         elif product.type_traçabilite == 'dlc' and life_use_date:
    #             print('dllllc')
    #             values['life_date'] = life_use_date
    #     res = super(ProductionLot, self).create(vals_list)
    #     return res

    is_type_tracabilite = fields.Selection(string='Traçabilité', related="product_id.is_type_tracabilite")


    