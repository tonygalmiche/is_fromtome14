from odoo import fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'

    is_imprimante_id = fields.Many2one('is.imprimante.etiquette', 'Imprimante étiquettes')
