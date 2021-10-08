# -*- coding: utf-8 -*-
from odoo import fields, api, models, _
import time
from datetime import datetime
from dateutil.parser import parse
import dateparser
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero
from datetime import datetime
from datetime import timedelta
import pytz
import logging


class IsScanPickingLine(models.Model):
    _name = 'is.scan.picking.line'
    _description = "Lignes Scan Picking"
    _order='id'

    scan_id             = fields.Many2one('is.scan.picking', 'Picking', required=True, ondelete='cascade')
    product_id          = fields.Many2one('product.product', 'Article', required=True)
    uom_id              = fields.Many2one('uom.uom', 'Unité', related='product_id.uom_id')
    nb_pieces_par_colis = fields.Integer(string='Nb Pièces / colis', related="product_id.is_nb_pieces_par_colis")
    lot_id            = fields.Many2one('stock.production.lot', 'Lot', required=True)
    type_tracabilite  = fields.Selection(string='Traçabilité', related="product_id.is_type_tracabilite")
    dlc_ddm           = fields.Date('DLC / DDM', related="lot_id.is_dlc_ddm")
    nb_pieces         = fields.Float('Pièces'   , digits=(14,2), help="Nb pièces scannées")
    nb_colis          = fields.Float('Colis'    , digits=(14,2), help="Nb Colis scannés")
    nb_colis_prevues  = fields.Float('Prévu'    , digits=(14,2), help="Nb Colis prévus")
    nb_colis_reste    = fields.Float('Reste'    , digits=(14,2), help="Nb Colis reste")
    poids             = fields.Float("Poids"    , digits=(14,4))
    info              = fields.Char("Info")


class IsScanPickingLine(models.Model):
    _name = 'is.scan.picking.product'
    _description = "Articles à scanner du Picking"
    _order='id'

    scan_id    = fields.Many2one('is.scan.picking', 'Picking', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', 'Article', required=True)
    nb_pieces  = fields.Float('Nb pièces prévues', digits=(14,2))
    uom_id     = fields.Many2one('uom.uom', 'Unité', related='product_id.uom_id')
    nb_colis   = fields.Float('Nb colis prévus', digits=(14,2))


class IsScanPicking(models.Model):
    _name = 'is.scan.picking'
    _inherit = 'barcodes.barcode_events_mixin'
    _description = "Scan Picking"
    _order='id desc'
    _rec_name = 'id'


    @api.depends('ean','lot','product_id','lot_id')
    def _compute_is_alerte(self):
        for obj in self:
            print(obj)
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


    picking_id = fields.Many2one('stock.picking', 'Picking', required=True)
    ean        = fields.Char("EAN")
    product_id = fields.Many2one('product.product', 'Article')
    lot        = fields.Char("Lot scanné")
    lot_id     = fields.Many2one('stock.production.lot', 'Lot')
    type_tracabilite = fields.Selection(string='Traçabilité', related="product_id.is_type_tracabilite")
    dlc_ddm          = fields.Date('DLC / DDM')
    poids       = fields.Float("Poids")
    ajouter     = fields.Boolean("Ajouter", help="Ajouter cette ligne")
    is_alerte   = fields.Text('Alerte', compute=_compute_is_alerte, readonly=True, store=False)
    line_ids    = fields.One2many('is.scan.picking.line', 'scan_id', 'Lignes')
    product_ids = fields.One2many('is.scan.picking.product', 'scan_id', 'Articles')


    def reset_scan(self):
        for obj in self:
            obj.ean        = False
            obj.product_id = False
            obj.lot        = False
            obj.lot_id     = False
            obj.dlc_ddm    = False
            obj.poids      = False


    def ajouter_ligne(self):
        for obj in self:
            if obj.product_id and obj.lot_id and obj.dlc_ddm:
                nb_pieces=obj.product_id.is_nb_pieces_par_colis


                #** Recherche de la quantité prévue ***************************
                prevu=0.0
                for line in obj.product_ids:
                    if line.product_id==obj.product_id:
                        prevu=line.nb_colis
                #**************************************************************

                #** Recherche quantité scannée ********************************
                products={}
                scanne=1
                for line in obj.line_ids:
                    if line.product_id==obj.product_id:
                        scanne+=line.nb_colis
                reste=prevu-scanne
                #**************************************************************

                tz = pytz.timezone('Europe/Paris')
                now = datetime.now(tz).strftime("%H:%M:%S")
                poids = obj.poids or obj.product_id.is_poids_net_colis
                vals={
                    "product_id": obj.product_id.id,
                    "lot_id"    : obj.lot_id.id,
                    "nb_pieces" : nb_pieces,
                    "nb_colis"  : 1,
                    "nb_colis_prevues": prevu,
                    "nb_colis_reste"  : reste,
                    "poids"     : poids,
                    "info"      : now,
                }
                obj.write({"line_ids": [(0,0,vals)]})
                obj.reset_scan()


    def on_barcode_scanned(self, barcode):
        for obj in self:
            code   = str(barcode)[2:]
            prefix = str(barcode)[:2]
            if prefix in ("01","02"):
                obj.reset_scan()
                obj.ean = code
                products = self.env['product.product'].search([('barcode', '=',code)])
                for product in products:
                    obj.product_id = product.id
            if prefix=="10":
                obj.lot = code
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
                        "company_id": obj.picking_id.company_id.id,
                        "name"      : obj.lot,
                        "product_id": obj.product_id.id,
                        "is_dlc_ddm": obj.dlc_ddm,
                    }
                    lot = self.env['stock.production.lot'].create(vals)
                    lot_id = lot.id
                obj.lot_id = lot_id
            obj.ajouter_ligne()


    def maj_picking_action(self):
        for obj in self:
            print(obj)
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


