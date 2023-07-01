# -*- coding: utf-8 -*-

from odoo import api, fields, models


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

    def is_archive_action(self):
        for obj in self:
            print(obj)

    def is_product_action(self):
        for obj in self:
            print(obj)

    def is_archive(self):
        for obj in self:
            test=False
            if not obj.product_tmpl_id.active:
                test=True
            obj.is_archive=test


    @api.depends('product_id')
    def _compute_is_prix_achat(self):
        for obj in self:
            prix_achat=0
            suppliers=self.env['product.supplierinfo'].search([('product_tmpl_id', '=', obj.product_tmpl_id.id)],limit=1)
            for line in suppliers:
                prix_achat=line.price
            taux=0
            if obj.fixed_price>0:
                taux = 100*(1-prix_achat/obj.fixed_price)

            alerte=False
            if taux<5:
                alerte=True
            obj.is_prix_achat = prix_achat
            obj.is_taux_marge = taux
            obj.is_alerte_marge = alerte


    is_archive      = fields.Boolean("Article archivé", compute=is_archive)
    is_prix_achat   = fields.Float(string="Prix d'achat"     , compute=_compute_is_prix_achat, digits=(14,4),)
    is_taux_marge   = fields.Float(string="Taux de marge (%)", compute=_compute_is_prix_achat, digits=(14,1),)
    is_alerte_marge = fields.Boolean("Alerte marge"          , compute=_compute_is_prix_achat, help="Alerte si le taux de marge est inférieur à 5%")

