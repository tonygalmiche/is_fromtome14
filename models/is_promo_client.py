# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)


class IsPromoClient(models.Model):
    _name = 'is.promo.client'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Promo client"
    _order = 'name desc'

    name              = fields.Char("N°Promo", readonly=True)
    partner_id        = fields.Many2one('res.partner', 'Client', required=True)
    date_debut_promo  = fields.Date("Date début promo"         , required=True)
    date_fin_promo    = fields.Date("Date fin promo"           , required=True)
    pourcent_promo_a_repercuter = fields.Float("Pourcentage promo fournisseur à répercuter (%)", digits=(14,2), compute='_compute_taux_remise', readonly=True, store=True)
    ligne_ids         = fields.One2many('is.promo.client.ligne', 'promo_id', 'Lignes', copy=False)

    @api.depends('partner_id')
    def _compute_taux_remise(self):
        for obj in self:
            obj.pourcent_promo_a_repercuter  = obj.partner_id.is_pourcent_promo_a_repercuter


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.promo.client')
        res = super(IsPromoClient, self).create(vals)
        return res


    def actualiser_promo_action(self):
        now = datetime.now().date()
        for obj in self:
            obj.ligne_ids.unlink()
            filtre=[
                ('date_debut_promo', '>=', obj.date_debut_promo),
                ('date_debut_promo', '<=', obj.date_fin_promo),
            ]
            lines = self.env['is.promo.fournisseur'].search(filtre, order="date_debut_promo")
            for promo in lines:
                remise_client = round(promo.taux_remise * obj.pourcent_promo_a_repercuter/100)
                if remise_client>=3:
                    for ligne in promo.ligne_ids:
                        vals={
                            'promo_id'            : obj.id,
                            'promo_fournisseur_id': promo.id,
                            'product_id'          : ligne.product_id.id,
                            'remise_fournisseur'  : ligne.taux_remise,
                            'remise_client'       : remise_client,
                        }
                        self.env['is.promo.client.ligne'].create(vals)


class IsPromoClientLigne(models.Model):
    _name = 'is.promo.client.ligne'
    _description = "Lignes promo client"
    _rec_name = 'promo_id'


    promo_id             = fields.Many2one('is.promo.client', 'Promo client', required=True, ondelete='cascade')
    product_id           = fields.Many2one('product.product', 'Article', required=True)
    promo_fournisseur_id = fields.Many2one('is.promo.fournisseur', 'Promo fournisseur', required=True)
    partner_id           = fields.Many2one(related="promo_fournisseur_id.partner_id")
    date_debut_promo     = fields.Date(related="promo_fournisseur_id.date_debut_promo")
    date_fin_promo       = fields.Date(related="promo_fournisseur_id.date_fin_promo")
    remise_fournisseur   = fields.Float("Remise fournisseur (%)", digits=(14,2))
    remise_client        = fields.Float("Remise client (%)"     , digits=(14,2))