class Picking(models.Model):
    _name = 'stock.picking'
    _inherit = 'stock.picking'

    # @api.depends('state')
    # def _compute_is_scan_vsb(self):
    #     for obj in self:
    #         vsb = False
    #         if obj.state=='assigned':
    #             vsb=True
    #         obj.is_scan_vsb=vsb
    # is_scan_vsb = fields.Boolean(string=u'Scan', compute='_compute_is_scan_vsb', readonly=True, store=False)


    @api.depends('move_line_ids_without_package')
    def _compute_poids_colis(self):
        for obj in self:
            poids=0
            colis=0
            for line in obj.move_line_ids_without_package:
                poids+=line.is_poids_net_reel
                colis+=line.is_nb_colis
            obj.is_poids_net=poids
            obj.is_nb_colis=colis

    is_poids_net = fields.Float(string='Poids net', digits=(14,3), compute='_compute_poids_colis')
    is_nb_colis  = fields.Float(string='Nb colis' , digits=(14,1), compute='_compute_poids_colis')


    def scan_picking_action(self):
        for obj in self:


            products={}
            for line in obj.move_ids_without_package:
                print(line)

                nb_colis=line.get_nb_colis()

                
                if line.product_id not in products:
                    products[line.product_id]=[0,0]
                products[line.product_id][0]+=line.product_uom_qty
                products[line.product_id][1]+=nb_colis
            print(products)

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
            #context['default_company_id'] = obj.company_id.id,
            res= {
                'name': 'Scan',
                'view_mode': 'form',
                'res_model': 'is.scan.picking',
                'type': 'ir.actions.act_window',
                'res_id': scan.id,
                'context': context,
            }
            return res


        #<field name="context">{'display_complete': True, 'default_company_id': allowed_company_ids[0]}</field>


    # @api.onchange('move_ids_without_package')
    # def _compute_is_alerte(self):
    #     print(self)
    #     for obj in self:
    #         obj.is_alerte=str(len(obj.move_ids_without_package))
    #         alerte=[]
    #         for line in obj.move_ids_without_package:
    #             if line.is_alerte:
    #                 alerte.append(line.is_alerte)
    #         if len(alerte)>0:
    #             alerte='\n'.join(alerte)
    #         else:
    #             alerte=False
    #         obj.is_alerte=alerte
    #         obj.is_info=False


    # is_alerte  = fields.Text('Alerte', copy=False, compute=_compute_is_alerte)
    # is_info    = fields.Text('Info'  , copy=False, compute=_compute_is_alerte)
    # is_user_id = fields.Many2one('res.users', string="Responsable", related="sale_id.user_id")
    #team_id = fields.Many2one('crm.team', 'Equipe Commerciale', related="sale_id.team_id")

    #@api.multi
    #def do_print_pickingorder(self):
    #    self.write({'printed': True})
    #    return self.env.ref('stock.action_report_delivery').report_action(self)





    # scans=[]
    # def _add_product(self, product, barcode, qty=1.0):
    #     is_scan_qty = 1
    #     tz = pytz.timezone('Europe/Paris')
    #     paris_now = datetime.now(tz).strftime("%H:%M:%S")
    #     line = self.move_ids_without_package.filtered(lambda r: r.product_id.id == product.id)
    #     if len(line)>1:
    #         raise UserError("Il y a 2 lignes sur l'article %s"%(line[0].product_id.default_code))
    #     if line.move_line_ids:
    #         line.move_line_ids[0].write({'weight_uom_id': line.product_id.weight_uom_id.id})
    #     if str(barcode)[:2] in ("01","02"):
    #         if line.show_details_visible:
    #             line.is_quantity_done_editable = True
    #         if line:
    #             if line.reserved_availability >= line.quantity_done+qty:
    #                 if line.is_colis:
    #                     line.move_line_ids[0].qty_done += qty
    #                     line.move_line_ids[0].split_qty()
    #                 else:
    #                     if product.uom_id.category_id.name=="Pièce":
    #                         line.move_line_ids[0].qty_done += qty
    #                     else:
    #                         weight = line.product_id.uom_po_id.factor_inv
    #                         line.move_line_ids[0].qty_done += weight
    #                     line.move_line_ids[0].split_qty()


    #                 message = "%s : %s : qt=%s " % (paris_now, product.name, line.quantity_done)
    #                 self.is_info=message
    #             else:
    #                 message = "%s : %s : qt=%s : Quantité réservée de %s atteinte " % (paris_now, product.name, line.quantity_done, line.reserved_availability)
    #                 self.is_alerte = message
    #                 self.is_info   = False
    #         else:
    #             message = "L'article %s n'est pas sur ce document !" %  product.name_get()[0][1]
    #             self.is_alerte = message
    #     else:
    #         code = str(barcode)[2:]
    #         n=len(line.move_line_ids)-1
    #         if n>0:
    #             if str(barcode)[:2] in ("10"):
    #                 if product:
    #                     if product.uom_id.category_id.name=="Pièce":
    #                         qty=product.uom_id.factor_inv or 1
    #                         if qty <1:
    #                             qty=1
    #                         line.move_line_ids[n].write({'weight': qty*is_scan_qty})
    #                 line.move_line_ids[n].write({'lot_name' : code} )
    #                 lot = self.env['stock.production.lot'].search([('name','=',code),('product_id','=',product.id)],limit=1)
    #                 if lot:
    #                     message = "Lot numéro  %s'" % (lot.name)
    #                 else:
    #                     lot = self.env['stock.production.lot'].create(
    #                         {'name': code, 'product_id': product.id}
    #                     )
    #                     message = "Création lot %s" % (lot.name)
    #                 picking_id = line.move_line_ids[0].picking_id.id
    #                 line.move_line_ids[n].write({'picking_id': picking_id,'lot_id': lot.id})

    #                 if self.is_info:
    #                     self.is_info+=" : "+message
    #                 else:
    #                     self.is_info=message

    #             elif str(barcode)[:2] in ("15"):
    #                 date_due = dateparser.parse(code, date_formats=['%y%m%d'])
    #                 contrat_date_obj = self.env['contrat.date.client'].search(
    #                     [('partner_id', '=', self.partner_id.id),
    #                      ('product_id', '=', product.product_tmpl_id.id)], limit=1)
    #                 contrat_date = datetime.now() + timedelta(days=contrat_date_obj.name)
    #                 if contrat_date_obj and contrat_date.date() > date_due.date():
    #                     raise UserError(_('Verifiez Contrat date du client !'))
    #                 elif date_due and date_due.date() < datetime.now().date():
    #                     raise UserError(_('Produit expiré !'))
    #                 elif date_due and date_due.date() == datetime.now().date():
    #                     raise UserError(_('Vérifiez date expiration produit !'))

    #                 line.move_line_ids[n].write({"life_use_date": date_due} )
    #                 line.move_line_ids[n].lot_id.write({"use_date": date_due})

    #             elif str(barcode)[:2] in ("17"):
    #                 life_use_date = dateparser.parse(code, date_formats=['%y%m%d'])
    #                 line.move_line_ids[n].write({"life_use_date" : life_use_date})
    #                 line.move_line_ids[n].lot_id.write({"life_date": life_use_date})

    #             elif str(barcode)[:2] in ("31"):
    #                 decimal = int(str(barcode)[3])
    #                 code = float(str(barcode)[4:-decimal] + '.' + str(barcode)[-decimal:])
    #                 if line.move_line_ids[n].weight_uom_id.category_id.name == "Poids":
    #                     if not line.is_colis:
    #                         vals={
    #                             "qty_done"       : code,
    #                             "weight"         : code * line.move_line_ids[n].product_uom_qty,
    #                         }
    #                     else:
    #                         qt = code * line.move_line_ids[n].product_uom_qty
    #                         vals={
    #                             "qty_done"       : 1,
    #                             "weight"         : qt,
    #                         }
    #                     line.move_line_ids[n].write(vals)
    #                 else:
    #                     product_weight = code * line.move_line_ids[n].product_uom_qty
    #                     line.move_line_ids[n].write({'product_weight': product_weight})
    #                 line._cal_move_weight()
    #     return True


    # def on_barcode_scanned(self, barcode):
    #     self.scans.append(barcode)
    #     if self.state not in ['assigned']:
    #         self.is_alerte="Le BL doit-être à l'état Prêt !"
    #         return
    #     if str(barcode)[:2] in ("01","02"):
    #         self.barcode_product_id = False
    #         pr_barcode =  str(barcode)[2:]
    #         product = self.env['product.product'].search([('barcode', '=',pr_barcode)])
    #         if product:
    #             self._add_product(product, barcode)
    #             self.barcode_product_id =  product.id
    #         else:
    #             self.barcode_product_id = False
    #             self.is_alerte="Code EAN %s non trouvé" % pr_barcode
    #             return
    #     if self.barcode_product_id and str(barcode)[:2] in ('10','15','17','31','37'):
    #         self._add_product(self.barcode_product_id, barcode)



    #TODO : A revoir
    # def button_validate(self):
    #     self.ensure_one()
    #     if not self.move_lines and not self.move_line_ids:
    #         raise UserError(_('Please add some items to move.'))

    #     picking_type = self.picking_type_id
    #     precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
    #     no_quantities_done = all(float_is_zero(move_line.qty_done, precision_digits=precision_digits) for move_line in
    #                              self.move_line_ids.filtered(lambda m: m.state not in ('done', 'cancel')))
    #     no_reserved_quantities = all(
    #         float_is_zero(move_line.product_qty, precision_rounding=move_line.product_uom_id.rounding) for move_line in
    #         self.move_line_ids)
    #     if no_reserved_quantities and no_quantities_done:
    #         print('You cannot validate a transfer if no quantites are reserved nor done. To force the transfer, switch in edit more and encode the done quantities.')

    #     if picking_type.use_create_lots or picking_type.use_existing_lots:
    #         lines_to_check = self.move_line_ids
    #         if not no_quantities_done:
    #             lines_to_check = lines_to_check.filtered(
    #                 lambda line: float_compare(line.qty_done, 0,
    #                                            precision_rounding=line.product_uom_id.rounding)
    #             )

    #         for line in lines_to_check:
    #             product = line.product_id
    #             if product and product.tracking != 'none':
    #                 if not line.lot_name and not line.lot_id:
    #                     print('You need to supply a Lot/Serial number for product  in ean picking module')

    #     if no_quantities_done:
    #         view = self.env.ref('stock.view_immediate_transfer')
    #         wiz = self.env['stock.immediate.transfer'].create({'pick_ids': [(4, self.id)]})
    #         return {
    #             'name': _('Immediate Transfer?'),
    #             'type': 'ir.actions.act_window',
    #             'view_type': 'form',
    #             'view_mode': 'form',
    #             'res_model': 'stock.immediate.transfer',
    #             'views': [(view.id, 'form')],
    #             'view_id': view.id,
    #             'target': 'new',
    #             'res_id': wiz.id,
    #             'context': self.env.context,
    #         }

    #     if self._get_overprocessed_stock_moves() and not self._context.get('skip_overprocessed_check'):
    #         view = self.env.ref('stock.view_overprocessed_transfer')
    #         wiz = self.env['stock.overprocessed.transfer'].create({'picking_id': self.id})
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'view_type': 'form',
    #             'view_mode': 'form',
    #             'res_model': 'stock.overprocessed.transfer',
    #             'views': [(view.id, 'form')],
    #             'view_id': view.id,
    #             'target': 'new',
    #             'res_id': wiz.id,
    #             'context': self.env.context,
    #         }

    #     if self._check_backorder():
    #         return self.action_generate_backorder_wizard()
    #     self.action_done()
    #     return



