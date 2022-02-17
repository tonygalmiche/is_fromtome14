# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
import codecs
import unicodedata
import base64
import sys

class IsListingPrixClient(models.Model):
    _name = 'is.listing.prix.client'
    _description = "Listing prix client"
    _order = 'name desc'

    name         = fields.Char("Listing", readonly=True)
    pricelist_id = fields.Many2one('product.pricelist', 'Liste de prix')
    partner_id   = fields.Many2one('res.partner', 'Partenaire')
    product_ids  = fields.Many2many('product.product', 'is_listing_prix_client_product_rel', 'doc_id', 'product_id', 'Articles')

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.listing.prix.client')
        res = super(IsListingPrixClient, self).create(vals)
        return res


    def ajouter_articles_action(self):
        for obj in self:
            print(obj)
            obj.product_ids=[]


            ids=[]
            for item in obj.pricelist_id.item_ids:
                ids.append(item.product_tmpl_id.id)
                #print(item.price)
            #print(ids)

            products = self.env['product.product'].search([('product_tmpl_id','in',ids)],limit=2000)
            print(products)
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
            ids=[]
            for p in obj.product_ids:
                ids.append(p.id)
            products = self.env['product.product'].search([('id','in',ids)], order="name")

            html="""
                <style>
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
            html+="<h1>Listing des prix %s</h1>"%(obj.name)
            html+="<table style='width:100%;border-spacing:3mm;border-collapse:separate;font-size:9pt'>"
            col=0
            ct=0
            for p in products:
                ct+=1
                print(ct,sys.getsizeof(html))



                #
                items = self.env['product.pricelist.item'].search([('pricelist_id','=',obj.pricelist_id.id),('product_tmpl_id','=',p.product_tmpl_id.id)])
                print("###", p,items)
                price=False
                for item in items:
                    price=item.price

                img=''
                if p.image_1920:
                    img = tools.image_data_uri(p.image_1920)
                col+=1
                if col==1:
                    html+="<tr>"

                html+='<td class="vignette">'
                html+='<div style="font-weight:bold;text-align:center;height:23mm">['+p.default_code+'] '+p.name+'</div>'
                
                if img:
                    html+='<div style="text-align:center;height:30mm"><img src="'+img+'" alt="Logo" style="max-height:30mm;max-width:35mm"/></div>'
                else:
                    html+='<div style="text-align:center;height:25mm"/>'


                if price:
                    html+='<div class="prix">'+str(price)+'/'+p.uom_id.name+'</div>'
                else:
                    html+='<div class="prix"/>'


                html+='<div style="line-height:2.1">'
                for l in p.milk_type_ids:
                    html+='<span class="tag">'+l.name+'</span> '
                traitement=''
                if p.traitement_thermique:
                    traitement = dict(self.env['product.product'].fields_get(allfields=['traitement_thermique'])['traitement_thermique']['selection'])[p.traitement_thermique]
                    traitement = traitement.replace(" ","&nbsp;")

                if traitement:
                    html+='<span class="tag" style="background-color:#DCDCDC">'+traitement+'</span> '
                if p.is_preco:
                    html+='<span class="tag" style="background-color:red;font-color:white">PRECO.</span> '
                if p.is_bio:
                    html+='<span class="tag" style="background-color:green;font-color:white">BIO</span> '

                html+='</div>'



                html+='</td>'
                if col==4:
                    col=0
                    html+="</tr>"
            html+="<table>"
            return html




    # def get_html3(self):
    #     """ Sortie sur 3 colonnes"""
    #     for obj in self:
    #         ids=[]
    #         for p in obj.product_ids:
    #             ids.append(p.id)
    #         products = self.env['product.product'].search([('id','in',ids)], order="name")
    #         html="<h1>Listing des prix %s</h1>"%(obj.name)
    #         html+="<table style='width:100%;border-spacing:3mm;border-collapse:separate;'>"
    #         col=0
    #         for p in products:
    #             img=''
    #             if p.image_1920:
    #                 img = tools.image_data_uri(p.image_1920)
    #             col+=1
    #             if col==1:
    #                 html+="<tr>"
    #             html+='<td style="border:1px solid #D8D8D9;width:33%;padding:2mm;margin:2mm;background-color:white;vertical-align:top;">'
    #             html+='<div style="font-weight:bold;text-align:center;height:20mm">['+p.default_code+'] '+p.name+'</div>'
    #             html+='<div style="text-align:center;height:30mm"><img src="'+img+'" alt="Logo" style="max-height:25mm;max-width:45mm"/></div>'
    #             html+='<div style="line-height:2.2">'
    #             for l in p.milk_type_ids:
    #                 html+='<span style="border-radius:5pt;background-color:#F2F2F5;border:1px solid #D8D8D9;padding:4pt;margin:4pt">'+l.name+'</span> '
    #             html+='</div>'
    #             traitement=''
    #             if p.traitement_thermique:
    #                 traitement = dict(self.env['product.product'].fields_get(allfields=['traitement_thermique'])['traitement_thermique']['selection'])[p.traitement_thermique]
    #                 traitement = traitement.replace(" ","&nbsp;")
    #             html+='<p style="line-height:2.2">'
    #             html+='<span style="border-radius:5pt;background-color:#DCDCDC;border:1px solid #D8D8D9;padding:4pt;margin:4pt">'+traitement+'</span> '
    #             if p.is_preco:
    #                 html+='<span style="border-radius:5pt;background-color:red;font-color:white;border:1px solid #FB573D;padding:4pt;margin:4pt">PRECO.</span> '
    #             if p.is_bio:
    #                 html+='<span style="border-radius:5pt;background-color:green;font-color:white;border:1px solid #FB573D;padding:4pt;margin:4pt">BIO</span> '
    #             html+='</p>'
    #             html+='<div style="height:10mm;text-align:center">U vente: Kg - Prix : 99,99</div>'
    #             html+='</td>'
    #             if col==3:
    #                 col=0
    #                 html+="</tr>"
    #         html+="<table>"
    #         return html

