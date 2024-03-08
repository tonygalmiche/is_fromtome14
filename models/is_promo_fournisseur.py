# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)


class IsPromoFournisseur(models.Model):
    _name = 'is.promo.fournisseur'
    _description = "Promo fournisseur"
    _order = 'name desc'

    name              = fields.Char("N°Promo", readonly=True)
    partner_id        = fields.Many2one('res.partner', 'Fournisseur', required=True)
    date_debut_promo  = fields.Date("Date début promo"              , required=True)
    date_fin_promo    = fields.Date("Date fin promo"                , required=True)
    intitule          = fields.Char('Intitulé de la promo')
    taux_remise       = fields.Float("Taux de remise (%)"           , required=True, digits=(14,2))
    product_ids       = fields.Many2many('product.product', 'is_promo_fournisseur_product_rel', 'promo_id', 'product_id', 'Articles à ajouter')
    ligne_ids         = fields.One2many('is.promo.fournisseur.ligne', 'promo_id', 'Lignes', copy=True)


    @api.constrains('taux_remise')
    def _constrains_taux_remise(self):
        for obj in self:
            if obj.taux_remise <= 0:
                raise ValidationError("Le taux de remise doit-être supérieur à 0")


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.promo.fournisseur')
        res = super(IsPromoFournisseur, self).create(vals)
        res.remove_doublons()
        return res


    def write(self, vals):
        res = super(IsPromoFournisseur, self).write(vals)
        self.remove_doublons()
        return res


    def unlink(self):
        self.ligne_ids.unlink()
        res = super(IsPromoFournisseur, self).unlink()
        return res


    def remove_doublons(self):
        for obj in self:
            product_ids=[]
            for l in obj.ligne_ids:
                if l.product_id not in product_ids:
                    product_ids.append(l.product_id)
                else:
                    l.unlink()


    def ajouter_articles_action(self):
        for obj in self:
            product_ids=[]
            for l in obj.ligne_ids:
                if l.product_id not in product_ids:
                    product_ids.append(l.product_id)
            new_product_ids=[]
            for p in obj.product_ids:
                if p not in product_ids:
                    new_product_ids.append(p._origin)
            for p in new_product_ids:
                vals={
                    'promo_id'   : obj._origin.id,
                    'product_id' : p.id,
                    'taux_remise': obj.taux_remise
                }
                self.env['is.promo.fournisseur.ligne'].create(vals)
            obj.product_ids=False


    # def appliquer_promo_action(self):
    #     for obj in self:
    #         now = datetime.now().date()
    #         for l in obj.ligne_ids:
    #             #** Suppressions des promos ***********************************
    #             filtre=[
    #                 ('promo_id', '=', l.id),
    #             ]
    #             self.env['product.supplierdiscount'].search(filtre).unlink()
    #             #**************************************************************

    #             #** Ajout des promos en fonction de la date du jour ***********
    #             if now>=obj.date_debut_promo and now<=obj.date_fin_promo:
    #                 filtre=[
    #                     ('product_tmpl_id', '=', l.product_id.product_tmpl_id.id),
    #                     ('date_start', '<=', now),
    #                     ('date_end', '>=', now),
    #                 ]
    #                 lines=self.env['product.supplierinfo'].search(filtre)
    #                 for line in lines:
    #                     _logger.info("appliquer_promo_action : %s => [%s]%s"%(obj.name, l.product_id.default_code,l.product_id.name))
    #                     vals={
    #                         'supplier_info_id': line.id,
    #                         'promo_id'        : l.id,
    #                         'name'            : l.taux_remise,
    #                     }
    #                     self.env['product.supplierdiscount'].create(vals)
    #             #**************************************************************


    def desactiver_promo_action(self):
        for obj in self:
            for l in obj.ligne_ids:
                filtre=[
                    ('promo_id', '=', l.id),
                ]
                lines = self.env['product.supplierdiscount'].search(filtre)
                lines.unlink()
    

    # def update_promo_fournisseur_ir_cron(self):
    #     self.env['is.promo.fournisseur'].search([]).appliquer_promo_action()


class IsPromoFournisseurLigne(models.Model):
    _name = 'is.promo.fournisseur.ligne'
    _description = "Lignes promo fournisseur"
    _rec_name = 'promo_id'


    promo_id    = fields.Many2one('is.promo.fournisseur', 'Promo fournisseur', required=True, ondelete='cascade')
    product_id  = fields.Many2one('product.product', 'Article', required=True)
    taux_remise = fields.Float("Taux de remise (%)"           , required=True, digits=(14,2))


    @api.onchange('product_id')
    def onchange_product_id(self):
        for obj in self:
            obj.taux_remise = obj.promo_id.taux_remise


    @api.constrains('taux_remise')
    def _constrains_taux_remise(self):
        for obj in self:
            if obj.taux_remise <= 0:
                raise ValidationError("Le taux de remise doit-être supérieur à 0 (%s)"%obj.product_id.name)


    def unlink(self):
        for obj in self:
            filtre=[
                ('promo_id', '=', obj.id),
            ]
            self.env['product.supplierdiscount'].search(filtre).unlink()
        res = super(IsPromoFournisseurLigne, self).unlink()
        return res


