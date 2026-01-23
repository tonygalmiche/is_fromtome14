# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import datetime, timedelta, date


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    is_pricelist_id = fields.Many2one('product.pricelist', string="Liste de prix d'origine")
    is_augmentation = fields.Float("Pourcentage d'augmentation à appliquer", digits=(16, 2))
    is_product_ids = fields.Many2many('product.template', 'is_pricelist_product_tmpl_rel', 'pricelist_id', 'product_tmpl_id', 'Articles à ajouter')
    is_existing_product_tmpl_ids = fields.One2many('product.template', compute='_compute_is_existing_product_tmpl_ids')

    @api.depends('item_ids', 'item_ids.product_tmpl_id')
    def _compute_is_existing_product_tmpl_ids(self):
        for obj in self:
            obj.is_existing_product_tmpl_ids = obj.item_ids.mapped('product_tmpl_id')

    def ajouter_articles_action(self):
        """Ajouter les articles sélectionnés dans la liste de prix à partir de la liste de prix d'origine"""
        for obj in self:
            if not obj.is_pricelist_id:
                continue
            # Récupérer les articles déjà présents dans la liste de prix
            existing_product_tmpl_ids = obj.item_ids.mapped('product_tmpl_id').ids
            
            for product_tmpl in obj.is_product_ids:
                # Vérifier si l'article n'existe pas déjà dans la liste de prix
                if product_tmpl.id not in existing_product_tmpl_ids:
                    # Rechercher la ligne correspondante dans la liste de prix d'origine
                    origin_items = self.env['product.pricelist.item'].search([
                        ('pricelist_id', '=', obj.is_pricelist_id.id),
                        ('product_tmpl_id', '=', product_tmpl.id),
                    ])
                    if origin_items:
                        # Copier les valeurs de la première ligne trouvée
                        origin_item = origin_items[0]
                        vals = {
                            'pricelist_id': obj.id,
                            'product_tmpl_id': product_tmpl.id,
                            'product_id': origin_item.product_id.id if origin_item.product_id else False,
                            'min_quantity': origin_item.min_quantity,
                            'fixed_price': origin_item.fixed_price,
                            'date_start': origin_item.date_start,
                            'date_end': origin_item.date_end,
                            'applied_on': origin_item.applied_on,
                            'base': origin_item.base,
                        }
                        self.env['product.pricelist.item'].create(vals)
            # Vider la sélection après l'ajout
            obj.is_product_ids = False

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

