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

    def is_archive(self):
        for obj in self:
            test=False
            if not obj.product_tmpl_id.active:
                test=True
            obj.is_archive=test

    is_archive = fields.Boolean("Article archivé", compute=is_archive)
 
