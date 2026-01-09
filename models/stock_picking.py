# -*- coding: utf-8 -*-
from odoo import fields, api, models, _
import time
from datetime import datetime, date, timedelta
from dateutil.parser import parse
import dateparser
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, format_datetime
import pytz
import logging
import base64
import io
try:
    from PyPDF2 import PdfWriter, PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfFileWriter as PdfWriter, PdfFileReader as PdfReader
    except ImportError:
        PdfWriter = PdfReader = None

class IsScanPickingLine(models.Model):
    _name = 'is.scan.picking.line'
    _description = "Lignes Scan Picking"
    _order='id'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for obj in self:
            obj.nb_pieces = obj.product_id.is_nb_pieces_par_colis
            obj.poids     = obj.product_id.is_poids_net_colis
            obj.nb_colis  = 1


    @api.depends('lot_id','nb_colis_reste')
    def _compute_alerte(self):
        for obj in self:
            alertes=[]
            if obj.nb_colis_reste<0:
                alertes.append("Reste<0")
            if obj.picking_id.picking_type_id.code=='outgoing':
                if obj.lot_id:
                    if obj.lot_id.create_date>obj.scan_id.create_date:
                        alertes.append("Lot créé après le scan")
            if obj.lot_id and obj.lot_id.is_dlc_ddm:
                now = datetime.now().date()
                if obj.lot_id.is_dlc_ddm<now:
                    depassement = (now-obj.lot_id.is_dlc_ddm).days
                    if depassement>=0:
                        alertes.append("DLC/DDM dépassée de %s jours"%depassement)
                if obj.product_id:
                    contrats = self.env['contrat.date.client'].search([('product_id', '=',obj.product_id.product_tmpl_id.id)])
                    for contrat in contrats:
                        date_limite = now+timedelta(days=contrat.name)
                        depassement = (date_limite-obj.lot_id.is_dlc_ddm).days
                        if not contrat.partner_id:
                            #date_limite = obj.lot_id.is_dlc_ddm-timedelta(days=contrat.name)
                            if obj.lot_id.is_dlc_ddm<=date_limite:
                                if depassement>=0:
                                    alertes.append("Contrat date de %s jours dépassé de %s jours (Date mini DLC=%s)"%(contrat.name, depassement, date_limite.strftime('%d/%m/%Y')))
                        else:
                            if obj.scan_id.picking_id:
                                if  obj.scan_id.picking_id.partner_id==contrat.partner_id:
                                    if depassement>=0:
                                        alertes.append("Contrat date client de %s jours dépassé de %s jours (Date mini DLC=%s)"%(contrat.name, depassement, date_limite.strftime('%d/%m/%Y')))
            obj.alerte = '\n'.join(alertes) or False


    @api.depends('product_id')
    def _compute_product_name(self):
        for obj in self:
            obj.product_name = obj.product_id.name

    scan_id             = fields.Many2one('is.scan.picking', 'Scan', required=True, ondelete='cascade')
    picking_id          = fields.Many2one('stock.picking', 'Picking', related='scan_id.picking_id')
    picking_type_id     = fields.Many2one('stock.picking.type', "Type d'opération", related='scan_id.picking_id.picking_type_id')
    product_id          = fields.Many2one('product.product', 'Article', required=True)
    product_name        = fields.Text('Désignation article', compute=_compute_product_name, readonly=True, store=True)
    product_code        = fields.Char('Code'                , related='product_id.default_code')
    uom_id              = fields.Many2one('uom.uom', 'Unité', related='product_id.uom_id')
    nb_pieces_par_colis = fields.Integer(string='PCB', related="product_id.is_nb_pieces_par_colis", help="Nb Pièces / colis")
    creation_lot        = fields.Boolean('Créé', help="Lot créé")
    lot_id              = fields.Many2one('stock.production.lot', 'Lot', required=True)
    type_tracabilite    = fields.Selection(string='Traçabilité', related="product_id.is_type_tracabilite")
    dlc_ddm             = fields.Date('DLC / DDM', related="lot_id.is_dlc_ddm")
    nb_pieces           = fields.Float('Pièces'   , digits=(14,4), help="Nb pièces scannées")
    nb_colis            = fields.Float('Colis'    , digits=(14,2), help="Nb Colis scannés")
    nb_colis_prevues    = fields.Float('Prévu'    , digits=(14,2), help="Nb Colis prévus")
    nb_colis_reste      = fields.Float('Reste'    , digits=(14,2), help="Nb Colis reste")
    poids               = fields.Float("Poids"    , digits='Stock Weight')
    info                = fields.Char("Info")
    alerte              = fields.Text('Alerte', compute=_compute_alerte, readonly=True, store=True)


