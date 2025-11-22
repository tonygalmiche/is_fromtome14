# -*- coding: utf-8 -*-
from odoo import api, fields, models, _   # type: ignore
from odoo.exceptions import Warning       # type: ignore
import codecs
import unicodedata
import base64
from datetime import datetime, date, timedelta
from math import *


class IsCommandeFromtomeLigne(models.Model):
    _name = 'is.commande.fromtome.ligne'
    _description = "Commande fromtome Lignes"
    _order='sequence,id'

    commande_id      = fields.Many2one('is.commande.fromtome', 'Cde', required=True, ondelete='cascade')
    sequence         = fields.Integer("Ord")
    product_id       = fields.Many2one('product.product', 'Article')
    uom_id           = fields.Many2one('uom.uom', "Unité article")
    nb_pieces_par_colis = fields.Integer(string='PCB')
    poids_net_colis     = fields.Float(string='Poids net colis (Kg)', digits='Stock Weight')
    unite            = fields.Char("Unité calcul")
    sale_qty         = fields.Float("Qt cde client" , digits=(14,4))
    purchase_qty     = fields.Float("Qt déja en cde", digits=(14,4))
    product_qty      = fields.Float("Qt à cde"      , digits=(14,4))
    stock            = fields.Float("Stock FT"      , digits=(14,2))
    stock_lc         = fields.Float("Stock LC"      , digits=(14,2))
    stock_mini       = fields.Float("Stock mini"    , digits=(14,2))
    order_line_id    = fields.Many2one('purchase.order.line', 'Ligne commande fournisseur', index=True)


