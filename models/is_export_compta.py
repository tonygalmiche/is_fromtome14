# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import codecs
import unicodedata
import base64
import shutil
import os

class IsExportComptaLigne(models.Model):
    _name = 'is.export.compta.ligne'
    _description = "Export Compta Lignes"
    _order='ligne,id'

    export_compta_id = fields.Many2one('is.export.compta', 'Export Compta', required=True, ondelete='cascade')
    ligne            = fields.Integer("Ligne")
    journal_code     = fields.Char("JournalCode")
    journal_lib      = fields.Char("JournalLib")
    partner_id       = fields.Many2one('res.partner', 'Partenaire')
    enseigne_id      = fields.Many2one('is.enseigne.commerciale', 'Enseigne', related='partner_id.is_enseigne_id')
    ecriture_num     = fields.Char("EcritureNum")
    ecriture_date    = fields.Date("EcritureDate")
    compte_num       = fields.Char("CompteNum")
    compte_lib       = fields.Char("CompteLib")
    comp_aux_num     = fields.Char("CompAuxNum")
    comp_aux_lib     = fields.Char("CompAuxLib")
    piece_ref        = fields.Char("PieceRef")
    piece_date       = fields.Date("PieceDate")
    ecriture_lib     = fields.Char("EcritureLib")
    debit            = fields.Float("Debit" , digits=(14,2))
    credit           = fields.Float("Credit", digits=(14,2))
    invoice_id       = fields.Many2one('account.move', 'Facture')
    payment_id       = fields.Many2one('account.payment', 'Paiement')




