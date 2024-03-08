
# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons import decimal_precision as dp
from odoo.exceptions import Warning
from datetime import datetime, timedelta, date


class SupplierDiscount(models.Model):
    _name = "product.supplierdiscount"
    _description = "SupplierDiscount"

    promo_id         = fields.Many2one('is.promo.fournisseur.ligne', 'Promo', index=True)
    name             = fields.Float('Discount')
    supplier_info_id = fields.Many2one('product.supplierinfo')
    date_start       = fields.Date('Start Date', help="Start date for this vendor price", related='supplier_info_id.date_start')
    date_end         = fields.Date('End Date'  , help="End date for this vendor price"  , related='supplier_info_id.date_end')
    delay            = fields.Integer(
        'Delivery Lead Time', default=0, required=True,
        help="Lead time in days between the confirmation of the purchase order and the receipt of the products in your warehouse. Used by the scheduler for automatic computation of the purchase order planning.")


class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    date_start   = fields.Date('Start Date', help="Start date for this vendor price", required=True)
    date_end     = fields.Date('End Date', help="End date for this vendor price", required=True)
    prix_brut    = fields.Float(string="Prix Brut", digits=(14,4))
    discount_ids = fields.One2many('product.supplierdiscount','supplier_info_id',string='Taux de remises', copy=True)
    price        = fields.Float(
        'Price', default=0.0, digits=dp.get_precision('Product Price'),
        required=True, help="The price to purchase a product", compute="compute_prix_net", store=True
    )
    discount = fields.Float(string="Remise (%)", digits="Discount")


    @api.depends('discount_ids','discount_ids.name','prix_brut')
    def compute_prix_net(self):
        for s in self:
            remise  = 0
            price = s.prix_brut
            if len(s.discount_ids)>0:
                for r in s.discount_ids:
                    price= price * (1- r.name/100)
            s.price = price


    def dupliquer_action(self):
        for obj in self:
            if obj.name.is_date_debut_nouveau_tarif==False or obj.name.is_date_debut_nouveau_tarif==False:
                raise Warning("Il faut renseigner les champs 'Date début nouveau tarif' et 'Date fin nouveau tarif' du fournisseur pour utiliser cette fonction")
            copy = obj.copy()
            copy.date_start = obj.name.is_date_debut_nouveau_tarif
            copy.date_end   = obj.name.is_date_fin_nouveau_tarif
            obj.date_end = obj.name.is_date_debut_nouveau_tarif-timedelta(days=1)


    @api.onchange("name")
    def onchange_name(self):
        """ Apply the default supplier discount of the selected supplier """
        for supplierinfo in self.filtered("name"):
            supplierinfo.discount = supplierinfo.name.default_supplierinfo_discount


    @api.model
    def _get_po_to_supplierinfo_synced_fields(self):
        """Overwrite this method for adding other fields to be synchronized
        with product.supplierinfo.
        """
        return ["discount"]


    @api.model_create_multi
    def create(self, vals_list):
        """Insert discount (or others) from context from purchase.order's
        _add_supplier_to_product method"""
        for vals in vals_list:
            product_tmpl_id = vals["product_tmpl_id"]
            po_line_map = self.env.context.get("po_line_map", {})
            if product_tmpl_id in po_line_map:
                po_line = po_line_map[product_tmpl_id]
                for field in self._get_po_to_supplierinfo_synced_fields():
                    if not vals.get(field):
                        vals[field] = po_line[field]
        return super().create(vals_list)
