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
    enseigne_id       = fields.Many2one(related='partner_id.is_enseigne_id')
    pricelist_id      = fields.Many2one(related="partner_id.property_product_pricelist", string="Liste de prix")
    pourcent_promo_a_repercuter = fields.Float("Pourcentage promo fournisseur à répercuter (%)", digits=(14,2), compute='_compute_taux_remise', readonly=True, store=True)
    date_debut_promo  = fields.Date("Date début promo"         , required=True)
    date_fin_promo    = fields.Date("Date fin promo"           , required=True)
    ligne_ids         = fields.One2many('is.promo.client.ligne', 'promo_id', 'Lignes', copy=False)
    nb_lignes         = fields.Char("Nb lignes", compute='_compute_nb_lignes')
    afficher_image    = fields.Boolean("Afficher image", default=True)
    afficher_prix     = fields.Boolean("Afficher prix" , default=True)


    @api.depends('ligne_ids')
    def _compute_nb_lignes(self):
        for obj in self:
            nb_lignes = 0
            if obj.ligne_ids:
                nb_lignes = len(obj.ligne_ids)
            obj.nb_lignes = nb_lignes


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
                        # Méthode utilisée dans is.listing.prix.client
                        # items = self.env['product.pricelist.item'].search([
                        #        ('pricelist_id','=',obj.pricelist_id.id),('product_tmpl_id','=',ligne.product_id.product_tmpl_id.id)
                        #    ], order="date_start desc", limit=1)
                        # prix_non_remise=0
                        # for item in items:
                        #    #price       = item.price
                        #    prix_non_remise = item.fixed_price
                        # Méthode standard d'Odoo
                        prix_non_remise = obj.pricelist_id._compute_price_rule(
                            [(ligne.product_id, 1, obj.partner_id)],
                            promo.date_debut_promo,
                            ligne.product_id.uom_id.id
                        )[ligne.product_id.id][0]
                        if prix_non_remise>0.1 and prix_non_remise<1000:
                            prix_remise = prix_non_remise - remise_client*prix_non_remise/100
                            vals={
                                'promo_id'            : obj.id,
                                'promo_fournisseur_id': promo.id,
                                'product_id'          : ligne.product_id.id,
                                'remise_fournisseur'  : ligne.taux_remise,
                                'remise_client'       : remise_client,
                                'prix_non_remise'     : prix_non_remise,
                                'prix_remise'         : prix_remise,
                            }
                            self.env['is.promo.client.ligne'].create(vals)


    def get_products(self):
        promos=[]
        for product in self.ligne_ids:
            promo = product.promo_fournisseur_id
            if promo not in promos:
                promos.append(promo)
        res={}
        for promo in promos:
            filtre=[
                ('promo_id','=',self.id),
                ('promo_fournisseur_id','=',promo.id),
            ]
            lignes = self.env['is.promo.client.ligne'].search(filtre)
            for ligne in lignes:
                if promo not in res:
                    res[promo]=[]
                res[promo].append(ligne)
        return res


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
    prix_non_remise      = fields.Float('Prix non remisé', digits='Product Price', default=0.0)
    prix_remise          = fields.Float('Prix remisé'    , digits='Product Price', default=0.0)

