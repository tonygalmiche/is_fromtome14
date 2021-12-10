# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _


class MailActivity(models.Model):
    _inherit = 'mail.activity'
 
    active = fields.Boolean("Actif", default=True)


    def unlink(self):
        self.active=False
        return True
