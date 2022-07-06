
# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons import decimal_precision as dp

class SupplierDiscount(models.Model):
    _name = "product.supplierdiscount"
    _description = "SupplierDiscount"

    name = fields.Float('Discount')
    supplier_info_id = fields.Many2one('product.supplierinfo')
    date_start = fields.Date('Start Date', help="Start date for this vendor price", related='supplier_info_id.date_start')
    date_end = fields.Date('End Date', help="End date for this vendor price", related='supplier_info_id.date_end')
    delay = fields.Integer(
        'Delivery Lead Time', default=0, required=True,
        help="Lead time in days between the confirmation of the purchase order and the receipt of the products in your warehouse. Used by the scheduler for automatic computation of the purchase order planning.")


class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    date_start = fields.Date('Start Date', help="Start date for this vendor price", required=True)
    date_end = fields.Date('End Date', help="End date for this vendor price", required=True)
    # barcode = fields.Char(
    #     'Code Barre',
    #     help="International Article Number used for product identification.")

    @api.depends('discount_ids','discount_ids.name','prix_brut')
    def compute_prix_net(self):
        for s in self:
            remise  = 0
            price = s.prix_brut
            if len(s.discount_ids)>0:
                for r in s.discount_ids:
                    # remise += r.name
                    price= price * (1- r.name/100)
            s.price = price

    prix_brut=fields.Float(string="Prix Brut", digits=(14,4))
    discount_ids=fields.One2many('product.supplierdiscount','supplier_info_id',string='Taux de remises')
    price = fields.Float(
        'Price', default=0.0, digits=dp.get_precision('Product Price'),
        required=True, help="The price to purchase a product", compute=compute_prix_net, store=True)


    # @api.depends('product_tmpl_id','date_start','date_end','name','price')
    # def fct_last_info(self):
    #     supp_info = self.env['product.supplierinfo'].search(
    #     [('name', '=', self.name.id), ('product_tmpl_id', '=', self.product_tmpl_id.id),
    #     ('date_start','<',self.date_start),
    #     ('date_end','<',self.date_end)],
    #         limit=1, order='date_start desc')
    #     self.last_supp_info = supp_info.id

    # last_supp_info = fields.Many2one('product.supplierinfo', compute=fct_last_info, string="Dernier Prix Fournisseur")
    # last_discount_ids = fields.One2many('product.supplierdiscount','supplier_info_id',string='Anciens Taux de remises', related='last_supp_info.discount_ids')
    # last_prix_brut = fields.Float('Dernier Prix Brut', related="last_supp_info.prix_brut")
    # last_price = fields.Float('Dernier Prix Net', related="last_supp_info.price")

    # @api.onchange('barcode')
    # @api.multi
    # def barcode_uniq(self):
    #     print('babaabababaa')
    #     list = []
    #     if self.barcode or self._origin.barcode:
    #         barcode_list = self.env['product.supplierinfo'].search([('barcode', '=', self.barcode)])
    #         print('baaaalllll--',barcode_list)
    #         if barcode_list:
    #             print('b&&&&&')
    #             for l in barcode_list:
    #                 list.append(l.id)
    #         print('llllllll--',list)
    #         if len(list) >= 1:
    #             print('messaaaageeee')
    #             warning_mess = {
    #                 'title': _('Référence interne'),
    #                 'message': _(
    #                     "Un code-barre ne peut être assigné qu'à un seul produit!")
    #             }
    #             return {'warning': warning_mess}
