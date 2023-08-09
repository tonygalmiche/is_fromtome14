# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import codecs
import unicodedata
import base64
from datetime import date,timedelta



class IsRelanceFactureLigne(models.Model):
    _name = 'is.relance.facture.ligne'
    _description = "Lignes des relances de factures"
    _order='sequence,id'


    @api.depends('invoice_id')
    def _compute(self):
        for obj in self:
            obj.amount_residual  = obj.invoice_id.amount_residual
            obj.partner_id       = obj.invoice_id.partner_id.id
            obj.invoice_date     = obj.invoice_id.invoice_date
            obj.invoice_date_due = obj.invoice_id.invoice_date_due


    relance_id       = fields.Many2one('is.relance.facture', 'Relance facture', required=True, ondelete='cascade')
    sequence         = fields.Integer("Ordre")
    invoice_id       = fields.Many2one('account.move', 'Facture', required=True, domain=[
        ("state","=","posted"),("move_type","=","out_invoice"),('payment_state',"=","not_paid")
    ])

    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id')
    amount_residual  = fields.Monetary(string="Montant dû"           , compute='_compute', readonly=True, store=True)
    partner_id       = fields.Many2one('res.partner', string="Client", compute='_compute', readonly=True, store=True)
    invoice_date     = fields.Date(string="Date facture"             , compute='_compute', readonly=True, store=True)
    invoice_date_due = fields.Date(string="Date d'échéance"          , compute='_compute', readonly=True, store=True)


    def voir_facture_action(self):
        for obj in self:
            return {
                "name": obj.relance_id.name,
                "view_mode": "form,tree",
                "res_model": "account.move",
                "res_id"   : obj.invoice_id.id,
                "type": "ir.actions.act_window",
            }



    def ajout_notification(self):
        for obj in self:

            print(obj.invoice_id._name)

            #email_from="tony.galmiche@infosaone.com"
            email_to="tony.galmiche@infosaone.com"
            email_cc="tony.galmiche@gmail.com"

            body_html="""
                <p>Bonjour,</p> 
                <p>Sauf erreur de notre part, les factures ci-dessous restent impayées:</p> 
                <ul>
                    <li>Fact N°              à échéance au </li>
                    <li>Fact N°              à échéance au </li>
                    <li>Fact N°              à échéance au </li>
                </ul>
                <p>Total FROMTOME à devoir</p> 
                <p>Merci de régulariser votre compte</p> 
            """

            vals={
                #'email_from'    : email_from, 
                'email_to'      : email_to, 
                'email_cc'      : email_cc,
                'subject'       : "Relance facture",
                #'body'          : "Relance facture", 
                'body_html'     : body_html, 
                'model'         : obj.invoice_id._name,
                'res_id'        : obj.invoice_id.id,
                'notification'  : True,
                'message_type'  : 'comment',
                "subtype_id"    : 2, #Note
            }
            #notification=self.env['mail.message'].create(vals)
            notification=self.env['mail.mail'].create(vals)






