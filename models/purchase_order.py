# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    is_commande_soldee = fields.Boolean(string=u'Commande soldée', default=False, copy=False, help=u"Cocher cette case pour indiquer qu'aucune nouvelle livraison n'est prévue sur celle-ci")


    def creer_commande_fromtome_action(self):
        for obj in self:
            vals={
                'company_id': 1,
                'partner_id': 3779,
                'user_id'   : 27,
            }
            order=self.env['sale.order'].sudo().create(vals)
            if order:
                for line in obj.order_line:
                    default_code =  (line.product_id.default_code or '')[2:]
                    filtre=[
                        ('default_code','=', default_code),
                        ('company_id'  ,'=', 1),
                    ]
                    products=self.env['product.product'].sudo().search(filtre,limit=1)
                    for product in products:
                        vals={
                            'sequence'  : line.sequence,
                            'product_id': product.id,
                            'name'      : product.name,
                            'product_uom_qty': line.product_qty,
                            'order_id'       : order.id,
                        }
                        res=self.env['sale.order.line'].sudo().create(vals)
                        line.price_unit = res.price_unit


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    is_sale_order_line_id = fields.Many2one('sale.order.line', string=u'Ligne commande client', index=True)



#TODO : Revoir dans un deuxième temps

# class PurchaseOrderLine(models.Model):
#     _inherit = 'purchase.order.line'

#     def _prepare_compute_all_values(self):
#         self.ensure_one()
#         return {
#             'price_unit': self.price_unit,
#             'currency_id': self.order_id.currency_id,
#             'product_qty': self.qty_invoiced,
#             'product': self.product_id,
#             'partner': self.order_id.partner_id,
#         }

#     @api.depends('product_qty', 'price_unit', 'taxes_id', 'qty_invoiced')
#     def _compute_amount(self):
#         for line in self:
#             vals = line._prepare_compute_all_values()
#             taxes = line.taxes_id.compute_all(
#                 vals['price_unit'],
#                 vals['currency_id'],
#                 vals['product_qty'],
#                 vals['product'],
#                 vals['partner'])
#             line.update({
#                 'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
#                 'price_total': taxes['total_included'],
#                 'price_subtotal': taxes['total_excluded'],
#             })

#     echantillion = fields.Boolean(string='Echantillon')

#     @api.onchange('product_qty', 'product_uom')
#     def _onchange_quantity(self):
#         if not self.product_id:
#             return
#         params = {'order_id': self.order_id}
#         seller = self.product_id._select_seller(
#             partner_id=self.partner_id,
#             quantity=self.product_qty,
#             date=self.order_id.date_order and self.order_id.date_order.date(),
#             uom_id=self.product_uom,
#             params=params)


#         if not seller:
#             if self.product_id.seller_ids.filtered(lambda s: s.name.id == self.partner_id.id):
#                 self.price_unit = 0.0
#             return

#         price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price,
#                                                                              self.product_id.supplier_taxes_id,
#                                                                              self.taxes_id,
#                                                                              self.company_id) if seller else 0.0
#         if price_unit and seller and self.order_id.currency_id and seller.currency_id != self.order_id.currency_id:
#             price_unit = seller.currency_id._convert(
#                 price_unit, self.order_id.currency_id, self.order_id.company_id, self.date_order or fields.Date.today())

#         if seller and self.product_uom and seller.product_uom != self.product_uom:
#             price_unit = seller.product_uom._compute_price(price_unit, self.product_uom)

#         self.price_unit = price_unit


#     @api.onchange('product_id')
#     def onchange_product_id(self):
#         result = {}
#         if not self.product_id:
#             return result

#         # Reset date, price and quantity since _onchange_quantity will provide default values
#         self.date_planned = self.order_id.date_planned or datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
#         self.price_unit = self.product_qty = 0.0
#         self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
#         result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

#         product_lang = self.product_id.with_context(
#             lang=self.partner_id.lang,
#             partner_id=self.partner_id.id,
#         )
#         self.name = product_lang.display_name
#         if product_lang.description_purchase:
#             self.name += '\n' + product_lang.description_purchase

#         self._compute_tax_id()

#         self._suggest_quantity()
#         self._onchange_quantity()

#         return result

# class PurchaseOrder(models.Model):
#     _inherit = 'purchase.order'

#     @api.onchange('date_planned')
#     @api.multi
#     def _onchange_date_planned(self):
#         print('_onchange_date_planned')
#         self.action_set_date_planned()


#     date_enlevelment = fields.Date('Date Enlèvement')
#     delivery_adress = fields.Many2one('res.partner', 'Adresse Livraison')