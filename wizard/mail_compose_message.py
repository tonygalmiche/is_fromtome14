# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MailComposer(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.multi
    def get_mail_values(self, res_ids):
        self.ensure_one()
        res = super(MailComposer, self).get_mail_values(res_ids)
        copie_ids=[]
        for key, value in res.items():
            for partner in self.is_partner_copie_ids:
                copie_ids.append((4,partner.id))
            if 'author_id' in  value:
                copie_ids.append((4,value['author_id']))
            value['is_partner_copie_ids'] = copie_ids
        return res
    is_partner_copie_ids = fields.Many2many('res.partner','mail_compose_message_partner_copie_rel', 'mail_compose_id', 'partner_id', string='en Copie')


class Message(models.Model):
    _inherit = 'mail.message'

    is_partner_copie_ids = fields.Many2many('res.partner', 'mail_notification_partner_copie_rel', 'message_id', 'partner_id', string='en Copie')


class MailMail(models.Model):
    _inherit = 'mail.mail'

    @api.multi
    def _send(self, auto_commit=False, raise_exception=False, smtp_session=None):
        for mail in self:
            email_cc = ','.join(mail.mail_message_id.is_partner_copie_ids.mapped('email'))
            mail.email_cc = email_cc
        new_mail = super(MailMail, self)._send(auto_commit=auto_commit, raise_exception=raise_exception, smtp_session=smtp_session)
        return new_mail

