# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class AccountPaymentOrder(models.Model):
    _inherit = 'account.payment.order'

    #Champ créé uniquement pour pouvoir faire un PDF
    partner_id = fields.Many2one('res.partner','Partenaire', related='generated_user_id.partner_id')