class IsCommandeFromtome(models.Model):
    _name = 'is.commande.fromtome'
    _description = "Commande fromtome"
    _order='name desc'

    name         = fields.Char("N°", readonly=True)
    enseigne_id  = fields.Many2one('is.enseigne.commerciale', 'Enseigne', required=True, help="Enseigne commerciale")
    warehouse_id = fields.Many2one(related='enseigne_id.warehouse_id')
    partner_id   = fields.Many2one('res.partner', 'Fournisseur', required=True)
    stock_mini   = fields.Boolean("Stock mini", default=True, help=u"Si cette case est cochée, il faut tenir compte du stock mini")
    order_id     = fields.Many2one('purchase.order', 'Commande Fromtome', copy=False)
    ligne_ids    = fields.One2many('is.commande.fromtome.ligne', 'commande_id', 'Lignes')
    date_fin     = fields.Date("Date de fin de prise en compte des commandes", required=True, default=lambda self: fields.Datetime.now()+timedelta(7), 
                        help="Date prise en compte:\nCommande client: Date livraison client entête\nCommande fournisseur: Date de réception entête")
    calcul_en_colis = fields.Boolean("Calcul en colis", default=False, help="Le résultat affiché sera en colis")


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.commande.fromtome')
        res = super(IsCommandeFromtome, self).create(vals)
        return res


    def calcul_besoins_action(self):
        cr,uid,context,su = self.env.args
        warehouses = self.env['stock.warehouse'].search([])
        for obj in self:

            if obj.order_id and obj.order_id.state!='draft':
                raise Warning(u"La commande Fromtome associée est déjà validée. Le calcul n'est pas autorisé !")

            obj.ligne_ids.unlink()

            #** Création commande fournisseur **********************************
            if obj.order_id:
                order=obj.order_id
            else:
                vals={
                    'partner_id'  : obj.partner_id.id,
                }
                order=self.env['purchase.order'].create(vals)
                obj.order_id=order.id
            if order:
                order.onchange_partner_id()
            order.order_line.unlink()
            now = date.today()
            filtre=[
                ('sale_ok','=',True),
                #('default_code','in',['0107001','1212017','1212022','1212035','0901019','1501008','1907005','1901010','1217002','1217001','0107002'])
            ]
            products = self.env['product.product'].search(filtre,order='name')
            sequence=1
            for product in products:
                if product.default_code:
                    #** Commande client ****************************************
                    sql="""
                        SELECT  
                            pt.default_code,
                            sol.product_id,
                            sum(sol.product_uom_qty-sol.qty_delivered)
                        FROM sale_order so join sale_order_line sol on so.id=sol.order_id
                                           join product_product pp on sol.product_id=pp.id
                                           join product_template pt on pp.product_tmpl_id=pt.id
                                           join res_partner rp on so.partner_id=rp.id
                        WHERE 
                            so.state='sale' and
                            (so.is_commande_soldee='f' or so.is_commande_soldee is null) and 
                            so.is_date_livraison>='2020-10-01' and
                            so.is_date_livraison<=%s and 
                            sol.product_id=%s and rp.is_enseigne_id=%s
                        GROUP BY pt.default_code,sol.product_id 
                        ORDER BY pt.default_code,sol.product_id
                    """
                    cr.execute(sql,[obj.date_fin, product.id,obj.enseigne_id.id])
                    sale_qty = 0
                    for row in cr.fetchall():
                        sale_qty = row[2]
                    if obj.calcul_en_colis:
                        sale_qty = product.product_tmpl_id.uom2colis(sale_qty)
                    #***********************************************************


                    #** Commande Fromtome ***********************************
                    sql="""
                        SELECT  
                            pt.default_code,
                            pol.product_id,
                            pol.product_qty,
                            pol.qty_received
                        FROM purchase_order po inner join purchase_order_line pol on po.id=pol.order_id
                                           inner join product_product pp on pol.product_id=pp.id
                                           inner join product_template pt on pp.product_tmpl_id=pt.id
                        WHERE 
                            po.state not in ('done','cancel','draft') and
                            po.date_planned>='2020-10-01' and
                            po.date_planned<=%s and 
                            pol.product_id=%s and
                            po.is_commande_soldee='f'
                    """
                    cr.execute(sql,[obj.date_fin,product.id])
                    purchase_qty = 0
                    for row in cr.fetchall():
                        qt = row[2]-(row[3] or 0)
                        if qt<0:
                            qt=0
                        purchase_qty += qt
                    #***********************************************************


                    #Convertir la quantité en UA en US *************************
                    purchase_qty = product.uom_po_id._compute_quantity(purchase_qty, product.uom_id, round=True, rounding_method='UP', raise_if_failure=True)
                    if obj.calcul_en_colis:
                        purchase_qty = product.product_tmpl_id.uom2colis(purchase_qty)
                    #***********************************************************


                    #** stock_mini *********************************************
                    stock_mini=0
                    if obj.stock_mini==True:
                        if obj.warehouse_id.code=="FT":
                            stock_mini = product.is_stock_mini
                        else:
                            stock_mini = product.is_stock_mini_lc
                    if obj.calcul_en_colis:
                        stock_mini = product.product_tmpl_id.uom2colis(stock_mini)
                    #***********************************************************


                    #** Recherche du stock dans l'Entrepôt ********************
                    stock_ft=0
                    stock_lc=0
                    for warehouse in warehouses:
                        location_id =  warehouse.lot_stock_id.id
                        stock = 0
                        quants = self.env['stock.quant'].search([('product_id','=',product.id),('location_id','=',location_id)])
                        for quant in quants:
                            stock+=quant.quantity
                        if warehouse.code=='LC':
                            stock_lc = stock
                        if warehouse.code=='FT':
                            stock_ft = stock
                    if obj.calcul_en_colis:
                        stock    = product.product_tmpl_id.uom2colis(stock)
                        stock_lc = product.product_tmpl_id.uom2colis(stock_lc)
                        stock_ft = product.product_tmpl_id.uom2colis(stock_ft)
                    #***********************************************************


                    #** Calcul de la quantité à commander **********************
                    product_qty = sale_qty - stock_ft - stock_lc + stock_mini - purchase_qty
                    if product_qty<0:
                        product_qty=0
                    #***********************************************************


                    # # ** Arrondi au colis supérieur ***************************
                    # if product_qty>0:
                    #     nb        = product.is_nb_pieces_par_colis
                    #     poids_net = product.is_poids_net_colis
                    #     unite     = product.uom_id.category_id.name
                    #     if unite=="Poids":
                    #         if poids_net>0:
                    #             product_qty = poids_net * ceil(product_qty / poids_net)
                    #     else:
                    #         if nb>0:
                    #             product_qty = nb * (product_qty / nb)
                    # # *********************************************************


                    #** Création des lignes de la commande **********************
                    order_line_id=False
                    if product_qty>0:
                        vals={
                            'order_id'    : order.id,
                            'sequence'    : sequence,
                            'product_id'  : product.id,
                            'name'        : product.name,
                            'product_qty' : 0,
                            'product_uom' : product.uom_po_id.id,
                            'date_planned': str(now)+' 08:00:00',
                            'price_unit'  : 0,
                        }
                        order_line=self.env['purchase.order.line'].create(vals)
                        order_line.onchange_product_id()

                        if obj.calcul_en_colis:
                            order_line.is_nb_colis = product_qty
                            order_line.onchange_is_nb_colis()
                        else:
                            order_line.product_qty = product_qty
                            order_line.onchange_product_qty_fromtome()
                        order_line._compute_is_nb_pieces_par_colis()
                        order_line_id=order_line.id
                    #***********************************************************


                    #** Création des lignes du calcul des besoins **************
                    if sale_qty>0 or product_qty>0:
                        unite="Colis"
                        if obj.calcul_en_colis!=True:
                            unite=product.uom_id.name
                        vals={
                            'commande_id'   : obj.id,
                            'sequence'      : sequence,
                            'product_id'    : product.id,
                            'uom_id'        : product.uom_id.id,
                            'nb_pieces_par_colis': product.is_nb_pieces_par_colis,
                            'poids_net_colis'    : product.is_poids_net_colis,
                            'unite'         : unite,
                            'sale_qty'      : sale_qty,
                            'purchase_qty'  : purchase_qty,
                            'product_qty'   : product_qty,
                            'stock'         : stock_ft,
                            'stock_lc'      : stock_lc,
                            'stock_mini'    : stock_mini,
                            'order_line_id' : order_line_id,
                        }
                        ligne=self.env['is.commande.fromtome.ligne'].create(vals)
                        sequence+=1
                    #***********************************************************




