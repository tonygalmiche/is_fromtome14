from odoo import api, fields, models

class Company(models.Model):
    _inherit = 'res.company'

    #inv_is_colis = fields.Boolean(string="Gestion Stock des colis", help="Cochez si l'unité de stockage est colis")
    is_gln = fields.Char(string='GLN')


# class ResDiscountSettings(models.TransientModel):
#     _inherit = 'res.config.settings'

#     inv_is_colis = fields.Boolean(related="company_id.inv_is_colis" ,string="Gestion Stock des colis",
#                                   help="Cochez si l'unité de stockage est colis", readonly=False, stored=True)
