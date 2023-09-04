# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime, timedelta, date


class IsSuiviCommandeHebdoLigne(models.Model):
    _name = 'is.suivi.commande.hebdo.ligne'
    _description = "Lignes Suivi Commande Hebdo"
    _order='partner_id'

    suivi_id    = fields.Many2one('is.suivi.commande.hebdo', 'Suivi', required=True, ondelete='cascade')
    partner_id  = fields.Many2one('res.partner', 'Client', required=True)
    heure_appel = fields.Char(string="Heure d'appel")
    phone       = fields.Char(string="Numéro")
    habitude_commande = fields.Selection([
        ('telephone', 'Téléphone'),
        ('mail'     , 'Mail'),
    ], 'Habitude commande')
    transporteur_id = fields.Many2one('is.transporteur', 'Transporteur')
    order_id  = fields.Many2one('sale.order', 'Commande')


class IsSuiviCommandeHebdo(models.Model):
    _name = 'is.suivi.commande.hebdo'
    _description = "Suivi Commande Hebdo"
    _order='date desc'
    _rec_name = 'date'


    date        = fields.Date("Date", default=lambda *a: fields.Date.today(), required=True)
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
                    ('date_order', '>=', date_debut),
                    ('date_order', '<=', date_fin),
                ]
                orders=self.env['sale.order'].search(filtre, order="id desc", limit=1)
                order_id=False
                for order in orders:
                    order_id = order.id
                vals={
                    "suivi_id"   : obj.id,
                    "partner_id" : partner.id,
                    "heure_appel": partner.is_heure_appel,
                    "phone"      : partner.mobile or partner.phone,
                    "habitude_commande": partner.is_habitude_commande,
                    "transporteur_id"  : partner.is_transporteur_id.id,
                    "order_id"         : order_id,
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

