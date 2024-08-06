# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.addons.is_fromtome14.models.res_partner import HABITUDE_COMMANDE
from datetime import datetime, timedelta, date


class IsSuiviCommandeHebdoLigne(models.Model):
    _name = 'is.suivi.commande.hebdo.ligne'
    _description = "Lignes Suivi Commande Hebdo"
    _order='partner_id'

    suivi_id    = fields.Many2one('is.suivi.commande.hebdo', 'Suivi', required=True, ondelete='cascade')
    partner_id  = fields.Many2one('res.partner', 'Client', required=True)
    heure_appel = fields.Char(string="Heure d'appel")
    phone       = fields.Char(string="Numéro")
    habitude_commande = fields.Selection(HABITUDE_COMMANDE, 'Habitude commande')
    transporteur_id = fields.Many2one('is.transporteur', 'Transporteur')
    order_id  = fields.Many2one('sale.order', 'Commande')
    nb_colis  = fields.Float(string="Nb colis commande")
    nb_cde_transporteur = fields.Integer(string="Nb cde transporteur", compute="_compute_nb_cde_transporteur")
    picking_id  = fields.Many2one('stock.picking', 'Livraison')
    nb_colis_picking = fields.Float(string="Nb colis livraison")
    ecart_colis      = fields.Float(string="Ecart colis")
    poids_picking    = fields.Float(string="Poids", help="Poids réél de la livraison")


    @api.depends('transporteur_id','order_id')
    def _compute_nb_cde_transporteur(self):
        for obj in self:
            filtre=[
                ('order_id'       , '!=', False),
                ('suivi_id'       , '=' , obj.suivi_id.id),
                ('transporteur_id', '=' , obj.transporteur_id.id),
            ]
            orders=self.env['is.suivi.commande.hebdo.ligne'].search(filtre)
            nb=len(orders)
            obj.nb_cde_transporteur = nb


class IsSuiviCommandeHebdo(models.Model):
    _name = 'is.suivi.commande.hebdo'
    _description = "Suivi Commande Hebdo"
    _order='date desc'
    _rec_name = 'date'


    date        = fields.Date("Date livraison client", default=lambda *a: fields.Date.today(), required=True)
    enseigne_id = fields.Many2one('is.enseigne.commerciale', 'Enseigne', required=True)
    commentaire = fields.Text("Commentaire")
    ligne_ids   = fields.One2many('is.suivi.commande.hebdo.ligne', 'suivi_id', 'Lignes')


    def generer_lignes_action(self):
        for obj in self:
            filtre=[
                ('is_enseigne_id', '=', obj.enseigne_id.id),
                ('is_company'    , '=', True),
                ('is_customer'   , '=', True),
            ]
            partners=self.env['res.partner'].search(filtre)
            obj.ligne_ids.unlink()
            for partner in partners:
                date_debut = obj.date
                date_fin   = obj.date+timedelta(days=6)
                filtre=[
                    ('partner_id', '=', partner.id),
                    ('state'     , '=', 'sale'),
                    ('is_date_livraison', '>=', date_debut),
                    ('is_date_livraison', '<=', date_fin),
                ]
                orders=self.env['sale.order'].search(filtre, order="id desc", limit=1)
                order_id=False
                picking_id=False
                nb_colis=0
                nb_colis_picking=0
                poids=0
                for order in orders:
                    order_id = order.id
                    for line in order.order_line:
                        nb_colis+=line.is_nb_colis


                    #** Recherche du picking **********************************
                    filtre=[
                        ('sale_id', '=', order.id),
                        ('state'     , '=', 'done'),
                    ]
                    pickings=self.env['stock.picking'].search(filtre, order="id")
                    for picking in pickings:
                        picking_id = picking.id
                        for line in picking.move_ids_without_package:
                            nb_colis_picking+=line.is_nb_colis
                            poids+=line.is_poids_net_reel
                    #**********************************************************

                vals={
                    "suivi_id"   : obj.id,
                    "partner_id" : partner.id,
                    "heure_appel": partner.is_heure_appel,
                    "phone"      : partner.mobile or partner.phone,
                    "habitude_commande": partner.is_habitude_commande,
                    "transporteur_id"  : partner.is_transporteur_id.id,
                    "order_id"         : order_id,
                    "nb_colis"         : nb_colis,
                    "picking_id"       : picking_id,
                    "nb_colis_picking" : nb_colis_picking,
                    "ecart_colis"      : nb_colis_picking-nb_colis,
                    "poids_picking"    : poids,
                }
                self.env['is.suivi.commande.hebdo.ligne'].create(vals)
            
            res= {
                'name': 'Lignes',
                'view_mode': 'tree',
                'view_type': 'form',
                'res_model': 'is.suivi.commande.hebdo.ligne',
                'type': 'ir.actions.act_window',
                'domain': [
                    ('suivi_id','=',obj.id),
                ],
                'limit': 1000,
            }
            return res




    # def voir_lignes_action(self):
    #     for obj in self:
    #         res= {
    #             'name': 'Lignes',
    #             'view_mode': 'tree',
    #             'view_type': 'form',
    #             'res_model': 'is.suivi.commande.hebdo.ligne',
    #             'type': 'ir.actions.act_window',
    #             'domain': [
    #                 ('suivi_id','=',obj.id),
    #             ],
    #         }
    #         return res

