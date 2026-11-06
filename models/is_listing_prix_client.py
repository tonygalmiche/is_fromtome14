# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools.pdf import merge_pdf
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import codecs
import unicodedata
import base64
import sys
import io
import threading
import time
import logging
import psutil

_logger = logging.getLogger(__name__)

# Nombre d'articles par lot pour la génération du PDF par lots
TAILLE_LOT = 250


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


    def _get_groupes_lait(self):
        """Articles regroupés par type de lait, triés par nom : [(milk_id, [product_id, ...]), ...]
        Un article n'apparaît que dans le premier type de lait qui le concerne"""
        self.ensure_one()
        groupes = []
        exclude = set()
        for milk in self.env['milk.type'].search([]):
            ids = []
            for p in self.product_ids:
                if milk in p.milk_type_ids and p.id not in exclude:
                    ids.append(p.id)
                    exclude.add(p.id)
            if ids:
                products = self.env['product.product'].search([('id', 'in', ids)], order="name")
                groupes.append((milk.id, products.ids))
        return groupes


    def _get_lots(self, taille_lot):
        """Découpe les groupes par type de lait en lots d'environ taille_lot articles.
        Un lot ne coupe un type de lait que si celui-ci dépasse taille_lot articles"""
        lots = []
        lot = []
        nb = 0
        for milk_id, product_ids in self._get_groupes_lait():
            for i in range(0, len(product_ids), taille_lot):
                morceau = product_ids[i:i + taille_lot]
                if lot and nb + len(morceau) > taille_lot:
                    lots.append(lot)
                    lot = []
                    nb = 0
                lot.append((milk_id, morceau))
                nb += len(morceau)
        if lot:
            lots.append(lot)
        return lots


    def _render_pdf_par_lots(self, report, taille_lot=TAILLE_LOT):
        """Génère le PDF par lots (images en image_512, sans numéro de page),
        fusionne les lots puis ajoute les numéros de page"""
        self.ensure_one()
        mo = 1024 * 1024
        process = psutil.Process()
        lots = self._get_lots(taille_lot)
        nb_articles = len(self.product_ids)
        fait = 0
        pdfs = []
        for n, groupes in enumerate(lots, 1):
            debut = time.time()
            report_lot = report.with_context(
                listing_groupes=groupes,
                listing_champ_image='image_512',
                listing_sans_numero_page=True,
            )
            pdf, _format = report_lot._render_qweb_pdf(self.ids)
            pdfs.append(pdf)
            nb = sum(len(product_ids) for _milk_id, product_ids in groupes)
            fait += nb
            _logger.info("Listing %s : lot %s/%s (%s articles, %s/%s) généré en %.1f s - PDF %.2f Mo - mémoire Odoo %.0f Mo",
                self.name, n, len(lots), nb, fait, nb_articles, time.time() - debut, len(pdf) / mo, process.memory_info().rss / mo)
        if not pdfs:
            raise UserError("Aucun article à imprimer")
        debut = time.time()
        pdf = pdfs[0] if len(pdfs) == 1 else merge_pdf(pdfs)
        del pdfs
        _logger.info("Listing %s : %s lots fusionnés en %.1f s - PDF %.2f Mo", self.name, len(lots), time.time() - debut, len(pdf) / mo)
        debut = time.time()
        pdf = self._numeroter_pages(pdf)
        _logger.info("Listing %s : numéros de page ajoutés en %.1f s - PDF %.2f Mo", self.name, time.time() - debut, len(pdf) / mo)
        return pdf


    def _numeroter_pages(self, pdf):
        """Ajoute 'Page: n / total' en bas de chaque page, à la place du pied de
        page de wkhtmltopdf"""
        reader = PdfFileReader(io.BytesIO(pdf), strict=False)
        writer = PdfFileWriter()
        total = reader.getNumPages()
        for n in range(total):
            page = reader.getPage(n)
            largeur = float(page.mediaBox.getWidth())
            hauteur = float(page.mediaBox.getHeight())
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=(largeur, hauteur))
            c.setFont("Helvetica", 9)
            c.setFillGray(0.42)
            c.drawCentredString(largeur / 2, 5 * mm, "Page: %s / %s" % (n + 1, total))
            c.save()
            page.mergePage(PdfFileReader(io.BytesIO(buffer.getvalue())).getPage(0))
            writer.addPage(page)
        resultat = io.BytesIO()
        writer.write(resultat)
        return resultat.getvalue()


    def _generer_pdf(self, report_xmlid, par_lots=False):
        """Génère le PDF du rapport indiqué, l'enregistre dans les pièces jointes
        (annule et remplace le précédent) et indique dans le chatter la durée et
        la mémoire maxi utilisée"""
        report = self.env.ref(report_xmlid)
        libelle = "%s (vignette)" % report.name if par_lots else report.name
        mo = 1024 * 1024
        for obj in self:
            mesure = MesureMemoire()
            mesure.start()
            debut = time.time()
            erreur = False
            try:
                if par_lots:
                    pdf = obj._render_pdf_par_lots(report)
                else:
                    pdf, _format = report._render_qweb_pdf(obj.ids)
            except Exception as e:
                _logger.exception("Échec de la génération du PDF '%s' du listing %s", libelle, obj.name)
                erreur = "%s : %s" % (type(e).__name__, str(e)[:1000])
            finally:
                mesure.arreter()
            duree = time.time() - debut
            memoire_maxi = max(mesure.odoo_max, mesure.enfants_max)

            if erreur:
                # L'exception est sortie du bloc except : la mémoire du HTML est libérée.
                # Le message est enregistré dans une transaction séparée pour ne pas
                # être annulé avec la transaction en erreur
                body = """
                    <b>Échec de la génération du PDF '%s'</b><br/>
                    Articles : %s<br/>
                    Durée : %.1f s<br/>
                    Mémoire maxi : %.0f Mo<br/>
                    Erreur : %s
                """ % (
                    libelle,
                    len(obj.product_ids),
                    duree,
                    memoire_maxi / mo,
                    tools.html_escape(erreur),
                )
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, self.env.uid, self.env.context)
                    env[obj._name].browse(obj.id).message_post(body=body)
                raise UserError("Échec de la génération du PDF '%s' après %.1f s (mémoire maxi : %.0f Mo) :\n%s" % (
                    libelle, duree, memoire_maxi / mo, erreur))

            # Annule et remplace le PDF précédent du même rapport (nom avec ou sans date)
            prefixe = "%s %s" % (libelle, obj.name)
            obj.attachment_ids.filtered(
                lambda a: a.name == prefixe + ".pdf" or a.name.startswith(prefixe + " ")
            ).unlink()
            date = fields.Datetime.context_timestamp(obj, fields.Datetime.now())
            nom = "%s %s.pdf" % (prefixe, date.strftime('%Y-%m-%d %H:%M:%S'))
            attachment = self.env['ir.attachment'].create({
                'name'     : nom,
                'type'     : 'binary',
                'datas'    : base64.b64encode(pdf),
                'res_model': obj._name,
                'res_id'   : obj.id,
                'mimetype' : 'application/pdf',
            })
            obj.attachment_ids = [(4, attachment.id)]

            body = """
                <b>PDF '%s' généré</b><br/>
                Articles : %s<br/>
                Durée : %.1f s<br/>
                Mémoire maxi : %.0f Mo<br/>
                Taille du PDF : %.2f Mo
            """ % (
                libelle,
                len(obj.product_ids),
                duree,
                memoire_maxi / mo,
                len(pdf) / mo,
            )
            obj.message_post(body=body)


    def generer_pdf_vignettes_action(self):
        self._generer_pdf('is_fromtome14.listing_prix_client_action')


    def generer_pdf_vignettes_par_lots_action(self):
        self._generer_pdf('is_fromtome14.listing_prix_client_action', par_lots=True)


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
            # Génération par lots : groupes du lot et champ image passés dans le contexte
            groupes = self.env.context.get('listing_groupes')
            if groupes is None:
                groupes = obj._get_groupes_lait()
            champ_image = self.env.context.get('listing_champ_image', 'image_1920')
            for milk_id, product_ids in groupes:
                milk = self.env['milk.type'].browse(milk_id)
                products = self.env['product.product'].browse(product_ids)
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
                        if p[champ_image]:
                            img = tools.image_data_uri(p[champ_image])
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
