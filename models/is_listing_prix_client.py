# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
import codecs
import unicodedata
import base64
import sys
import threading
import time
import psutil


@api.model
def _lang_get(self):
    return self.env['res.lang'].get_installed()


class MesureMemoire(threading.Thread):
    """Relève toutes les 0,2 s la mémoire (RSS) du processus Odoo et de ses
    processus enfants (wkhtmltopdf) et garde le maximum de chacun"""

    def __init__(self, intervalle=0.2):
        super().__init__(daemon=True)
        self.process = psutil.Process()
        self.intervalle = intervalle
        self.odoo_debut = self.process.memory_info().rss
        self.odoo_max = self.odoo_debut
        self.enfants_max = 0
        self._arret = threading.Event()

    def mesurer(self):
        try:
            self.odoo_max = max(self.odoo_max, self.process.memory_info().rss)
            enfants = 0
            for enfant in self.process.children(recursive=True):
                try:
                    enfants += enfant.memory_info().rss
                except psutil.Error:
                    pass
            self.enfants_max = max(self.enfants_max, enfants)
        except psutil.Error:
            pass

    def run(self):
        while not self._arret.is_set():
            self.mesurer()
            self._arret.wait(self.intervalle)

    def arreter(self):
        self._arret.set()
        self.join()
        self.mesurer()


