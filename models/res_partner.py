# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


HABITUDE_COMMANDE = [
    ('telephone', 'Téléphone'),
    ('mail'     , 'Mail'),
    ('sms'      , 'SMS'),
]


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    partner_id = fields.Many2one('res.partner','Client')


class IsEnseigneCommerciale(models.Model):
    _name = 'is.enseigne.commerciale'
    _description = "Enseigne commerciale"

    name                = fields.Many2one('res.partner', 'Enseigne commerciale', required=True)
    warehouse_id        = fields.Many2one('stock.warehouse', 'Entrepôt')
    modele_commande_ids = fields.Many2many('ir.attachment', 'is_enseigne_commerciale_modele_commande_rel', 'enseigne_id', 'file_id', 'Modèle de commande client')
    prix_sur_livraison  = fields.Boolean("Afficher le prix de vente sur le bon de livraison", default=False)
    rib                 = fields.Char("RIB")
    note_bl             = fields.Text("Note BL", help="Note à ajouter sur le BL")
    mini_cde_franco     = fields.Integer(string='Mini de commande franco (€)')


class IsTransporteur(models.Model):
    _name = 'is.transporteur'
    _description = "Transporteur"

    name = fields.Char('Transporteur', required=True)


class IsHeureMaxi(models.Model):
    _name = 'is.heure.maxi'
    _description = "Heure maxi d'envoi des commandes au fournisseur"
    _order='name'

    name = fields.Char("Heure maxi d'envoi des commandes au fournisseur", required=True)


class IsRemiseParticuliere(models.Model):
    _name = 'is.remise.particuliere'
    _description = "Remises particulières pour les clients"
    _order='product_id'

    partner_id    = fields.Many2one('res.partner', 'Client', required=True, ondelete='cascade')
    product_id    = fields.Many2one('product.product', 'Article', required=True)
    remise_client = fields.Float("Remise client (%)", digits=(14,2))


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _compute_is_encours_client(self):
        for obj in self:
            val = 0
            if obj.is_customer and obj.is_company:
                filtre=[('partner_id', '=', obj.id),('state', '=', 'posted'),('move_type', 'in', ['out_refund','out_invoice'])]
                invoices=self.env['account.move'].search(filtre)
                for invoice in invoices:
                    val+=invoice.amount_residual_signed
            obj.is_encours_client = val

  
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
    is_transporteur_id          = fields.Many2one('is.transporteur', 'Transporteur')
    is_warehouse_id             = fields.Many2one('stock.warehouse', 'Entrepôt', help="Entrepôt à utiliser dans les réceptions ou les livraisons")
    is_frais_port_id            = fields.Many2one('product.product', 'Frais de port', domain=[('categ_id.name','=','TRANSPORT')], help="Utilisé pour ajouter automatiquement une ligne de frais de port sur les commandes")
    is_heure_envoi_id           = fields.Many2one('is.heure.maxi', 'Jour / Heure limite', help="Heure maxi d'envoi de la commande au fournisseur")
    is_encours_client           = fields.Float(string='En-cours client', digits=(14,2), compute='_compute_is_encours_client')
    is_heure_appel              = fields.Char(string="Heure d'appel", help="Heure d'appel des clients")
    is_habitude_commande        = fields.Selection(HABITUDE_COMMANDE, 'Habitude commande')
    is_date_debut_nouveau_tarif = fields.Date(string="Date début nouveau tarif", help="Date utilisée lors de la copie d'un tarif dans un article")
    is_date_fin_nouveau_tarif   = fields.Date(string="Date fin nouveau tarif"  , help="Date utilisée lors de la copie d'un tarif dans un article")
    is_mini_cde                 = fields.Float(string="Mini de commande", help='Minimum de commande fournisseur', digits=(14,4))
    is_contact_relance_facture_id = fields.Many2one('res.partner', 'Contact relance facture')
    is_remise_particuliere_ids    = fields.One2many('is.remise.particuliere', 'partner_id', 'Remises particulières')
    is_commentaire_commande       = fields.Char(string="Commentaire commande")
    is_emplacement_fournisseur    = fields.Integer(string="Emplacement palette fournisseur")
    is_mini_cde_franco            = fields.Integer(string='Mini de commande franco (€)')


    default_supplierinfo_discount = fields.Float(
        string="Remise par défaut pour les articles (%)",
        digits="Discount",
    )

    is_pourcent_promo_a_repercuter = fields.Float(
        string="Pourcentage promo fournisseur à répercuter (%)",
        digits="Discount",
    )

    def creer_modele_commande(self):
        for obj in self:
            vals={
                'name'  : obj.name,
            }
            modele=self.env['is.modele.commande'].create(vals)
            obj.is_modele_commande_id = modele.id
            modele.initialiser_action()


    def _message_auto_subscribe_notify(self, partner_ids, template):
        "Désactiver les notifications d'envoi des mails"
        return True

