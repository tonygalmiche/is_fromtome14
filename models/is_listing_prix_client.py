# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
import codecs
import unicodedata
import base64
import sys


@api.model
def _lang_get(self):
    return self.env['res.lang'].get_installed()


class IsListingPrixClient(models.Model):
    _name = 'is.listing.prix.client'
    _description = "Listing prix client"
    _order = 'nom_listing, name desc'

    name          = fields.Char("Listing", readonly=True)
    enseigne_id   = fields.Many2one('is.enseigne.commerciale', 'Enseigne', required=True, help="Enseigne commerciale")
    pricelist_id  = fields.Many2one('product.pricelist', 'Liste de prix' , required=True)
    partner_id    = fields.Many2one('res.partner', 'Client')
    nom_listing   = fields.Char("Nom du listing")
    product_ids   = fields.Many2many('product.product', 'is_listing_prix_client_product_rel', 'doc_id', 'product_id', 'Articles')
    afficher_prix = fields.Boolean("Afficher prix actuel", default=True)
    prix_futur = fields.Selection([
            ('cdf_quai'  , 'Cdf quai'),
            ('cdf_franco', 'Cdf franco'),
            ('lf'        , 'LF'),
            ('lf_coll'   , 'LF coll.'),
            ('ft'        , 'FT'),
        ], 'Prix futur à afficher', copy=False)
    lang = fields.Selection(_lang_get, string='Langue', default='fr_FR')


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
                        items = self.env['product.pricelist.item'].search([
                                ('pricelist_id','=',obj.pricelist_id.id),('product_tmpl_id','=',p.product_tmpl_id.id)
                            ], order="date_start desc", limit=1)
                        price=False
                        for item in items:
                            price=item.price
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


                        html+='<div style="font-weight:bold;text-align:center;height:16mm">['+p.default_code+'] '+p.name+'</div>'
                        if img:
                            html+='<div style="text-align:center;height:30mm"><img src="'+img+'" alt="Logo" style="max-height:30mm;max-width:35mm"/></div>'
                        else:
                            html+='<div style="text-align:center;height:25mm"/>'
                        if price:
                            html+='<div class="prix">'+str(price)+'/'+p.uom_id.name+'</div>'
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
