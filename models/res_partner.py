# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    partner_id = fields.Many2one('res.partner','Client')


class IsEnseigneCommerciale(models.Model):
    _name = 'is.enseigne.commerciale'
    _description = "Enseigne commerciale"

    name = fields.Many2one('res.partner', 'Enseigne commerciale', required=True)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_date_reception           = fields.Date(string='Dernière date de réception saisie')
    is_product_supplierinfo_ids = fields.One2many('product.supplierinfo', 'name', 'Liste de prix')
    is_gln                      = fields.Char(string='GLN Client')
    is_iln                      = fields.Char(string='ILN Client')
    is_enseigne_id              = fields.Many2one('is.enseigne.commerciale', 'Enseigne', help="Enseigne commerciale")
    is_customer                 = fields.Boolean("Est un Client")
    is_supplier                 = fields.Boolean("Est un Fournisseur")
    is_frequence_facturation    = fields.Selection(string='Fréquence facturation', selection=[('au_mois', 'Au mois'),('a_la_livraison', 'A la livraison')])




# TODO : A revoir dans un deuxième temps

    # @api.multi
    # @api.depends('country_id')
    # def _compute_product_pricelist(self):
    #     company = self.env.context.get('force_company', False)
    #     res = self.env['product.pricelist']._get_partner_pricelist_multi(self.ids, company_id=company)

    #     for p in self:
    #         pricelist = res.get(p.id)
    #         if pricelist:
    #             if not pricelist.partner_id:
    #                 p.property_product_pricelist = res.get(p.id)
    #             elif p.id == pricelist.partner_id.id:
    #                 p.property_product_pricelist = pricelist.id
    #         else:
    #             continue


    # # NOT A REAL PROPERTY !!!!
    # property_product_pricelist = fields.Many2one(
    #     'product.pricelist', 'Pricelist', store=True,  help="This pricelist will be used, instead of the default one, for sales to the current partner..", compute=_compute_product_pricelist)

    # mode_facturation = fields.Selection([('cmde', 'A la commande'), ('mensuel', 'Mensuel')], string="Mode Facturation")