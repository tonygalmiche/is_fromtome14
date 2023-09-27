# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, format_date, get_lang
from odoo.http import request
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

    currency_id      = fields.Many2one('res.currency', related='invoice_id.currency_id')
    amount_residual  = fields.Monetary(string="Montant dû"           , compute='_compute', readonly=True, store=True)
    partner_id       = fields.Many2one('res.partner', string="Client", compute='_compute', readonly=True, store=True)
    invoice_date     = fields.Date(string="Date facture"             , compute='_compute', readonly=True, store=True)
    invoice_date_due = fields.Date(string="Date d'échéance"          , compute='_compute', readonly=True, store=True)
    is_date_relance  = fields.Date(related='invoice_id.is_date_relance')
    is_date_releve   = fields.Date(related='invoice_id.is_date_releve')


    def voir_facture_action(self):
        for obj in self:
            return {
                "name": obj.relance_id.name,
                "view_mode": "form,tree",
                "res_model": "account.move",
                "res_id"   : obj.invoice_id.id,
                "type": "ir.actions.act_window",
            }


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

    name          = fields.Char("N°", readonly=True)
    type_document = fields.Selection([
            ('relance_facture', 'Relance de facture'),
            ('releve_facture' , 'Relevé de facture'),
        ], 'Type de document', default='relance_facture', required=True)
    partner_id        = fields.Many2one('res.partner', string="Client")
    nb_jours          = fields.Integer("Nombre de jours de retard mini", default=1)
    nb_jours_relance  = fields.Integer("Nombre de jours depuis la dernière relance", default=14)
    nb_jours_echeance = fields.Integer("Nombre de jours avant l'échéance", default=7)
    ligne_ids         = fields.One2many('is.relance.facture.ligne', 'relance_id', 'Lignes')
    currency_id       = fields.Many2one('res.currency'     , compute='_compute', readonly=True, store=True)
    amount_residual   = fields.Monetary(string="Montant dû", compute='_compute', readonly=True, store=True)
    state      = fields.Selection([
            ('brouillon', 'Brouillon'),
            ('envoye'   , 'Envoyé'),
        ], 'Etat', default='brouillon')


    @api.onchange('type_document','nb_jours','nb_jours_relance','nb_jours_echeance','partner_id')
    def cherche_factures(self):
        for obj in self:
            date_maxi          = date.today()-timedelta(days=obj.nb_jours)
            date_maxi_relance  = date.today()-timedelta(days=obj.nb_jours_relance)
            date_maxi_echeance = date.today()+timedelta(days=obj.nb_jours_echeance)
            lines=[]
            filtre=[
                ("state","=","posted"),
                ("move_type","=","out_invoice"),
                ('payment_state',"=","not_paid"),
            ]
            if obj.partner_id:
                filtre.append(("partner_id","=",obj.partner_id.id))
            if obj.type_document=="relance_facture":
                filtre.append(
                    ('invoice_date_due','<=',date_maxi)
                )
            if obj.type_document=="releve_facture":
                filtre.append(
                    ('invoice_date_due','>=',date.today())
                )
                filtre.append(
                    ('invoice_date_due','<=',date_maxi_echeance)
                )
                filtre.append(
                    ('is_date_releve','=',False)
                )
            invoices = self.env['account.move'].search(filtre, order="partner_id,name")
            for invoice in invoices:
                if obj.type_document=="relance_facture":
                    if invoice.is_date_relance==False or invoice.is_date_relance<=date_maxi_relance:
                        vals = {
                            'invoice_id': invoice.id
                        }
                        lines.append([0,0,vals])
                if obj.type_document=="releve_facture":
                    if invoice.is_date_releve==False or invoice.is_date_releve<=date_maxi_echeance:
                        vals = {
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
                if obj.type_document=="relance_facture":
                    line.invoice_id.is_date_relance = date.today()
                if obj.type_document=="releve_facture":
                    line.invoice_id.is_date_releve = date.today()
                partner=line.invoice_id.partner_id
                if partner not in mails:
                    mails[partner]=[]
                mails[partner].append(line.invoice_id)
            for partner in mails:
                obj.send_mail(partner,mails[partner])
            obj.state="envoye"
        

    def send_mail(self, partner, invoices):
        invoice=invoices[0]
        template = self.env.ref('account.email_template_edi_invoice', False)
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model="account.move",
            default_res_id=invoice.id,
            #default_use_template=bool(template),
            #default_template_id=template.id,
            default_composition_mode='comment',
            #default_is_log=True,
            custom_layout='mail.mail_notification_light', #Permet de définir la mise en page du mail
        )
         #** Recherche des factures PDF et génération si non trouvée **********
        attachment_ids=[]

        if self.type_document=="relance_facture":
            for invoice in invoices:
                filtre=[
                    ("res_model","=","account.move"),
                    ("res_id","=",invoice.id),
                ]
                attachments = self.env['ir.attachment'].search(filtre,limit=1,order="id desc")
                if len(attachments)>0:
                    attachment=attachments[0]
                else:
                    pdf = request.env.ref('account.account_invoices_without_payment').sudo()._render_qweb_pdf([invoice.id])
                    if pdf:
                        attachments = self.env['ir.attachment'].search(filtre,limit=1,order="id desc")
                        if len(attachments)>0:
                            attachment=attachments[0]
                if attachment:
                    attachment_ids.append(attachment.id)
        #**********************************************************************

        #** body **************************************************************
        if self.type_document=="relance_facture":
            body="""
                <p>Bonjour,</p> 
                <p>Sauf erreur de notre part, les factures ci-dessous restent impayées:</p> 
                <ul>
            """
            total=0
            for invoice in invoices:
                total+=invoice.amount_residual
                body+="<li>Facture N°%s à l'échéance du %s pour un montant de %0.2f€ </li>"%(invoice.name, invoice.invoice_date_due.strftime('%d/%m/%Y'), invoice.amount_residual)
            body+="""
                    </ul>
                <p>Total FROMTOME à devoir : %0.2f€</p> 
                <p>Merci de régulariser votre compte</p> 
            """%(total)
        if self.type_document=="releve_facture":
            body="""
                <p>Bonjour,</p> 
                <p>Veuillez trouver ci-dessous les factures à échéance ces prochains jours:</p> 
                <ul>
            """
            total=0
            for invoice in invoices:
                total+=invoice.amount_residual
                body+="<li>Facture N°%s à l'échéance du %s pour un montant de %0.2f€ </li>"%(invoice.name, invoice.invoice_date_due.strftime('%d/%m/%Y'), invoice.amount_residual)
            body+="""
                    </ul>
                <p>Total FROMTOME à devoir : %0.2f€</p> 
            """%(total)
        #**********************************************************************


        #** subject ***********************************************************
        invoice_name=[]
        for invoice in invoices:
            invoice_name.append(invoice.name)

        if self.type_document=="relance_facture":
            subject="Relance de factures %s (%s)"%(partner.parent_id.name or partner.name, ", ".join(invoice_name))
        if self.type_document=="releve_facture":
            subject="Relevé de factures %s (%s)"%(partner.parent_id.name or partner.name, ", ".join(invoice_name))
        #**********************************************************************
        vals={
            "model"         : "account.move",
            "subject"       : subject,
            "body"          : body,
            "partner_ids"   : [invoice.partner_id.id],
            "attachment_ids": attachment_ids,
            #"template_id"   : False,
        }
        wizard = self.env['mail.compose.message'].with_context(ctx).create(vals)
        wizard.send_mail()



    #TODO  : Envoi du message directement sans passer par le wizard 'mail.compose.message' => L'enveloppe rouge n'apparait pas dans les logs
    # def envoi_mail(self, partner, invoices):
    #     for obj in self:
    #         body_html="""
    #             <p>Bonjour,</p> 
    #             <p>Sauf erreur de notre part, les factures ci-dessous restent impayées:</p> 
    #             <ul>
    #         """
    #         for invoice in invoices:
    #             body_html+="<li>Fact N°%s à échéance au %s </li>"%(invoice.name, invoice.invoice_date_due)
    #         body_html+="""
    #              </ul>
    #             <p>Total FROMTOME à devoir</p> 
    #             <p>Merci de régulariser votre compte</p> 
    #         """
    #         email_to="tony.galmiche@infosaone.com"
    #         email_cc="tony.galmiche@gmail.com"
    #         vals={
    #             #'email_from'    : email_from, 
    #             'email_to'      : email_to, 
    #             'email_cc'      : email_cc,
    #             'subject'       : "Relance facture %s"%(partner.name),
    #             'body'          : body_html, 
    #             'body_html'     : body_html, 
    #             'model'         : invoices[0]._name,
    #             'res_id'        : invoices[0].id,
    #             'notification'  : True,
    #             'message_type'  : 'comment', # Choix : email, comment
    #             "subtype_id"    : 1,         # 1=Discussions, 2=Note
    #             #"parent_id"     : invoices[0].id,
    #         }
    #         email=self.env['mail.mail'].create(vals)
    #         email.send()
    #     # for attachment in attachments:
    #     #     attachment_data = {
    #     #         'name': attachment[0],
    #     #         'datas': attachment[1],
    #     #         'type': 'binary',
    #     #         'res_model': 'mail.message',
    #     #         'res_id': mail.mail_message_id.id,
    #     #     }
    #     #     attachment_ids.append((4, Attachment.create(attachment_data).id))
    #     # if attachment_ids:
    #     #     mail.write({'attachment_ids': attachment_ids})
    #     # if force_send:
    #     #     mail.send(raise_exception=raise_exception)
    #     # return mail.id  # TDE CLEANME: return mail + api.returns ?

