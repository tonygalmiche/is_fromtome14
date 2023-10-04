# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime, timedelta, date


class is_preparation_transfert_entrepot_ligne(models.Model):
    _name = 'is.preparation.transfert.entrepot.ligne'
    _description = "Lignes préparation transfert entrepôt"
    _order='designation'

    preparation_id = fields.Many2one('is.analyse.rupture', 'Analyse', required=True, ondelete='cascade')
    product_id     = fields.Many2one('product.product', 'Article')
    designation    = fields.Char("Désignation" )
    default_code   = fields.Char("Référence interne")
    stock_mini     = fields.Float("Stock mini"  , digits='Product Unit of Measure')
    stock_ft       = fields.Float("Stock FT"    , digits='Product Unit of Measure')
    reception_ft   = fields.Float("Réception FT", digits='Product Unit of Measure')
    livraison_ft   = fields.Float("Livraison FT", digits='Product Unit of Measure')
    solde_ft       = fields.Float("Solde FT"    , digits='Product Unit of Measure')
    stock_lc       = fields.Float("Stock LC"    , digits='Product Unit of Measure')
    reception_lc   = fields.Float("Réception LC", digits='Product Unit of Measure')
    livraison_lc   = fields.Float("Livraison LC", digits='Product Unit of Measure')
    solde_lc       = fields.Float("Solde LC"    , digits='Product Unit of Measure')
    solde          = fields.Float("Solde total" , digits='Product Unit of Measure')


    def acceder_article_action(self):
            for obj in self:
                res= {
                    'name': 'Article',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_model': 'product.template',
                    'type': 'ir.actions.act_window',
                    'res_id':obj.product_id.product_tmpl_id.id,
                }
                return res

    def mouvement_stock_action(self):
            for obj in self:
                res= {
                    'name': 'Mouvements',
                    'view_mode': 'tree,form',
                    'view_type': 'form',
                    'res_model': 'stock.move.line',
                    'type': 'ir.actions.act_window',
                    'domain': [
                        ('product_id','=',obj.product_id.id),
                        ('state','not in',['done','cancel']),
                    ],
                    'views': [[self.env.ref('is_fromtome14.is_view_move_line_tree').id, 'list'], [False, 'form']],
                }
                return res


class is_preparation_transfert_entrepot(models.Model):
    _name = 'is.preparation.transfert.entrepot'
    _description = "Préparation transfert entrepôt"
    _order='date desc'
    _rec_name = 'date'


    date        = fields.Date("Date", required=True, default=lambda *a: fields.Date.today(), readonly=True)
    date_debut  = fields.Date("Date de début", required=True, help="Date de début des mouvements en attente")
    date_fin    = fields.Date("Date de fin"  , required=True, help="Date de gin des mouvements en attente")
    commentaire = fields.Text("Commentaire")
    ligne_ids   = fields.One2many('is.preparation.transfert.entrepot.ligne', 'preparation_id', 'Lignes')


    def voir_lignes_action(self):
        for obj in self:
            res= {
                'name': 'Lignes',
                'view_mode': 'tree',
                'view_type': 'form',
                'res_model': 'is.preparation.transfert.entrepot.ligne',
                'type': 'ir.actions.act_window',
                'domain': [
                    ('preparation_id','=',obj.id),
                ],
                'limit': 2000,
            }
            return res


    def actualiser_lignes_action(self):
        warehouses = self.env['stock.warehouse'].search([])
        for obj in self:
            obj.ligne_ids.unlink()
            filtre=[]
            products=self.env['product.product'].search(filtre, order="name")
            for product in products:
                solde_ft = solde_lc = solde = 0
                #** Recherche du stock par entrepôt ***************************
                stock_ft=0
                stock_lc=0
                for warehouse in warehouses:
                    location_id =  warehouse.lot_stock_id.id
                    stock = 0
                    quants = self.env['stock.quant'].search([('product_id','=',product.id),('location_id','=',location_id)])
                    for quant in quants:
                        stock+=quant.quantity
                    if warehouse.code=='LC':
                        stock_lc = stock
                    if warehouse.code=='FT':
                        stock_ft = stock
                #**************************************************************

                #** Recherche des receptions par entrepôt *********************
                reception_ft=0
                reception_lc=0
                for warehouse in warehouses:
                    location_id =  warehouse.lot_stock_id.id
                    filtre=[
                        ('location_dest_id', '=', location_id),
                        ('state'             , 'not in', ['done','cancel']),
                        ('product_id','=', product.id),
                        ('date_deadline', '>='   , obj.date_debut),
                        ('date_deadline', '<='   , obj.date_fin),
                    ]
                    moves=self.env['stock.move'].search(filtre)
                    for move in moves:
                        if warehouse.code=='LC':
                            reception_lc+=move.product_qty
                        if warehouse.code=='FT':
                            reception_ft+=move.product_qty
                #**************************************************************

                #** Recherche des livraisons par entrepôt *********************
                livraison_ft=0
                livraison_lc=0
                for warehouse in warehouses:
                    location_id =  warehouse.lot_stock_id.id
                    filtre=[
                        ('location_id', '='     , location_id),
                        ('state'      , 'not in', ['done','cancel']),
                        ('product_id' , '='     , product.id),
                        ('date_deadline', '>='   , obj.date_debut),
                        ('date_deadline', '<='   , obj.date_fin),
                    ]
                    moves=self.env['stock.move'].search(filtre)
                    for move in moves:
                        if warehouse.code=='LC':
                            livraison_lc+=move.product_qty
                        if warehouse.code=='FT':
                            livraison_ft+=move.product_qty
                #**************************************************************

                #** Solde *****************************************************
                solde_ft = stock_ft + reception_ft - livraison_ft
                solde_lc = stock_lc + reception_lc - livraison_lc
                solde = solde_ft + solde_lc
                #**************************************************************

                if product.is_stock_mini or stock_ft or stock_lc or livraison_ft or livraison_lc or reception_ft or reception_lc:
                    vals={
                        "preparation_id": obj.id,
                        "product_id"    : product.id,
                        "designation"   : product.name,
                        "default_code"  : product.default_code,
                        "stock_mini"    : product.is_stock_mini,
                        "stock_ft"      : stock_ft,
                        "stock_lc"      : stock_lc,
                        "reception_ft"  : reception_ft,
                        "reception_lc"  : reception_lc,
                        "livraison_ft"  : livraison_ft,
                        "livraison_lc"  : livraison_lc,
                        "solde_ft"      : solde_ft,
                        "solde_lc"      : solde_lc,
                        "solde"         : solde,
                    }
                    self.env['is.preparation.transfert.entrepot.ligne'].create(vals)
        return self.voir_lignes_action()