class IsScanPickingLine(models.Model):
    _name = 'is.scan.picking.product'
    _description = "Articles à scanner du Picking"
    _order='id'

    scan_id    = fields.Many2one('is.scan.picking', 'Picking', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', 'Article', required=True)
    nb_pieces  = fields.Float('Nb pièces prévues', digits=(14,4))
    uom_id     = fields.Many2one('uom.uom', 'Unité', related='product_id.uom_id')
    nb_colis   = fields.Float('Nb colis prévus', digits=(14,2))


    def imprimer_etiquette_action(self):
        for obj in self:
            context = obj._context.copy()
            context['default_product_id'] = obj.product_id.id
            #context['default_lot']        = obj.lot
            #context['default_dlc']        = obj.dlc
            #context['default_dluo']       = obj.dluo
            #context['default_imprimante_id'] = obj.imprimante_id.id
            action = {
                'name': "Dupliquer",
                'view_mode': 'form',
                'res_model': 'is.imprimer.etiquette.gs1',
                #'view_id': self.env.ref('account.view_account_bnk_stmt_cashbox_footer').id,
                'type': 'ir.actions.act_window',
                'context': context,
                #'target': 'new'
            }
            return action


class IsScanPicking(models.Model):
    _name = 'is.scan.picking'
    _inherit = 'barcodes.barcode_events_mixin'
    _description = "Scan Picking"
    _order='id desc'
    _rec_name = 'id'


    @api.depends('ean','lot','product_id','lot_id','line_ids')
    def _compute_is_alerte(self):
        for obj in self:
            alertes=[]
            if obj.picking_id.picking_type_id.code=='outgoing':
                nb_creation_lot=0
                for line in obj.line_ids:
                    if line.creation_lot:
                        nb_creation_lot+=1
                if nb_creation_lot:
                    alertes.append("Attention : Vous avez créé %s nouveaux lots sur cette livraison ce qui n'est pas normal"%nb_creation_lot)

            if obj.ean and not obj.product_id:
                alertes.append("Article non trouvé pour ce code ean")
            #obj.is_alerte = '\n'.join(alertes) or False
            #if obj.lot and not obj.lot_id:
            #    alertes.append("Lot non trouvé ou non valide (manque DLC/DDM ou poids)")
            if obj.lot and not obj.lot_id and not obj.dlc_ddm :
                alertes.append("DLC/DDM non trouvée => Lot non valide")
            if obj.lot and not obj.lot_id and not obj.poids:
                alertes.append("Poids non trouvé pour un article vendu au poids")
            obj.is_alerte = '\n'.join(alertes) or False

    @api.onchange('ajouter')
    def _onchange_ajouter(self):
        for obj in self:
            obj.ajouter_ligne()
            obj.reset_scan()

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        for obj in self:
            obj.dlc_ddm = obj.lot_id.is_dlc_ddm

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.env.context.get("noonchange"): 
            for obj in self:
                obj.poids = obj.product_id.is_poids_net_colis


    @api.depends('ean','product_id')
    def _compute_maj_code_ean_article_vsb(self):
        for obj in self:
            vsb=False
            if obj.ean and obj.product_id and not obj.product_id.barcode:
                vsb=True
            obj.maj_code_ean_article_vsb=vsb
 


    type         = fields.Selection(string='Type', selection=[('picking', 'Picking'), ('inventory', 'Inventaire')], required=True, default='picking')
    picking_id   = fields.Many2one('stock.picking', 'Picking'     , required=False)
    partner_id   = fields.Many2one(related="picking_id.partner_id")
    inventory_id = fields.Many2one('stock.inventory', 'Inventaire', required=False)
    ean          = fields.Char("EAN")
    product_id   = fields.Many2one('product.product', 'Article')
    lot          = fields.Char("Lot scanné")
    lot_id       = fields.Many2one('stock.production.lot', 'Lot')
    type_tracabilite = fields.Selection(string='Traçabilité', related="product_id.is_type_tracabilite")
    dlc_ddm      = fields.Date('DLC / DDM')
    poids        = fields.Float("Poids", digits='Stock Weight')
    nb_colis     = fields.Integer('Colis', default=1)
    ajouter      = fields.Boolean("Ajouter", help="Ajouter cette ligne")
    is_alerte    = fields.Text('Alerte', compute=_compute_is_alerte, readonly=True, store=False)
    line_ids     = fields.One2many('is.scan.picking.line', 'scan_id', 'Lignes')
    product_ids  = fields.One2many('is.scan.picking.product', 'scan_id', 'Articles')
    maj_code_ean_article_vsb = fields.Boolean(string="Mettre ce code EAN sur l'article sélectionné vsb", compute='_compute_maj_code_ean_article_vsb')


    def reset_scan(self):
        for obj in self:
            obj.ean        = False
            obj.product_id = False
            obj.lot        = False
            obj.lot_id     = False
            obj.dlc_ddm    = False
            obj.poids      = False
            obj.nb_colis   = 1


    def ajouter_ligne(self): #, creation_lot=False):
        for obj in self:
            creation_lot=False
            if obj.product_id and obj.lot and obj.dlc_ddm:
                filtre=[
                    ('name'      ,'=', obj.lot ),
                    ('product_id','=', obj.product_id.id),
                    ('is_dlc_ddm','=', obj.dlc_ddm),
                ]
                lot = self.env['stock.production.lot'].search(filtre,limit=1)
                if lot:
                    lot_id = lot.id
                else:
                    vals={
                        "company_id": 1,
                        "name"      : obj.lot,
                        "product_id": obj.product_id.id,
                        "is_dlc_ddm": obj.dlc_ddm,
                    }
                    lot = self.env['stock.production.lot'].create(vals)
                    lot_id = lot.id
                    creation_lot=True
                obj.lot_id = lot_id

            if obj.product_id and obj.lot_id and obj.dlc_ddm:
                nb_colis = obj.nb_colis or 1
                nb_pieces=obj.product_id.is_nb_pieces_par_colis*nb_colis

                #** Recherche de la quantité prévue ***************************
                prevu=0.0
                if obj.picking_id:
                    for line in obj.product_ids:
                        if line.product_id==obj.product_id:
                            prevu=line.nb_colis
                #**************************************************************

                #** Recherche quantité scannée ********************************
                products={}
                scanne=nb_colis
                reste=0
                if obj.picking_id:
                    for line in obj.line_ids:
                        if line.product_id==obj.product_id:
                            scanne+=line.nb_colis
                    reste=prevu-scanne
                #**************************************************************

                tz = pytz.timezone('Europe/Paris')
                now = datetime.now(tz).strftime("%H:%M:%S")
                poids = (obj.poids or obj.product_id.is_poids_net_colis)*nb_colis
                vals={
                    "product_id": obj.product_id.id,
                    "lot_id"    : obj.lot_id.id,
                    "nb_pieces" : nb_pieces,
                    "nb_colis"  : nb_colis,
                    "nb_colis_prevues": prevu,
                    "nb_colis_reste"  : reste,
                    "poids"           : poids,
                    "info"            : now,
                    "creation_lot"    : creation_lot,
                }
                obj.write({"line_ids": [(0,0,vals)]})
                obj.reset_scan()


    def on_barcode_scanned(self, barcode):
        for obj in self:
            barcodes = barcode.split(chr(16))
            for barcode in barcodes:
                barcode_reste = False
                code   = str(barcode)[2:]
                prefix = str(barcode)[:2]
                if prefix in ("01","02"):
                    barcode_reste = barcode[16:]
                    obj.reset_scan()
                    ean = code[:14]
                    obj.ean = ean
                    products = self.env['product.product'].search([('barcode', '=',ean)])
                    for product in products:
                        self.env.context = self.with_context(noonchange=True).env.context
                        obj.product_id = product.id
                if prefix in ["15","17"]:
                    date = code[:6]
                    date = dateparser.parse(date, date_formats=['%y%m%d'])
                    if date:
                        obj.dlc_ddm = date.strftime('%Y-%m-%d')
                        barcode_reste = barcode[8:]

                if prefix=="31":
                    barcode_reste = barcode[10:]
                    barcode = barcode[0:10]
                    decimal = int(str(barcode)[3])
                    poids    = float(str(barcode)[4:-decimal] + '.' + str(barcode)[-decimal:])
                    obj.poids = poids

                #TODO : 15/11/23 : Normalement le champ 37 est de Longueur variable, mais le MOELLEUX D'ARINTHOD ne met pas de séparateur
                #⁼> Dans ce cas, je recherche si le champ '10 (Lot)' est disponible juste après 1 caractère
                if prefix=="37":
                    if code[1:3]=="10":
                        barcode_reste = code[1:]

                #Lot : Longueur variable => Prendre tout le reste
                if prefix=="10":
                    obj.lot = code.strip()
                    barcode_reste=False

                if barcode_reste:
                    obj.on_barcode_scanned(barcode_reste)

            if not barcode_reste:
                    unite = obj.product_id.uom_id.category_id.name
                    test=False
                    if unite=="Poids" and obj.poids>0:
                        test=True
                    if unite=="Poids" and obj.product_id.is_forcer_poids_colis:
                        test=True
                    if unite!="Poids":
                        test=True
                    if test:
                        obj.ajouter_ligne() #creation_lot=creation_lot)


    def maj_picking_action(self):
        for obj in self:
            obj.picking_id.move_line_ids_without_package.unlink()

            #** Ajoute des lignes sur la commande fournisseur *****************
            if obj.picking_id.purchase_id:
                products=[]
                for line in obj.picking_id.purchase_id.order_line:
                    if line.product_id not in products:
                        products.append(line.product_id)
                if products:
                    products_scan=[]
                    for line in obj.line_ids:
                        if line.product_id not in products:
                            if line.product_id not in products_scan:
                                products_scan.append(line.product_id)
                    if products_scan:
                        for product in products_scan:
                            vals={
                                'order_id'    : obj.picking_id.purchase_id.id,
                                'sequence'    : 9999,
                                'product_id'  : product.id,
                                'name'        : 'x',
                                'product_qty' : 0,
                                'product_uom' : product.uom_po_id.id,
                                'date_planned': str(date.today())+' 08:00:00',
                                'price_unit'  : 0,
                            }
                            order_line=self.env['purchase.order.line'].create(vals)
                            order_line.onchange_product_id()
                            order_line.product_qty = 0
                            order_line.onchange_product_qty_fromtome()
                            order_line.name = '## Ajouté en reception ##'
            #******************************************************************

            #** Ajout ligne sur commande client (31/07/2025) ******************
            lines_dict={}
            if obj.picking_id.sale_id:
                products=[]
                for line in obj.picking_id.sale_id.order_line:
                    if line.product_id not in products:
                        products.append(line.product_id)
                if products:
                    products_scan=[]
                    for line in obj.line_ids:
                        if line.product_id not in products:
                            if line.product_id not in products_scan:
                                products_scan.append(line.product_id)
                    if products_scan:
                        for product in products_scan:
                            vals={
                                "order_id"         : obj.picking_id.sale_id.id,
                                "product_id"       : product.id,
                                "sequence"         : 800,
                                "product_uom_qty"  : 0,
                            }
                            order_line = self.env['sale.order.line'].create(vals)
                            lines_dict[product] = order_line
                            #** Création d'un stock.move.line à 0 pour ajouter l'article sur le picking 
                            #   et faire le lien entre la ligne de commande et le stock.move
                            vals={
                                "picking_id"        : obj.picking_id.id,
                                "product_id"        : product.id,
                                "company_id"        : obj.picking_id.company_id.id,
                                "product_uom_id"    : line.product_id.uom_id.id,
                                "location_id"       : obj.picking_id.location_id.id,
                                "location_dest_id"  : obj.picking_id.location_dest_id.id,
                            }
                            res = self.env['stock.move.line'].create(vals)
                            res.move_id.sale_line_id = order_line.id


            #** jout des scans sur stock.move.line ****************************
            poids_net_total=0
            for line in obj.line_ids:
                poids_net_total+=line.poids
                unite = line.uom_id.category_id.name
                if unite=="Poids":
                    qty=line.poids
                else:
                    qty=line.nb_pieces
                vals={
                    "picking_id"        : obj.picking_id.id,
                    "product_id"        : line.product_id.id,
                    "lot_id"            : line.lot_id.id,
                    "company_id"        : obj.picking_id.company_id.id,
                    "product_uom_id"    : line.product_id.uom_id.id,
                    "location_id"       : obj.picking_id.location_id.id,
                    "location_dest_id"  : obj.picking_id.location_dest_id.id,
                    "qty_done"          : qty,
                    "is_nb_colis"       : line.nb_colis,
                    "is_poids_net_reel" : line.poids,
                }
                res = self.env['stock.move.line'].create(vals)
            #******************************************************************


            #** Ajout de la ligne "Frais de port" *****************************
            if obj.picking_id.sale_id.partner_id.is_frais_port_id:
                #** Vérification que le port est bien sur les lignes de la commande
                test = False
                for line in obj.picking_id.sale_id.order_line:
                    if line.product_id==obj.picking_id.sale_id.partner_id.is_frais_port_id and line.product_uom_qty>0:
                        test=True
                        break
                if test:
                    #** Calcul du poids si frais de port au kg ****************
                    product_uom = obj.picking_id.sale_id.partner_id.is_frais_port_id.uom_id
                    unite = product_uom.category_id.name
                    if unite=="Poids":
                        qty_done = poids_net_total
                    else:
                        qty_done = 1
                    #**********************************************************
                    vals={
                        "picking_id"        : obj.picking_id.id,
                        "product_id"        : obj.picking_id.sale_id.partner_id.is_frais_port_id.id,
                        "company_id"        : obj.picking_id.company_id.id,
                        "product_uom_id"    : product_uom.id,
                        "location_id"       : obj.picking_id.location_id.id,
                        "location_dest_id"  : obj.picking_id.location_dest_id.id,
                        "qty_done"          : qty_done,
                    }
                    res = self.env['stock.move.line'].create(vals)
            #******************************************************************
            obj.picking_id.move_ids_without_package._compute_is_nb_colis_poids()
            obj.picking_id._compute_is_alerte()


    def maj_inventory_action(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            obj.inventory_id.line_ids.unlink()
            SQL="""
                SELECT product_id, lot_id, sum(nb_pieces), sum(poids)
                FROM is_scan_picking_line
                WHERE scan_id=%s
                GROUP BY product_id, lot_id
            """
            cr.execute(SQL,[obj.id])
            for row in cr.fetchall():
                filtre=[
                    ('id','=', row[0]),
                ]
                product = self.env['product.product'].search(filtre,limit=1)
                qty=row[2]
                if product:
                    unite = product.uom_id.category_id.name
                    if unite=="Poids":
                        qty=row[3]
                vals={
                    "inventory_id"      : obj.inventory_id.id,
                    "product_id"        : row[0],
                    "prod_lot_id"       : row[1],
                    "company_id"        : 1,
                    "location_id"       : 8,
                    "product_qty"       : qty,
                }
                res = self.env['stock.inventory.line'].create(vals)


    def maj_code_ean_article_action(self):
        for obj in self:
            if obj.product_id and not obj.product_id.barcode:
                obj.product_id.barcode=obj.ean


class Picking(models.Model):
    _inherit = 'stock.picking'

    is_poids_net      = fields.Float(string='Poids net', digits='Stock Weight', compute='_compute_poids_colis', readonly=True, store=True)
    is_nb_colis       = fields.Float(string='Nb colis' , digits=(14,1)        , compute='_compute_poids_colis', readonly=True, store=True)
    is_date_livraison = fields.Date('Date livraison client', help="Date d'arrivée chez le client prévue sur la commande"    , related='sale_id.is_date_livraison')
    is_date_reception = fields.Datetime('Date réception'   , help="Date de réception chez Fromtome indiquée sur la commande", related='purchase_id.date_planned')
    is_enseigne_id    = fields.Many2one('is.enseigne.commerciale', 'Enseigne', related='partner_id.is_enseigne_id')
    is_transporteur_id = fields.Many2one('is.transporteur', 'Transporteur', compute='_compute_is_transporteur_id', store=True, readonly=False, tracking=True)
    is_transporteur_par_ordre = fields.Char('Transporteur par ordre', related='is_transporteur_id.transporteur_par_ordre', store=True, readonly=True)
    is_alerte          = fields.Text('Alerte', compute="_compute_is_alerte", readonly=True, store=False)
    is_preparation_transfert_id = fields.Many2one('is.preparation.transfert.entrepot', 'Préparation transfert', tracking=True)
    is_palette_europe  = fields.Integer(string='Palette Europe')
    is_palette_perdue  = fields.Integer(string='Palette Perdue')
    is_palette_demie   = fields.Integer(string='Palette Demie')


    @api.depends('partner_id','sale_id')
    def _compute_is_transporteur_id(self):
        for obj in self:
            obj.is_transporteur_id = obj.sale_id.is_transporteur_id.id or obj.partner_id.is_transporteur_id.id


    @api.depends('move_line_ids_without_package','is_palette_europe')
    def _compute_is_alerte(self):
        for obj in self:
            alertes=[]
            scans = self.env['is.scan.picking'].search([('picking_id','=',obj.id)],limit=1)
            date_scan=False
            poids_scan=False
            for scan in scans:
                if not date_scan:
                    date_scan=scan.write_date
                if date_scan<scan.write_date:
                    date_scan=scan.write_date
                for line in scan.line_ids:
                    unite = line.product_id.uom_id.category_id.name
                    if unite=="Poids":
                        poids_scan+=line.poids
            date_picking=False
            poids_picking=False
            for line in obj.move_ids_without_package:
                unite = line.product_id.uom_id.category_id.name
                if unite=="Poids":
                    poids_picking+=line.quantity_done
                    if round(line.quantity_done,4)!=round(line.is_poids_net_reel,4):
                        alertes.append("[%s] Poids net réel différent de Fait (%.4f!=%.4f)"%(line.product_id.default_code, line.is_poids_net_reel, line.quantity_done))

            for line in obj.move_line_ids_without_package:
                if not date_picking:
                    date_picking=line.write_date
                if date_picking<line.write_date:
                    date_picking=line.write_date
 
            if date_scan and date_picking:
                if date_scan>date_picking:
                    alertes.append("La 'Mise à jour du picking' n'a pas été faite, car le scan est plus récent que le picking")
            if poids_scan and poids_picking:
                if round(poids_scan,4)!=round(poids_picking,4):
                    alertes.append("Le poids du scan (%.2f) est différent du poids du picking (%.2f)"%(poids_scan,poids_picking))


            #** Recherche des lignes sans lien avec la commande de vente ******
            if obj.picking_type_id.code=='outgoing':
                for move in obj.move_ids_without_package:
                    if not move.sale_line_id and move.state!='cancel':
                        alertes.append("Article '%s' sans lien avec la commande et donc ne sera pas facturé"%(move.product_id.name))
            #******************************************************************


            obj.is_alerte = '\n'.join(alertes) or False


    @api.depends('move_line_ids_without_package','move_line_ids_without_package.is_poids_net_reel','move_line_ids_without_package.is_nb_colis','state')
    def _compute_poids_colis(self):
        for obj in self:
            poids=0
            colis=0
            for line in obj.move_line_ids_without_package:
                poids+=line.is_poids_net_reel
                colis+=line.is_nb_colis
            obj.is_poids_net=poids
            obj.is_nb_colis=colis


    def solde_commande_action(self):
        domain=[
            ('is_commande_soldee', '=', False),
            ('state'             , '=', 'sale'),
        ]
        orders = self.env['sale.order'].search(domain)
        orders.commande_soldee_action_server()

        domain=[
            ('is_commande_soldee', '=', False),
            ('state'             , '=', 'purchase'),
        ]
        orders = self.env['purchase.order'].search(domain)
        orders.commande_soldee_action_server()


    def action_picking_send(self):
        self.ensure_one()
        template = self.env.ref(
            'is_fromtome14.email_template_stock_picking',
            False,
        )
        compose_form = self.env.ref(
            'mail.email_compose_message_wizard_form',
            False,
        )
        ctx = dict(
            default_model='stock.picking',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
            user_id=self.env.user.id,
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }


    # def action_picking_send_direct(self):
    #     """Envoie directement le mail du BL sans afficher le wizard.
    #     L'expéditeur est le user_id du partner_id du picking.
    #     """
    #     self.ensure_one()
    #     template = self.env.ref(
    #         'is_fromtome14.email_template_stock_picking',
    #         False,
    #     )
    #     if not template:
    #         raise UserError(_("Le modèle de mail 'email_template_stock_picking' n'a pas été trouvé."))
        
    #     # Récupérer l'utilisateur lié au partenaire du picking (user_id du partner_id)
    #     sender_user = self.partner_id.user_id if self.partner_id and self.partner_id.user_id else self.env.user
        
    #     # Construire le contexte avec l'utilisateur expéditeur
    #     ctx = dict(
    #         self.env.context,
    #         user_id=sender_user,
    #     )
        
    #     # Envoyer le mail avec le template
    #     template.with_context(ctx).send_mail(
    #         self.id,
    #         force_send=True,
    #         email_values={
    #             'email_from': sender_user.email or self.company_id.email or '',
    #         }
    #     )
        
    #     # Message de confirmation dans le chatter
    #     self.message_post(body=_("BL envoyé par mail à %s (expéditeur: %s)") % (
    #         self.partner_id.email or self.partner_id.name,
    #         sender_user.email or sender_user.name,
    #     ))
        
    #     return True


    def scan_picking_action(self):
        for obj in self:
            products={}
            for line in obj.move_ids_without_package:
                nb_colis=line.get_nb_colis()
                if line.product_id not in products:
                    products[line.product_id]=[0,0]
                products[line.product_id][0]+=line.product_uom_qty
                products[line.product_id][1]+=nb_colis
            scans = self.env['is.scan.picking'].search([('picking_id','=',obj.id)],limit=1)
            if scans:
                scan=scans[0]
            else:
                vals={
                    "picking_id": obj.id,
                }
                scan=self.env['is.scan.picking'].create(vals)
            scan.product_ids.unlink()
            for product in products:
                vals={
                    "scan_id"    : scan.id,
                    "product_id" : product.id,
                    "nb_pieces"  : products[product][0],
                    "nb_colis"   : products[product][1],
                }
                res = self.env['is.scan.picking.product'].create(vals)


            context = dict(self.env.context)
            context['form_view_initial_mode'] = 'edit'
            res= {
                'name': 'Scan',
                'view_mode': 'form',
                'res_model': 'is.scan.picking',
                'type': 'ir.actions.act_window',
                'res_id': scan.id,
                'context': context,
            }
            return res


    def init_sale_order_action(self):
        for obj in self:
            if obj.picking_type_id.code=='outgoing' and not  obj.sale_id:
                for move in obj.move_ids_without_package:
                    if move.sale_line_id:
                        sale_id = move.sale_line_id.order_id.id
                        obj.sale_id = sale_id
                        break


    def trier_par_emplacement_fournisseur(self):
        for obj in self:            
            moves = self.env['stock.move'].search([('picking_id','=',obj.id)])
            for move in moves:
                move.is_fournisseur_id          = move.product_id.is_fournisseur_id
                move.is_emplacement_fournisseur = move.product_id.is_fournisseur_id.is_emplacement_fournisseur
                move.is_poids_net_colis         = move.product_id.is_poids_net_colis
            moves = self.env['stock.move'].search([('picking_id','=',obj.id)],order="is_emplacement_fournisseur,is_poids_net_colis desc, product_id")
            sequence=10
            for move in moves:
                move.sequence=sequence
                sequence+=10


    def trier_par_designation_action(self):
        for obj in self:
            my_dict={}
            for move in obj.move_ids_without_package:
                if move.product_id.default_code:
                    name=move.product_id.name
                else:
                    name="zzzz"
                key="%s-%s"%(name, move.id)
                my_dict[key]=move
            sorted_dict = dict(sorted(my_dict.items()))
            sequence=10
            for key in sorted_dict:
                move=sorted_dict[key]
                move.sequence=sequence
                sequence+=10


    def trier_par_ref_fromtome_action(self):
        for obj in self:
            my_dict={}
            for move in obj.move_ids_without_package:
                key="%s-%s"%(move.product_id.default_code or 'zzzz', move.id)
                my_dict[key]=move
            sorted_dict = dict(sorted(my_dict.items()))
            sequence=10
            for key in sorted_dict:
                move=sorted_dict[key]
                move.sequence=sequence
                sequence+=10


    def trier_par_ref_fournisseur_action(self):
        for obj in self:
            my_dict={}
            for move in obj.move_ids_without_package:
                key="%s-%s"%(move.is_ref_fournisseur or 'zzzz', move.id)
                my_dict[key]=move
            sorted_dict = dict(sorted(my_dict.items()))
            sequence=10
            for key in sorted_dict:
                move=sorted_dict[key]
                move.sequence=sequence
                sequence+=10


    def trier_par_poids_action(self):
        for obj in self:
            my_dict={}
            for move in obj.move_ids_without_package:
                poids=str(int(move.product_id.is_poids_net_colis*100000)).zfill(10)
                key="%s-%s"%(poids, move.id)
                my_dict[key]=move
            sorted_dict = dict(sorted(my_dict.items(),reverse=True))
            sequence=10
            for key in sorted_dict:
                move=sorted_dict[key]
                move.sequence=sequence
                sequence+=10


    def _message_auto_subscribe_notify(self, partner_ids, template):
        "Désactiver les notifications d'envoi des mails"
        return True


    def voir_picking_action(self):
        for obj in self:
            res= {
                'name': 'Picking',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_model': 'stock.picking',
                'type': 'ir.actions.act_window',
                'res_id':obj.id,
            }
            return res


    def action_print_prepa_and_palette_combined(self):
        """
        Méthode pour fusionner les PDF de la fiche prépa et de la fiche palette
        et retourner le résultat combiné (pour un ou plusieurs pickings)
        """
        return self.action_print_multiple_prepa_and_palette_combined()

    def action_print_multiple_prepa_and_palette_combined(self):
        """
        Méthode pour fusionner les PDF de plusieurs fiches prépa et palette
        et retourner le résultat combiné
        """
        if not PdfWriter or not PdfReader:
            raise UserError(_("PyPDF2 n'est pas installé. Veuillez l'installer pour fusionner les PDF."))
        
        if not self:
            raise UserError(_("Aucune livraison sélectionnée."))
        
        all_pdfs = []
        
        for picking in self:
            # Générer le PDF de la fiche prépa pour ce picking
            prepa_report = self.env.ref('stock.action_report_picking')
            prepa_pdf, _ = prepa_report._render_qweb_pdf([picking.id])
            all_pdfs.append(prepa_pdf)
            
            # Générer le PDF de la fiche palette pour ce picking
            palette_report = self.env.ref('is_fromtome14.action_report_fiche_palette')
            palette_pdf, _ = palette_report._render_qweb_pdf([picking.id])
            all_pdfs.append(palette_pdf)
        
        # Fusionner tous les PDF
        merged_pdf = self._merge_multiple_pdfs(all_pdfs)
        
        # Créer l'attachement et retourner l'action pour l'afficher
        picking_names = "_".join([p.name for p in self[:3]])  # Limiter à 3 noms pour éviter un nom trop long
        if len(self) > 3:
            picking_names += f"_et_{len(self)-3}_autres"
        elif len(self) == 1:
            picking_names = self.name
            
        attachment = self.env['ir.attachment'].create({
            'name': f'Fiche{"s" if len(self) > 1 else ""}_Prepa_Palette_{picking_names}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(merged_pdf),
            'res_model': self._name,
            'res_id': self.id if len(self) == 1 else False,
            'mimetype': 'application/pdf'
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
    
    def _merge_multiple_pdfs(self, pdf_data_list):
        """
        Fusionner plusieurs PDF en un seul
        """
        output = PdfWriter()
        
        for pdf_data in pdf_data_list:
            pdf_stream = io.BytesIO(pdf_data)
            pdf_reader = PdfReader(pdf_stream)
            
            # Compatibilité avec différentes versions de PyPDF2
            if hasattr(pdf_reader, 'pages'):
                pages = pdf_reader.pages
            else:
                pages = [pdf_reader.getPage(i) for i in range(pdf_reader.getNumPages())]
                
            for page in pages:
                if hasattr(output, 'add_page'):
                    output.add_page(page)
                else:
                    output.addPage(page)
        
        # Retourner le PDF fusionné
        merged_stream = io.BytesIO()
        output.write(merged_stream)
        merged_stream.seek(0)
        return merged_stream.read()
    

class PickingType(models.Model):
    _inherit = 'stock.picking.type'


    def _compute_picking_count(self):
        domains = {
            'count_picking_draft': [('state', '=', 'draft')],
            'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting'))],
            'count_picking_ready': [('state', '=', 'assigned')],
            'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed'))],
            'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed'))],
            'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting'))],
        }
        for field in domains:
            data = self.env['stock.picking'].read_group(domains[field] +
                [('state', 'not in', ('done', 'cancel')), ('picking_type_id', 'in', self.ids)],
                ['picking_type_id'], ['picking_type_id'])
            count = {
                x['picking_type_id'][0]: x['picking_type_id_count']
                for x in data if x['picking_type_id']
            }
            for record in self:
                record[field] = count.get(record.id, 0)
        for record in self:
            record.rate_picking_backorders = record.count_picking and record.count_picking_backorders * 100 / record.count_picking or 0
            now = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)[:10]
            filtre=[]
            if record.id==1:
                filtre=[
                    ('is_date_reception'  ,'<', now),
                    ('picking_type_id'  ,'=', record.id),
                    ('state', 'in', ('assigned', 'waiting', 'confirmed')),
                ]
            if record.id==2:
                filtre=[
                    ('is_date_livraison'  ,'<', now),
                    ('picking_type_id'  ,'=', record.id),
                    ('state', 'in', ('assigned', 'waiting', 'confirmed')),
                ]
            pickings=self.env['stock.picking'].search(filtre)
            record.count_picking_late = len(pickings)


    def get_action_picking_tree_late(self):
        now = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)[:10]
        filtre=[]
        if self.id==1:
            filtre=[
                ('is_date_reception'  ,'<', now),
                ('picking_type_id'  ,'=', self.id),
                ('state', 'in', ('assigned', 'waiting', 'confirmed')),
            ]
        if self.id==2:
            filtre=[
                ('is_date_livraison'  ,'<', now),
                ('picking_type_id'  ,'=', self.id),
                ('state', 'in', ('assigned', 'waiting', 'confirmed')),
            ]
        pickings=self.env['stock.picking'].search(filtre)
        ids=[]
        for picking in pickings:
            ids.append(picking.id)
        res= {
            'name': 'Retard',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'domain': [
                ('id','in',ids),
            ],
        }
        return res