class IsExportCompta(models.Model):
    _name = 'is.export.compta'
    _description = "Export Compta"
    _order = 'name desc'

    name       = fields.Char("N°Folio", readonly=True)
    date_fin   = fields.Date("Date de fin"  , required=True)
    facture    = fields.Boolean("Exporter les factures", default=True)
    escompte   = fields.Boolean("Exporter les escomptes", default=True)
    traite     = fields.Boolean("Exporter les traites", default=True)
    ligne_ids  = fields.One2many('is.export.compta.ligne', 'export_compta_id', u'Lignes')
    file_ids   = fields.Many2many('ir.attachment', 'is_export_compta_attachment_rel', 'doc_id', 'file_id', u'Fichiers')
    company_id = fields.Many2one('res.company', u'Société',required=True,default=lambda self: self.env.user.company_id.id)
    format_export = fields.Selection([
        ('ALG_COMPTA' , 'ALG COMPTA'),
        ('MY_UNISOFT' , 'MY UNISOFT'),
    ], 'Format export', required=True, default="ALG_COMPTA")


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.export.compta')
        res = super(IsExportCompta, self).create(vals)
        return res


    def generer_lignes_action(self):
        cr, user, context, su = self.env.args
        ct=0

        #Retourne le dictionnaire traduit du champ type de account.journal
        account_journal_type = dict(self.env['account.journal'].with_context(lang='fr_FR').fields_get(['type'])['type']['selection'])

        for obj in self:
            obj.ligne_ids.unlink()
            if obj.facture:
                invoices = self.env['account.move'].search([('is_export_compta_id','=',obj.id)])
                for invoice in invoices:
                    invoice.is_export_compta_id=False
                self._cr.commit()
                sql="""
                    SELECT  
                        aj.name,
                        am.name,
                        am.invoice_date,
                        aa.code,
                        aa.name,
                        am.invoice_date,
                        'aml.name',
                        sum(aml.debit),
                        sum(aml.credit),
                        rp.name,
                        rp.ref,
                        am.id,
                        aj.code,
                        am.partner_id,
                        aj.type,
                        aa.name
                    FROM account_move_line aml inner join account_move am                on aml.move_id=am.id
                                            inner join account_account aa             on aml.account_id=aa.id
                                            left outer join res_partner rp            on aml.partner_id=rp.id
                                            inner join account_journal aj             on aml.journal_id=aj.id
                    WHERE 
                        am.is_export_compta_id is null and
                        am.invoice_date<=%s and aj.name in ('VE','AC')
                    GROUP BY 
                        aj.name,
                        am.name,
                        am.invoice_date,
                        aa.code,
                        aa.name,
                        am.invoice_date,
                        rp.name,
                        rp.ref,
                        am.id,
                        aj.code,
                        am.partner_id,
                        aj.type,
                        aa.name
                    ORDER BY am.invoice_date,am.name,aa.code
                """
                cr.execute(sql,[obj.date_fin])
                for row in cr.fetchall():
                    invoice_id = row[11]
                    invoices = self.env['account.move'].search([('id','=',invoice_id)])
                    compte_num = row[3]
                    comp_aux_num = ''
                    if compte_num[:3] in ['401','411']:
                        comp_aux_num = row[10]
                    for invoice in invoices:
                        invoice.is_export_compta_id = obj.id
                        if compte_num[:3]=='411':
                            compte_num = invoice.partner_id.property_account_receivable_id.code
                        if compte_num[:3]=='401':
                            compte_num = invoice.partner_id.property_account_payable_id.code
                    journal_lib = account_journal_type.get(row[14])
                    ct=ct+1
                    vals={
                        'export_compta_id': obj.id,
                        'ligne'           : ct,
                        'journal_code'           : row[0],
                        'journal_lib'            : journal_lib,
                        'ecriture_num'           : row[1],
                        'ecriture_date'          : row[2],
                        'compte_num'             : compte_num,
                        'compte_lib'             : row[15],
                        'comp_aux_num'           : comp_aux_num,
                        'piece_ref'              : row[1],
                        'piece_date'             : row[5],
                        'ecriture_lib'           : row[9] or row[6],
                        'debit'                  : row[7],
                        'credit'                 : row[8],
                        'invoice_id'             : invoice_id,
                        'partner_id'             : row[13],
                    }
                    self.env['is.export.compta.ligne'].create(vals)

            if obj.escompte:
                payments = self.env['account.payment'].search([('is_export_compta_id','=',obj.id)])
                for payment in payments:
                    payment.is_export_compta_id=False
                self._cr.commit()
                sql="""
                    SELECT  
                        am.partner_id,
                        am.name,
                        am.date,
                        aa.code,
                        aa.name,
                        aml.name,
                        aml.debit,
                        aml.credit,
                        rp.name,
                        rp.ref,
                        aml.payment_id,
                        am.invoice_date,
                        aa.name
                    FROM account_move_line aml inner join account_move am                on aml.move_id=am.id
                                            inner join account_account aa             on aml.account_id=aa.id
                                            left outer join res_partner rp            on aml.partner_id=rp.id
                                            inner join account_journal aj             on aml.journal_id=aj.id
                                            inner join account_payment ap             on aml.payment_id=ap.id
                    WHERE 
                        am.date<='"""+str(obj.date_fin)+"""' and 
                        am.company_id="""+str(self.env.user.company_id.id)+""" and
                        aa.code='665100' and
                        ap.is_export_compta_id is null and 
                        aa.code is not null
                    ORDER BY am.date
                """
                cr.execute(sql)
                for row in cr.fetchall():
                    payment_id = row[10]
                    payments = self.env['account.payment'].search([('id','=',payment_id)])
                    partner=False
                    for payment in payments:
                        payment.is_export_compta_id = obj.id
                        partner = payment.partner_id
                    if partner:
                        journal_code  = 'ESC'
                        ecriture_num  = row[1]
                        ecriture_date = row[2]
                        compte_num = row[3]
                        ct=ct+1
                        vals={
                            'export_compta_id': obj.id,
                            'ligne'           : ct,
                            'journal_code'           : journal_code,
                            'journal_lib'            : journal_code,
                            'ecriture_num'           : ecriture_num,
                            'ecriture_date'          : ecriture_date,
                            'compte_num'             : compte_num,
                            'compte_lib'             : row[12],
                            'piece_ref'              : ecriture_num,
                            'piece_date'             : ecriture_date,
                            'ecriture_lib'           : row[5],
                            'debit'                  : row[6],
                            'credit'                 : row[7],
                            'payment_id'             : payment_id,
                            'partner_id'             : row[0],
                        }
                        self.env['is.export.compta.ligne'].create(vals)
                        ct=ct+1
                        compte_num = partner.property_account_receivable_id.code
                        vals={
                            'export_compta_id': obj.id,
                            'ligne'           : ct,
                            'journal_code'           : journal_code,
                            'ecriture_num'           : ecriture_num,
                            'ecriture_date'          : ecriture_date,
                            'compte_num'             : compte_num,
                            'compte_lib'             : row[12],
                            'piece_ref'              : ecriture_num,
                            'piece_date'             : ecriture_date,
                            'ecriture_lib'           : row[5],
                            'debit'                  : row[7],
                            'credit'                 : row[6],
                            'payment_id'             : payment_id,
                            'partner_id'             : row[0],
                        }
                        self.env['is.export.compta.ligne'].create(vals)


            if obj.traite:
                journal_code  = 'RG'
                payments = self.env['account.payment.order'].search([('is_export_compta_id','=',obj.id)])
                for payment in payments:
                    payment.is_export_compta_id=False
                domain=[
                    ('is_export_compta_id','=',False),
                    ('date_generated','<=',obj.date_fin),
                    ('state','!=','cancel'),
                ]
                payments = self.env['account.payment.order'].search(domain)
                for payment in payments:
                    for invoice in payment.move_ids:
                        for line in invoice.line_ids:
                            num_fac=False
                            for l in line.bank_payment_line_id:
                                num_fac=l.communication
                            ecriture_lib = line.partner_id.name or line.name
                            if num_fac:
                                ecriture_lib = "%s:%s"%(num_fac,line.partner_id.name or '')
                            ct=ct+1
                            compte_num = line.account_id.code or ''
                            if compte_num == '512100':
                                 compte_num = '511130'
                            vals={
                                'export_compta_id': obj.id,
                                'ligne'           : ct,
                                'journal_code'           : journal_code,
                                'journal_lib'            : journal_code,
                                'ecriture_num'           : payment.name,
                                'ecriture_date'          : payment.date_generated,
                                'compte_num'             : compte_num,
                                'compte_lib'             : compte_num,
                                'piece_ref'              : payment.name,
                                'piece_date'             : payment.date_generated,
                                'ecriture_lib'           : ecriture_lib,
                                'debit'                  : line.debit,
                                'credit'                 : line.credit,
                                'partner_id'             : line.partner_id.id,
                            }
                            self.env['is.export.compta.ligne'].create(vals)
                            ct=ct+1
                    payment.is_export_compta_id=obj.id


    def generer_fichier_action(self):
        cr=self._cr
        for obj in self:
            model='is.export.compta'
            attachments = self.env['ir.attachment'].search([('res_model','=',model),('res_id','=',obj.id)])
            attachments.unlink()
            if obj.format_export=='ALG_COMPTA':
                name='export-compta.txt'
                dest     = '/tmp/'+name
                f = codecs.open(dest,'wb',encoding='utf-8')
                f.write("ligne\tjournal_code\tecriture_num\tecriture_date\tcompte_num\tcomp_aux_num\tpiece_ref\tpiece_date\tecriture_lib\tdebit\tcredit\tenseigne\r\n")
                for row in obj.ligne_ids:
                    f.write(str(row.ligne)+'\t')
                    f.write(row.journal_code+'\t')
                    f.write(row.ecriture_num+'\t')
                    f.write(row.ecriture_date.strftime('%Y%m%d')+'\t')
                    f.write((row.compte_num or '')+'\t')
                    f.write((row.comp_aux_num or '')+'\t')
                    f.write(row.piece_ref+'\t')
                    f.write(row.piece_date.strftime('%Y%m%d')+'\t')
                    f.write(row.ecriture_lib+'\t')
                    f.write(str(row.debit).replace('.','.')+'\t')
                    f.write(str(row.credit).replace('.','.')+'\t')
                    f.write((row.enseigne_id.name.name or '')+'\t')
                    f.write('\r\n')
                f.close()
                r = open(dest,'rb').read()
                r=base64.b64encode(r)
                vals = {
                    'name':        name,
                    #'datas_fname': name,
                    'type':        'binary',
                    'res_model':   model,
                    'res_id':      obj.id,
                    'datas':       r,
                }
                attachment = self.env['ir.attachment'].create(vals)
                obj.file_ids=[(6,0,[attachment.id])]


            if obj.format_export=='MY_UNISOFT':
                #** Création du dossier d'export ******************************
                dir_path="/tmp/%s"%obj.name
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
                os.mkdir(dir_path)
                #**************************************************************

                name='export-compta.txt'
                dest = '%s/%s'%(dir_path,name)
                f = codecs.open(dest,'wb',encoding='utf-8')
                f.write("JournalCode\tJournalLib\tEcritureNum\tEcritureDate\tCompteNum\tCompteLib\tCompAuxNum\tCompAuxLib\tPieceRef\tPieceDate\tEcritureLib\tDebit\tCredit\tEcritureLet\tDateLet\tValidDate\tMontantdevise\tIdevise\r\n")

                for row in obj.ligne_ids:
                    f.write(row.journal_code+'\t')
                    f.write((row.journal_lib or '')+'\t')
                    f.write(row.ecriture_num+'\t')
                    f.write(row.ecriture_date.strftime('%Y%m%d')+'\t')
                    f.write((row.compte_num or '')+'\t')
                    f.write((row.compte_lib or '')+'\t')
                    f.write((row.comp_aux_num or '')+'\t')
                    f.write((row.comp_aux_num or '')+'\t')
                    f.write(row.piece_ref+'\t')
                    f.write(row.piece_date.strftime('%Y%m%d')+'\t')
                    f.write(row.ecriture_lib+'\t')
                    f.write(str(row.debit).replace('.','.')+'\t')
                    f.write(str(row.credit).replace('.','.')+'\t')
                    f.write('\t')
                    f.write('\t')
                    f.write('\t')
                    f.write('\t')
                    f.write('\t')
                    f.write('\r\n')
                f.close()

                #** Enregistement des PDF des factures ************************
                invoices=[]
                for line in obj.ligne_ids:
                    if line.journal_code=='VE':
                        if line.invoice_id and line.invoice_id not in invoices:
                            invoices.append(line.invoice_id)
                nb=len(invoices)
                ct=1
                for invoice in invoices:
                    pdf = self.env.ref('account.account_invoices')._render_qweb_pdf(invoice.id)[0]
                    if pdf:
                        pdf_name = invoice.name.replace('/','_')
                        path = "%s/%s.pdf"%(dir_path,pdf_name)
                        print(ct,nb,path)
                        f = open(path,'wb')
                        f.write(pdf)
                        f.close()
                    ct+=1
                #**************************************************************

                #** Création du ZIP *******************************************
                zip_path = '/tmp/%s'%obj.name
                shutil.make_archive(zip_path, 'zip', dir_path)
                #**************************************************************

                #** Ajout de la pièce jointe **********************************
                zip_name = '%s.zip'%obj.name
                zip_path = '/tmp/%s'%zip_name
                r = open(zip_path,'rb').read()
                r=base64.b64encode(r)
                vals = {
                    'name':        zip_name,
                    'type':        'binary',
                    'res_model':   model,
                    'res_id':      obj.id,
                    'datas':       r,
                }
                attachment = self.env['ir.attachment'].create(vals)
                obj.file_ids=[(6,0,[attachment.id])]
                #**************************************************************
