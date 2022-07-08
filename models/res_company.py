from email.policy import default
from odoo import api, fields, models

class Company(models.Model):
    _inherit = 'res.company'

    is_gln          = fields.Char(string='GLN')
    is_regroupe_cde = fields.Selection(string='Regrouper les commandes', selection=[('Oui', 'Oui'), ('Non', 'Non')], default="Oui", help="Regrouper les commandes des clients sur les commandes fournisseur")


