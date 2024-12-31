# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _

class MailTemplate(models.Model):
    _inherit = 'mail.template'
 
    active = fields.Boolean("Actif", default=True)