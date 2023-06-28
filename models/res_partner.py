# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    partner_id = fields.Many2one('res.partner','Client')


class IsEnseigneCommerciale(models.Model):
    _name = 'is.enseigne.commerciale'
    _description = "Enseigne commerciale"

    name         = fields.Many2one('res.partner', 'Enseigne commerciale', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Entrepôt')


class IsTransporteur(models.Model):
    _name = 'is.transporteur'
    _description = "Transporteur"

    name = fields.Char('Transporteur', required=True)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_date_reception           = fields.Date(string='Dernière date de réception saisie')
    is_product_supplierinfo_ids = fields.One2many('product.supplierinfo', 'name', 'Liste de prix')
    is_gln                      = fields.Char('GLN Client')
    is_iln                      = fields.Char('ILN Client')
    is_code_fromtome            = fields.Char('Code Fournisseur', help="Code Fromtome chez le client")
    is_code_interne             = fields.Char('Code Interne'    , help="Code interne utilisé en particulier pour Le Cellier")
    is_code_tarif               = fields.Char('Code Tarif'      , help="Code utilisé par Le Cellier pour la gestion des tarifs")
    is_enseigne_id              = fields.Many2one('is.enseigne.commerciale', 'Enseigne', help="Enseigne commerciale")
    is_customer                 = fields.Boolean("Est un Client")
    is_supplier                 = fields.Boolean("Est un Fournisseur")
    is_frequence_facturation    = fields.Selection(string='Fréquence facturation', selection=[('au_mois', 'Au mois'),('a_la_livraison', 'A la livraison')])
    is_modele_commande_id       = fields.Many2one('is.modele.commande', 'Modèle de commande')
    is_presentation_bl          = fields.Selection(string='Présentation BL', selection=[('standard', 'Standard'),('detaillee', 'Détaillée')], default="standard")
    is_transporteur_id          = fields.Many2one('is.transporteur', 'Transporteur', help="Enseigne commerciale")
    is_warehouse_id             = fields.Many2one('stock.warehouse', 'Entrepôt', help="Entrepôt à utiliser dans les réceptions ou les livraisons")
    is_frais_port_id            = fields.Many2one('product.product', 'Frais de port', domain=[('categ_id.name','=','TRANSPORT')], help="Utilisé pour ajouter automatiquement une ligne de frais de port sur les commandes")
    is_heure_envoi              = fields.Char('Heure', help="Heure maxi d'envoi de la commande au fournisseur")


    def creer_modele_commande(self):
        for obj in self:
            vals={
                'name'  : obj.name,
            }
            modele=self.env['is.modele.commande'].create(vals)
            obj.is_modele_commande_id = modele.id
            modele.initialiser_action()
