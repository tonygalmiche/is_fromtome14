# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"


    @api.depends('partner_id','is_fromtome_order_id')
    def _compute_is_fromtome_order_vsb(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            vsb=True
            if self.env.user.company_id.partner_id!=obj.partner_id:
                vsb=False
            if obj.is_fromtome_order_id:
                vsb=False
            obj.is_fromtome_order_vsb=vsb



    @api.depends('order_line.date_planned')
    def _compute_date_planned(self):
        for order in self:
            print(order)


    is_commande_soldee    = fields.Boolean(string='Commande soldée', default=False, copy=False, help=u"Cocher cette case pour indiquer qu'aucune nouvelle livraison n'est prévue sur celle-ci")
    is_fromtome_order_id  = fields.Many2one('sale.order', 'Commande Fromtome', copy=False,readonly=True)
    is_fromtome_order_vsb = fields.Boolean(string='Créer commande dans Fromtome vsb', compute='_compute_is_fromtome_order_vsb')



    def commande_fournisseur_entierement_facturee_action_server(self):
        for obj in self:
            obj.invoice_status = "invoiced"


    def initialisation_etat_facturee_fournisseur_action_server(self):
        for obj in self:
            obj._get_invoiced()
 



    def commande_soldee_action_server(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            solde=False
            if obj.state not in ["draft","sent","to_approve"]:
                solde=True
                filtre=[
                    ('purchase_id','=',obj.id),
                    ('state','not in',['done','cancel']),
                ]

                pickings = self.env['stock.picking'].search(filtre)
                for picking in pickings:
                    solde=False
            obj.is_commande_soldee=solde


    def creer_commande_fromtome_action(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            vals={
                #'company_id': 1,
                'partner_id': obj.partner_id.id,
                'user_id'   : uid,
            }
            order=self.env['sale.order'].create(vals)
            obj.is_fromtome_order_id=order.id
            if order:
                for line in obj.order_line:
                    vals={
                        'sequence'  : line.sequence,
                        'product_id': line.product_id.id,
                        'name'      : line.product_id.name,
                        'product_uom_qty': line.product_qty,
                        'order_id'       : order.id,
                    }
                    res=self.env['sale.order.line'].create(vals)
                    line.price_unit = res.price_unit

                    # default_code =  (line.product_id.default_code or '')[2:]
                    # filtre=[
                    #     ('default_code','=', default_code),
                    #     ('company_id'  ,'=', 1),
                    # ]
                    # products=self.env['product.product'].search(filtre,limit=1)
                    # for product in products:
                    #     vals={
                    #         'sequence'  : line.sequence,
                    #         'product_id': product.id,
                    #         'name'      : product.name,
                    #         'product_uom_qty': line.product_qty,
                    #         'order_id'       : order.id,
                    #     }
                    #     res=self.env['sale.order.line'].create(vals)
                    #     line.price_unit = res.price_unit


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.depends('product_id','product_qty')
    def _compute_is_nb_pieces_par_colis(self):
        for obj in self:
            nb        = obj.product_id.is_nb_pieces_par_colis
            poids_net = obj.product_id.is_poids_net_colis
            unite     = obj.product_uom.category_id.name
            obj.is_nb_pieces_par_colis = nb
            nb_colis  = 0
            if unite=="Poids":
                if poids_net>0:
                    nb_colis = obj.product_qty/poids_net
            else:
                if nb>0:
                    nb_colis = obj.product_qty / nb
            obj.is_nb_colis = nb_colis
            obj.is_poids_net = nb_colis * poids_net


    @api.depends('product_id','is_nb_colis','price_unit')
    def _compute_is_alerte(self):
        for obj in self:
            alerte=[]
            if obj.is_nb_colis!=round(obj.is_nb_colis):
                alerte.append("Colis incomplet")
            if obj.is_nb_colis==0:
                alerte.append("Colis à 0")
            if obj.price_unit==0:
                alerte.append("Prix à 0")
            obj.is_alerte="\n".join(alerte)


    is_sale_order_line_id  = fields.Many2one('sale.order.line', string=u'Ligne commande client', index=True)
    is_nb_pieces_par_colis = fields.Integer(string='PCB', compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_nb_colis            = fields.Float(string='Nb Colis', digits=(14,2) , compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_poids_net           = fields.Float(string='Poids net', digits='Stock Weight', compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True, help="Poids net total (Kg)")
    is_alerte              = fields.Text(string='Alerte', compute='_compute_is_alerte')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # @api.onchange('date_planned')
    # @api.multi
    # def _onchange_date_planned(self):
    #     self.action_set_date_planned()

    is_date_enlevement      = fields.Date('Date Enlèvement')                          # était date_enlevelment
    is_adresse_livraison_id = fields.Many2one('res.partner', 'Adresse Livraison', default=lambda self: self.env.user.company_id.partner_id.id)


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
