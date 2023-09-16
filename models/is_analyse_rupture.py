# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime, timedelta, date


class IsAnalyseRuptureLigne(models.Model):
    _name = 'is.analyse.rupture.ligne'
    _description = "Lignes Analyse rupture"
    _order='product_id'

    analyse_id     = fields.Many2one('is.analyse.rupture', 'Analyse', required=True, ondelete='cascade')
    product_id     = fields.Many2one('product.product', 'Article')
    order_id       = fields.Many2one('sale.order', 'Commande')
    line_id        = fields.Many2one('sale.order.line', 'Ligne de commande')
    partner_id     = fields.Many2one('res.partner', 'Client')
    enseigne_id    = fields.Many2one('is.enseigne.commerciale', 'Enseigne')
    demande_client = fields.Float("Demande client", digits='Product Unit of Measure')
    demande_totale = fields.Float("Demande totale", digits='Product Unit of Measure')
    stock          = fields.Float("Stock actuel"  , digits='Product Unit of Measure')
    manque         = fields.Float("Manque"        , digits='Product Unit of Measure')


class IsAnalyseRupture(models.Model):
    _name = 'is.analyse.rupture'
    _description = "Analyse rupture"
    _order='date desc'
    _rec_name = 'date'


    date                = fields.Date("Date"                      , required=True, default=lambda *a: fields.Date.today())
    date_livraison_mini = fields.Date("Date livraison client mini", required=True, default=lambda *a: fields.Date.today())
    date_livraison_maxi = fields.Date("Date livraison client maxi", required=True)
    commentaire         = fields.Text("Commentaire")
    ligne_ids           = fields.One2many('is.analyse.rupture.ligne', 'analyse_id', 'Lignes')


    def generer_lignes_action(self):
        for obj in self:
            print(obj)
            filtre=[
                ('is_commande_soldee', '=', False),
                ('state'             , '=', 'sale'),
                ('is_date_livraison','>=', obj.date_livraison_mini),
                ('is_date_livraison','<=', obj.date_livraison_maxi),
            ]
            orders=self.env['sale.order'].search(filtre, order="id desc")
            products={}
            for order in orders:
                for line in order.order_line:
                    product = line.product_id
                    if product not in products:
                        products[product]=0
                    products[product]+=line.qty_to_deliver
            obj.ligne_ids.unlink()
            for order in orders:
                for line in order.order_line:
                    product = line.product_id
                    demande = products[product]
                    stock   = product.qty_available
                    manque  = stock - demande
                    if manque<0:
                        vals={
                            "analyse_id" : obj.id,
                            "product_id" : product.id,
                            "order_id"   : order.id,
                            "line_id"    : line.id,
                            "partner_id" : order.partner_id.id,
                            "enseigne_id": order.partner_id.is_enseigne_id.id,
                            "demande_client": line.qty_to_deliver,
                            "demande_totale": demande,
                            "stock"      : stock,
                            "manque"     : -manque,
                        }
                        self.env['is.analyse.rupture.ligne'].create(vals)
            res= {
                'name': 'Lignes',
                'view_mode': 'tree',
                'view_type': 'form',
                'res_model': 'is.analyse.rupture.ligne',
                'type': 'ir.actions.act_window',
                'domain': [
                    ('analyse_id','=',obj.id),
                ],
                'limit': 2000,
            }
            return res