#TODO : A revoir
# class StockMoveLine(models.Model):
#     _inherit = "stock.move.line"

#     @api.onchange('qty_done','product_uom_qty')
#     def delete_line_qty_zero(self):

#         print("#### delete_line_qty_zero ####",self,self.product_uom_qty)

#         if self.product_uom_qty == 0:
#             self.unlink()

#     @api.constrains('lot_id', 'product_id')
#     def _check_lot_product(self):
#         for line in self:
#             if line.lot_id and line.product_id != line.lot_id.product_id:
#                 print('this lot is incompatible with this product .')

#     @api.multi
#     def write(self, vals):
#         res=super(StockMoveLine, self).write(vals)
#         for obj in self:
#             if obj.product_id and obj.lot_id and obj.life_use_date:
#                 if not obj.lot_id.use_date and not obj.lot_id.life_date:
#                     print("### StockMoveLine ### obj=",obj)
#                     if obj.lot_id.type_traçabilite=="ddm":
#                         obj.lot_id.write({"use_date": obj.life_use_date})
#                     else:
#                         obj.lot_id.write({"life_date": obj.life_use_date})
#         return res



#TODO : A revoir
# class StockQuant(models.Model):
#     _inherit = 'stock.quant'
#     @api.model
#     def _update_reserved_quantity(self, product_id, location_id, quantity, lot_id=None, package_id=None, owner_id=None,
#                                   strict=False):
#         """ Increase the reserved quantity, i.e. increase `reserved_quantity` for the set of quants
#         sharing the combination of `product_id, location_id` if `strict` is set to False or sharing
#         the *exact same characteristics* otherwise. Typically, this method is called when reserving
#         a move or updating a reserved move line. When reserving a chained move, the strict flag
#         should be enabled (to reserve exactly what was brought). When the move is MTS,it could take
#         anything from the stock, so we disable the flag. When editing a move line, we naturally
#         enable the flag, to reflect the reservation according to the edition.

