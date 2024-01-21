from email.policy import default
from odoo import api, fields, models

class Company(models.Model):
    _inherit = 'res.company'

    is_gln          = fields.Char(string='GLN')
    is_regroupe_cde = fields.Selection(string='Regrouper les commandes', selection=[('Oui', 'Oui'), ('Non', 'Non')], default="Oui", help="Regrouper les commandes des clients sur les commandes fournisseur")

    is_date_bascule_tarif = fields.Date(string='Date bascule tarif client')
    is_coef_cdf_quai      = fields.Float(string='Coefficient Cdf quai'  , digits=(14,4))
    is_coef_cdf_franco    = fields.Float(string='Coefficient Cdf franco', digits=(14,4))
    is_coef_lf            = fields.Float(string='Coefficient LF'        , digits=(14,4))
    is_coef_lf_coll       = fields.Float(string='Coefficient LF coll.'  , digits=(14,4))
    is_coef_ft            = fields.Float(string='Coefficient FT'        , digits=(14,4))


    def actualiser_tarif_action(self):
        for obj in self:
            self.env['product.template'].search([])._compute_tarifs()



    # def initialiser_tarif_en_cours_action(self):
    #     for obj in self:
    #         print(obj)


    # def initialiser_tarif_futur_action(self):
    #     for obj in self:
    #         print(obj)


    # def basculer_vers_nouveau_tarif_action(self):
    #     for obj in self:
    #         print(obj)
