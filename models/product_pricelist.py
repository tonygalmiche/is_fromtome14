# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import datetime, timedelta, date


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    is_augmentation = fields.Float("Pourcentage d'augmentation à appliquer", digits=(16, 2))
 

    def appliquer_augmentation_action(self):
        for obj in self:
            for item in obj.item_ids:
                price = item.fixed_price + item.fixed_price*obj.is_augmentation/100
                item.fixed_price = price
            obj.is_augmentation=0


    def lignes_action(self):
        for obj in self:
            print(obj)


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    def is_alerte_action(self):
        for obj in self:
            print(obj)

    # def is_product_action(self):
    #     for obj in self:
    #         print(obj)

    # def is_archive(self):
    #     for obj in self:
    #         test=False
    #         if not obj.product_tmpl_id.active:
    #             test=True
    #         obj.is_archive=test


    @api.depends('product_id')
    def _compute_is_alerte(self):
        today = date.today()
        product_ids={}
        if len(self)>0:
            for line in self[0].pricelist_id.item_ids:
                product_tmpl_id = line.product_tmpl_id.id
                if product_tmpl_id not in product_ids:
                    product_ids[product_tmpl_id]=0
                product_ids[product_tmpl_id]+=1
        for obj in self:
            alerte=[]
            if not obj.product_tmpl_id.active:
                alerte.append("Article désactivé")
            prix_achat=0
            filtre = [
                ('product_tmpl_id', '=', obj.product_tmpl_id.id),
                ('date_start', '<=', today),
                ('date_end'  , '>=', today),
            ]
            suppliers=self.env['product.supplierinfo'].search(filtre,limit=1)
            for line in suppliers:
                prix_achat=line.price
            taux=0
            if obj.fixed_price>0:
                taux = 100*(1-prix_achat/obj.fixed_price)
            if taux<5:
                alerte.append("Marge inférieure à 5%")
            if obj.product_tmpl_id.id in product_ids and product_ids[obj.product_tmpl_id.id ]>1:
                alerte.append("Il y a %s lignes avec cet article"%(product_ids[obj.product_tmpl_id.id ]))
            if len(alerte)>0:
                alerte = ", ".join(alerte)
            else:
                alerte=False


            obj.is_prix_achat = prix_achat
            obj.is_taux_marge = taux
            obj.is_alerte = alerte

    #is_archive    = fields.Boolean("Article archivé"       , compute=is_archive)
    is_prix_achat = fields.Float(string="Prix d'achat"     , compute=_compute_is_alerte, digits=(14,4),)
    is_taux_marge = fields.Float(string="Taux de marge (%)", compute=_compute_is_alerte, digits=(14,1),)
    is_alerte     = fields.Text("Alerte"                   , compute=_compute_is_alerte) # help="Alerte si le taux de marge est inférieur à 5%"