#         :return: a list of tuples (quant, quantity_reserved) showing on which quant the reservation
#             was done and how much the system was able to reserve on it
#         """
#         self = self.sudo()
#         rounding = product_id.uom_id.rounding
#         quants = self._gather(product_id, location_id, lot_id=lot_id, package_id=package_id, owner_id=owner_id,
#                               strict=strict)
#         reserved_quants = []

#         if float_compare(quantity, 0, precision_rounding=rounding) > 0:
#             available_quantity = self._get_available_quantity(product_id, location_id, lot_id=lot_id,
#                                                               package_id=package_id, owner_id=owner_id, strict=strict)
#         elif float_compare(quantity, 0, precision_rounding=rounding) < 0:
#             available_quantity = sum(quants.mapped('reserved_quantity'))
#         else:
#             return reserved_quants

#         for quant in quants:
#             if float_compare(quantity, 0, precision_rounding=rounding) > 0:
#                 max_quantity_on_quant = quant.quantity - quant.reserved_quantity
#                 if float_compare(max_quantity_on_quant, 0, precision_rounding=rounding) <= 0:
#                     continue
#                 max_quantity_on_quant = min(max_quantity_on_quant, quantity)
#                 quant.reserved_quantity += max_quantity_on_quant
#                 reserved_quants.append((quant, max_quantity_on_quant))
#                 quantity -= max_quantity_on_quant
#                 available_quantity -= max_quantity_on_quant
#             else:
#                 max_quantity_on_quant = min(quant.reserved_quantity, abs(quantity))
#                 quant.reserved_quantity -= max_quantity_on_quant
#                 reserved_quants.append((quant, -max_quantity_on_quant))
#                 quantity += max_quantity_on_quant
#                 available_quantity += max_quantity_on_quant

#             if float_is_zero(quantity, precision_rounding=rounding) or float_is_zero(available_quantity,
#                                                                                      precision_rounding=rounding):
#                 break
#         return reserved_quants

