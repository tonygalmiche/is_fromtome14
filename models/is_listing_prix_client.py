# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
import codecs
import unicodedata
import base64

class IsListingPrixClient(models.Model):
    _name = 'is.listing.prix.client'
    _description = "Listing prix client"
    _order = 'name desc'

    name        = fields.Char("Liste de prix", readonly=True)
    partner_id  = fields.Many2one('res.partner', 'Partenaire')
    product_ids = fields.Many2many('product.product', 'is_listing_prix_client_product_rel', 'doc_id', 'product_id', 'Articles')

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.listing.prix.client')
        res = super(IsListingPrixClient, self).create(vals)
        return res



    def get_html(self):
        for obj in self:
            ids=[]
            for p in obj.product_ids:
                ids.append(p.id)
            products = self.env['product.product'].search([('id','in',ids)], order="name")
            html="<h1>Listing des prix %s</h1>"%(obj.name)
            html+="<table style='width:100%;border-spacing:3mm;border-collapse:separate;'>"
            col=0
            for p in products:
                img=''
                if p.image_1920:
                    img = tools.image_data_uri(p.image_1920)
                col+=1
                if col==1:
                    html+="<tr>"
                html+='<td style="border:1px solid #D8D8D9;width:33%;padding:2mm;margin:2mm;background-color:white;vertical-align:top;">'
                html+='<div style="font-weight:bold;text-align:center;height:20mm">['+p.default_code+'] '+p.name+'</div>'
                html+='<div style="text-align:center;height:30mm"><img src="'+img+'" alt="Logo" style="max-height:25mm;max-width:45mm"/></div>'
                html+='<div style="line-height:2.2">'
                for l in p.milk_type_ids:
                    html+='<span style="border-radius:5pt;background-color:#F2F2F5;border:1px solid #D8D8D9;padding:4pt;margin:4pt">'+l.name+'</span> '
                html+='</div>'
                traitement=''
                if p.traitement_thermique:
                    traitement = dict(self.env['product.product'].fields_get(allfields=['traitement_thermique'])['traitement_thermique']['selection'])[p.traitement_thermique]
                    traitement = traitement.replace(" ","&nbsp;")
                html+='<p style="line-height:2.2">'
                html+='<span style="border-radius:5pt;background-color:#DCDCDC;border:1px solid #D8D8D9;padding:4pt;margin:4pt">'+traitement+'</span> '
                if p.is_preco:
                    html+='<span style="border-radius:5pt;background-color:red;font-color:white;border:1px solid #FB573D;padding:4pt;margin:4pt">PRECO.</span> '
                if p.is_bio:
                    html+='<span style="border-radius:5pt;background-color:green;font-color:white;border:1px solid #FB573D;padding:4pt;margin:4pt">BIO</span> '
                html+='</p>'
                html+='<div style="height:10mm;text-align:center">U vente: Kg - Prix : 99,99</div>'
                html+='</td>'
                if col==3:
                    col=0
                    html+="</tr>"
            html+="<table>"
            return html


