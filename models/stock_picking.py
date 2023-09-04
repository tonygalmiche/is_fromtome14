# -*- coding: utf-8 -*-
from odoo import fields, api, models, _
import time
from datetime import datetime
from dateutil.parser import parse
import dateparser
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, format_datetime
from datetime import datetime
from datetime import timedelta
import pytz
import logging

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
            if obj.lot_id and obj.lot_id.is_dlc_ddm:
                now = datetime.now().date()
                if obj.lot_id.is_dlc_ddm<now:
                    alertes.append("DLC/DDM dépassée")
                if obj.product_id:
                    contrats = self.env['contrat.date.client'].search([('product_id', '=',obj.product_id.product_tmpl_id.id)])
                    for contrat in contrats:
                        if not contrat.partner_id:
                            date_limite = obj.lot_id.is_dlc_ddm-timedelta(days=contrat.name)
                            if date_limite<=now:
                                alertes.append("Contrat date de %s jours dépassé (Date limite=%s)"%(contrat.name,date_limite.strftime('%d/%m/%Y')))
                        else:
                            if obj.scan_id.picking_id:
                                if  obj.scan_id.picking_id.partner_id==contrat.partner_id:
                                    date_limite = obj.lot_id.is_dlc_ddm-timedelta(days=contrat.name)
                                    alertes.append("Contrat date client de %s jours dépassé (Date limite=%s)"%(contrat.name,date_limite.strftime('%d/%m/%Y')))
            obj.alerte = '\n'.join(alertes) or False


    @api.depends('product_id')
    def _compute_product_name(self):
        for obj in self:
            obj.product_name = obj.product_id.name

    scan_id             = fields.Many2one('is.scan.picking', 'Picking', required=True, ondelete='cascade')
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


    @api.depends('ean','lot','product_id','lot_id')
    def _compute_is_alerte(self):
        for obj in self:
            alertes=[]
            if obj.ean and not obj.product_id:
                alertes.append("Article non trouvé pour ce code ean")
            obj.is_alerte = '\n'.join(alertes) or False
            if obj.lot and not obj.lot_id:
                alertes.append("Lot non trouvé")
            obj.is_alerte = '\n'.join(alertes) or False

    @api.onchange('ajouter')
    def _onchange_ajouter(self):
        for obj in self:
            obj.ajouter_ligne()

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        for obj in self:
            obj.dlc_ddm = obj.lot_id.is_dlc_ddm

    @api.onchange('product_id')
    def _onchange_product_id(self):
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


    def ajouter_ligne(self, creation_lot=False):
        for obj in self:
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
            creation_lot=False
            code   = str(barcode)[2:]
            prefix = str(barcode)[:2]
            if prefix in ("01","02"):
                obj.reset_scan()
                obj.ean = code
                products = self.env['product.product'].search([('barcode', '=',code)])
                for product in products:
                    obj.product_id = product.id
            if prefix=="10":
                obj.lot = code.strip()
            if prefix in ["15","17"]:
                date = dateparser.parse(code, date_formats=['%y%m%d'])
                obj.dlc_ddm = date.strftime('%Y-%m-%d')
            if prefix=="31":
                decimal = int(str(barcode)[3])
                poids    = float(str(barcode)[4:-decimal] + '.' + str(barcode)[-decimal:])
                obj.poids = poids

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
            obj.ajouter_ligne(creation_lot=creation_lot)


    def maj_picking_action(self):
        for obj in self:
            obj.picking_id.move_line_ids_without_package.unlink()
            for line in obj.line_ids:
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

            #** Ajout de la ligne "Frais de port" *****************************
            if obj.picking_id.sale_id.partner_id.is_frais_port_id:
                #** Vérification que le port est bien sur les lignes de la commande
                test = False
                for line in obj.picking_id.sale_id.order_line:
                    if line.product_id==obj.picking_id.sale_id.partner_id.is_frais_port_id:
                        test=True
                        break
                if test:
                    vals={
                        "picking_id"        : obj.picking_id.id,
                        "product_id"        : obj.picking_id.sale_id.partner_id.is_frais_port_id.id,
                        "company_id"        : obj.picking_id.company_id.id,
                        "product_uom_id"    : obj.picking_id.sale_id.partner_id.is_frais_port_id.uom_id.id,
                        "location_id"       : obj.picking_id.location_id.id,
                        "location_dest_id"  : obj.picking_id.location_dest_id.id,
                        "qty_done"          : 1,
                    }
                    res = self.env['stock.move.line'].create(vals)
            #******************************************************************


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


    @api.depends('move_line_ids_without_package','state')
    def _compute_poids_colis(self):
        for obj in self:
            poids=0
            colis=0
            for line in obj.move_line_ids_without_package:
                poids+=line.is_poids_net_reel
                colis+=line.is_nb_colis
            obj.is_poids_net=poids
            obj.is_nb_colis=colis
            if obj.sale_id:
                obj.sale_id.commande_soldee_action_server()
            if obj.purchase_id:
                obj.purchase_id.commande_soldee_action_server()


    is_poids_net      = fields.Float(string='Poids net', digits='Stock Weight', compute='_compute_poids_colis')
    is_nb_colis       = fields.Float(string='Nb colis' , digits=(14,1)        , compute='_compute_poids_colis')
    is_date_livraison = fields.Date('Date livraison client', help="Date d'arrivée chez le client prévue sur la commande"    , related='sale_id.is_date_livraison')
    is_date_reception = fields.Datetime('Date réception'   , help="Date de réception chez Fromtome indiquée sur la commande", related='purchase_id.date_planned')
    is_enseigne_id    = fields.Many2one('is.enseigne.commerciale', 'Enseigne', related='partner_id.is_enseigne_id')
    is_transporteur_id = fields.Many2one(related='partner_id.is_transporteur_id')


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