class IsListingPrixClient(models.Model):
    _name = 'is.listing.prix.client'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Listing prix client"
    _order = 'nom_listing, name desc'

    name          = fields.Char("Listing", readonly=True)
    enseigne_id   = fields.Many2one('is.enseigne.commerciale', 'Enseigne', required=True, help="Enseigne commerciale")
    pricelist_id  = fields.Many2one('product.pricelist', 'Liste de prix' , required=True)
    partner_id    = fields.Many2one('res.partner', 'Client')
    nom_listing   = fields.Char("Nom du listing")
    product_ids   = fields.Many2many('product.product', 'is_listing_prix_client_product_rel', 'doc_id', 'product_id', 'Articles')
    nb_articles   = fields.Integer("Nombre d'articles", compute='_compute_nb_articles', store=True)
    afficher_prix = fields.Boolean("Afficher prix actuel", default=True)
    prix_futur = fields.Selection([
            ('cdf_quai'  , 'Cdf quai'),
            ('cdf_franco', 'Cdf franco'),
            ('lf'        , 'LF'),
            ('lf_coll'   , 'LF coll.'),
            ('ft'        , 'FT'),
        ], 'Prix futur à afficher', copy=False)
    lang = fields.Selection(_lang_get, string='Langue', default='fr_FR')
    active = fields.Boolean("Actif", default=True, tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', 'is_listing_prix_client_attachment_rel', 'doc_id', 'file_id', 'Pièces jointes', copy=False)


    @api.depends('product_ids')
    def _compute_nb_articles(self):
        for obj in self:
            obj.nb_articles = len(obj.product_ids)


    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            self.nom_listing  = self.partner_id.name
            self.enseigne_id  = self.partner_id.is_enseigne_id.id
            self.pricelist_id = self.partner_id.property_product_pricelist.id


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.listing.prix.client')
        res = super(IsListingPrixClient, self).create(vals)
        return res


    def ajouter_articles_action(self):
        for obj in self:
            obj.product_ids=[]
            ids=[]
            for item in obj.pricelist_id.item_ids:
                ids.append(item.product_tmpl_id.id)
            products = self.env['product.product'].search([('product_tmpl_id','in',ids)]) #,limit=2000)
            ids=[]
            for p in products:
                ids.append(p.id)
            vals={
                'product_ids': [(6, 0, ids)]
            }
            obj.write(vals)


    def _generer_pdf(self, report_xmlid):
        """Génère le PDF du rapport indiqué, l'enregistre dans les pièces jointes
        (annule et remplace le précédent) et indique dans le chatter la durée et
        la mémoire maxi utilisée"""
        report = self.env.ref(report_xmlid)
        for obj in self:
            mesure = MesureMemoire()
            mesure.start()
            debut = time.time()
            try:
                pdf, _format = report._render_qweb_pdf(obj.ids)
            finally:
                mesure.arreter()
            duree = time.time() - debut

            nom = "%s %s.pdf" % (report.name, obj.name)
            obj.attachment_ids.filtered(lambda a: a.name == nom).unlink()
            attachment = self.env['ir.attachment'].create({
                'name'     : nom,
                'type'     : 'binary',
                'datas'    : base64.b64encode(pdf),
                'res_model': obj._name,
                'res_id'   : obj.id,
                'mimetype' : 'application/pdf',
            })
            obj.attachment_ids = [(4, attachment.id)]

            mo = 1024 * 1024
            body = """
                <b>PDF '%s' généré</b><br/>
                Articles : %s<br/>
                Durée : %.1f s<br/>
                Mémoire maxi Odoo : %.0f Mo (%.0f Mo au départ)<br/>
                Mémoire maxi wkhtmltopdf : %.0f Mo<br/>
                Taille du PDF : %.1f Mo
            """ % (
                report.name,
                len(obj.product_ids),
                duree,
                mesure.odoo_max / mo,
                mesure.odoo_debut / mo,
                mesure.enfants_max / mo,
                len(pdf) / mo,
            )
            obj.message_post(body=body)


    def generer_pdf_vignettes_action(self):
        self._generer_pdf('is_fromtome14.listing_prix_client_action')


    def generer_pdf_liste_action(self):
        self._generer_pdf('is_fromtome14.listing_prix_client_liste_action')


    def get_html4(self):
        """ Sortie sur 4 colonnes"""
        for obj in self:
            html="""
                <style>
                    h1{
                        font-size: 14pt;
                        margin-bottom: 0;
                        font-weight: bold;
                        line-height: 1;
                        margin-left:2mm;
                        margin-right:2mm;
                        padding:2mm;
                        background-color:black;
                        color:white;
                    }
                    table{
                        width:100%;
                        border-spacing:2mm 1mm;
                        border-collapse:separate;
                        font-size:9pt;
                    }
                    .tag{
                        border-radius:5pt;
                        border:1px solid #D8D8D9;
                        padding:2pt;
                        margin:2pt;
                        background-color:#F2F2F5;
                    }
                    .vignette{
                        border:1px solid #D8D8D9;
                        width:25%;
                        padding:2mm;
                        margin:2mm;
                        background-color:white;
                        vertical-align:top;
                    }
                    .prix{
                        text-align:center;
                        margin-bottom:2pt;
                        background-color:#F2F2F5;
                        margin-top:3mm;
                    }
                </style>
            """
            exclude=[]
            milks = self.env['milk.type'].search([])
            for milk in milks:

                ids=[]
                for p in obj.product_ids:
                    if milk in p.milk_type_ids:
                        if p.id not in exclude:
                            ids.append(p.id)
                            exclude.append(p.id)
                products = self.env['product.product'].search([('id','in',ids)], order="name")
                if products:
                    html+='<div style="height:2mm"></div>'
                    html+="<h1>%s</h1>"%(milk.name)
                    html+="<table>"
                    html+='<thead><tr style="height:0">'
                    html+='<th style="width:25%"></th>'
                    html+='<th style="width:25%"></th>'
                    html+='<th style="width:25%"></th>'
                    html+='<th style="width:25%"></th>'
                    html+='</tr></thead>'
                    html+="<tbody>"
                    col=1
                    ct=0
                    for p in products:
                        ct+=1

                        # #** Recherche du prix (ancienne méthode) **************
                        # items = self.env['product.pricelist.item'].search([
                        #         ('pricelist_id','=',obj.pricelist_id.id),('product_tmpl_id','=',p.product_tmpl_id.id)
                        #     ], order="date_start desc", limit=1)
                        # price=False
                        # for item in items:
                        #     price=item.price
                        # #******************************************************

                        #** Recherche du prix (du 15/02/26) *******************
                        price=False
                        if obj.afficher_prix:
                            price = p.get_product_pricelist(obj.pricelist_id)
                        #******************************************************

                        img=''
                        if p.image_1920:
                            img = tools.image_data_uri(p.image_1920)
                        colspan=1
                        border_width="1px"
                        if p.is_mise_en_avant:
                            border_width="4px"
                            colspan=2
                            if col==4:
                                html+='<td class="vignette"></td>'
                                html+="</tr>"
                                col=1
                        if col==1:
                            html+='<tr>'

                        if colspan>1:
                            html+='<td class="vignette" colspan="%s" style="border-width:%s">'%(colspan,border_width)
                        else:
                            html+='<td class="vignette">'

                        if obj.lang=="de_DE":
                            html+='<div style="text-align:center;font-size:8pt">Art. Nr./Bezeichnung<br>Gewicht/Verpackungseinheit</div>'

                        #** Recherche product dans la langue indiquée *********
                        translate_product = p.with_context(lang=obj.lang)
                        #******************************************************

                        html+='<div style="font-weight:bold;text-align:center;height:16mm">['+p.default_code+'] '+translate_product.name+'</div>'
                        if img:
                            html+='<div style="text-align:center;height:30mm"><img src="'+img+'" alt="Logo" style="max-height:30mm;max-width:35mm"/></div>'
                        else:
                            html+='<div style="text-align:center;height:25mm"/>'
                        if price:
                            price_fmt = '{:,.2f}'.format(price).replace(',', ' ').replace('.', ',')
                            html+='<div class="prix">'+price_fmt+'&nbsp;€/'+p.uom_id.name+'</div>'
                        else:
                            html+='<div class="prix"/>'
                        html+='<div style="line-height:2.1">'
                        #for l in p.milk_type_ids:
                        #    html+='<span class="tag">'+l.name+'</span> '
                        traitement=''
                        if p.traitement_thermique:
                            traitement = dict(self.env['product.product'].fields_get(allfields=['traitement_thermique'])['traitement_thermique']['selection'])[p.traitement_thermique]
                            traitement = traitement.replace(" ","&nbsp;")

                        if traitement:
                            html+='<span class="tag" style="background-color:#DCDCDC">'+traitement+'</span> '
                        if p.is_preco:
                            html+='<span class="tag" style="background-color:red;font-color:white">PRECO.</span> '
                        if p.is_bio_id:
                            html+='<span class="tag" style="background-color:#169539;font-color:white">BIO</span> '
                        html+='</div>'
                        html+='</td>'
                        col+=colspan
                        if col==5:
                            col=1
                            html+="</tr>"
                    if col>1:
                        for x in range(0, 5-col):
                            html+='<td class="vignette"></td>'
                        html+='</tr>'

                    html+="</tbody>"
                    html+="</table>"
                    html+='<div style="page-break-after: always;"></div>'
            return html


    def get_products(self):
        ids=[]
        for product in self.product_ids:
            ids.append(product.id)
        products = self.env['product.product'].search([('id','in',ids)],order='is_type_article,name')
        res={}
        for product in products:
            type = product.is_type_article 
            if type not in res:
                res[type]=[]
            res[type].append(product)
        return res
