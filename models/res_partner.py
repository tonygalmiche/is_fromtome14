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
    is_gln                      = fields.Char('GLN Client')
    is_iln                      = fields.Char('ILN Client')
    is_code_fromtome            = fields.Char('Code Fournisseur', help="Code Fromtome chez le client")
    is_enseigne_id              = fields.Many2one('is.enseigne.commerciale', 'Enseigne', help="Enseigne commerciale")
    is_customer                 = fields.Boolean("Est un Client")
    is_supplier                 = fields.Boolean("Est un Fournisseur")
    is_frequence_facturation    = fields.Selection(string='Fréquence facturation', selection=[('au_mois', 'Au mois'),('a_la_livraison', 'A la livraison')])