class IsRelanceFacture(models.Model):
    _name = 'is.relance.facture'
    _description = "Relances de factures"
    _order = 'name desc'


    @api.depends('ligne_ids')
    def _compute(self):
        currency=self.env.user.company_id.currency_id
        for obj in self:
            amount_residual=0
            for line in obj.ligne_ids:
                amount_residual+=line.amount_residual
            obj.amount_residual = amount_residual
            obj.currency_id = currency.id

    name            = fields.Char("N°Relance", readonly=True)
    partner_id      = fields.Many2one('res.partner', string="Client")
    nb_jours        = fields.Integer("Nombre de jours de retard mini", default=1, required=True)
    ligne_ids       = fields.One2many('is.relance.facture.ligne', 'relance_id', 'Lignes')
    currency_id     = fields.Many2one('res.currency'     , compute='_compute', readonly=True, store=True)
    amount_residual = fields.Monetary(string="Montant dû", compute='_compute', readonly=True, store=True)
    state      = fields.Selection([
            ('brouillon', 'Brouillon'),
            ('envoye'   , 'Envoyé'),
        ], 'Etat', default='brouillon')


    @api.onchange('nb_jours','partner_id')
    def cherche_receptions(self):
        for obj in self:
            date_maxi = date.today()-timedelta(days=obj.nb_jours)
            lines=[]
            filtre=[
                ("state","=","posted"),
                ("move_type","=","out_invoice"),
                ('payment_state',"=","not_paid"),
                ('invoice_date_due','<=',date_maxi),
            ]
            if obj.partner_id:
                filtre.append(("partner_id","=",obj.partner_id.id))
            invoices = self.env['account.move'].search(filtre, order="partner_id,name")
            for invoice in invoices:
                vals = {
                    #'relance_id': obj.id,
                    'invoice_id': invoice.id
                }
                lines.append([0,0,vals])
            obj.ligne_ids = False
            obj.ligne_ids = lines



    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.relance.facture')
        res = super(IsRelanceFacture, self).create(vals)
        return res


    def voir_factures_action(self):
        for obj in self:
            ids=[]
            for line in obj.ligne_ids:
                ids.append(line.invoice_id.id)
            return {
                "name": obj.name,
                "view_mode": "tree,form",
                "res_model": "account.move",
                "type": "ir.actions.act_window",
                "domain": [
                    ('id','in',ids),
                ],
            }




    def generer_relance_action(self):
        for obj in self:
            mails={}
            for line in obj.ligne_ids:
                line.invoice_id.is_date_relance = date.today()
                partner=line.invoice_id.partner_id
                if partner not in mails:
                    mails[partner]=[]
                mails[partner].append(line.invoice_id)


            print(mails)
            for partner in mails:
                #print(partner.name)
                #for line in mails[partner]:
                #    print("-",line.name)
                obj.envoi_mail(partner,mails[partner])



                #line.ajout_notification()
            #obj.state="envoye"
        






    def envoi_mail(self, partner, invoices):
        for obj in self:
            print(partner.name)

            body_html="""
                <p>Bonjour,</p> 
                <p>Sauf erreur de notre part, les factures ci-dessous restent impayées:</p> 
                <ul>
            """
            for invoice in invoices:
                body_html+="<li>Fact N°%s à échéance au %s </li>"%(invoice.name, invoice.invoice_date_due)
            body_html+="""
                 </ul>
                <p>Total FROMTOME à devoir</p> 
                <p>Merci de régulariser votre compte</p> 
            """

            #print(body_html)

            email_to="tony.galmiche@infosaone.com"
            email_cc="tony.galmiche@gmail.com"

            vals={
                #'email_from'    : email_from, 
                'email_to'      : email_to, 
                'email_cc'      : email_cc,
                'subject'       : "Relance facture %s"%(partner.name),
                'body'          : body_html, 
                'body_html'     : body_html, 
                'model'         : invoices[0]._name,
                'res_id'        : invoices[0].id,
                'notification'  : True,
                'message_type'  : 'comment', # Choix : email, comment
                "subtype_id"    : 1,         # 1=Discussions, 2=Note
                #"parent_id"     : invoices[0].id,
            }
            email=self.env['mail.mail'].create(vals)
            email.send()
          

        # for attachment in attachments:
        #     attachment_data = {
        #         'name': attachment[0],
        #         'datas': attachment[1],
        #         'type': 'binary',
        #         'res_model': 'mail.message',
        #         'res_id': mail.mail_message_id.id,
        #     }
        #     attachment_ids.append((4, Attachment.create(attachment_data).id))
        # if attachment_ids:
        #     mail.write({'attachment_ids': attachment_ids})

        # if force_send:
        #     mail.send(raise_exception=raise_exception)
        # return mail.id  # TDE CLEANME: return mail + api.returns ?

