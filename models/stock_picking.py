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


class Picking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'barcodes.barcode_events_mixin']


    @api.onchange('move_ids_without_package')
    def _compute_is_alerte(self):
        for obj in self:
            obj.is_alerte=str(len(obj.move_ids_without_package))
            alerte=[]
            for line in obj.move_ids_without_package:
                if line.is_alerte:
                    alerte.append(line.is_alerte)
            if len(alerte)>0:
                alerte='\n'.join(alerte)
            else:
                alerte=False
            obj.is_alerte=alerte


    is_alerte  = fields.Text('Alerte', copy=False, compute=_compute_is_alerte)
    is_info    = fields.Text('Info'  , copy=False, compute=_compute_is_alerte)

    is_user_id = fields.Many2one('res.users', string="Responsable", related="sale_id.user_id")
    #team_id = fields.Many2one('crm.team', 'Equipe Commerciale', related="sale_id.team_id")

    #@api.multi
    #def do_print_pickingorder(self):
    #    self.write({'printed': True})
    #    return self.env.ref('stock.action_report_delivery').report_action(self)


    scans=[]
    def _add_product(self, product, barcode, qty=1.0):
        is_scan_qty = 1
        tz = pytz.timezone('Europe/Paris')
        paris_now = datetime.now(tz).strftime("%H:%M:%S")
        line = self.move_ids_without_package.filtered(lambda r: r.product_id.id == product.id)
        if len(line)>1:
            raise UserError("Il y a 2 lignes sur l'article %s"%(line[0].product_id.default_code))
        if line.move_line_ids:
            line.move_line_ids[0].write({'weight_uom_id': line.product_id.weight_uom_id.id})
        if str(barcode)[:2] in ("01","02"):
            if line.show_details_visible:
                line.is_quantity_done_editable = True
            if line:
                if line.reserved_availability >= line.quantity_done+qty:
                    if line.is_colis:
                        line.move_line_ids[0].qty_done += qty
                        line.move_line_ids[0].split_qty()
                    else:
                        if product.uom_id.category_id.name=="Pièce":
                            line.move_line_ids[0].qty_done += qty
                        else:
                            weight = line.product_id.uom_po_id.factor_inv
                            line.move_line_ids[0].qty_done += weight
                        line.move_line_ids[0].split_qty()


                    message = "%s : %s : qt=%s " % (paris_now, product.name, line.quantity_done)
                    self.is_info=message
                else:
                    message = "%s : %s : qt=%s : Quantité réservée de %s atteinte " % (paris_now, product.name, line.quantity_done, line.reserved_availability)
                    self.is_alerte = message
                    self.is_info   = False
            else:
                message = "L'article %s n'est pas sur ce document !" %  product.name_get()[0][1]
                self.is_alerte = message
        else:
            code = str(barcode)[2:]
            n=len(line.move_line_ids)-1
            if n>0:
                if str(barcode)[:2] in ("10"):
                    if product:
                        if product.uom_id.category_id.name=="Pièce":
                            qty=product.uom_id.factor_inv or 1
                            if qty <1:
                                qty=1
                            line.move_line_ids[n].write({'weight': qty*is_scan_qty})
                    line.move_line_ids[n].write({'lot_name' : code} )
                    lot = self.env['stock.production.lot'].search([('name','=',code),('product_id','=',product.id)],limit=1)
                    if lot:
                        message = "Lot numéro  %s'" % (lot.name)
                    else:
                        lot = self.env['stock.production.lot'].create(
                            {'name': code, 'product_id': product.id}
                        )
                        message = "Création lot %s" % (lot.name)
                    picking_id = line.move_line_ids[0].picking_id.id
                    line.move_line_ids[n].write({'picking_id': picking_id,'lot_id': lot.id})

                    if self.is_info:
                        self.is_info+=" : "+message
                    else:
                        self.is_info=message

                elif str(barcode)[:2] in ("15"):
                    date_due = dateparser.parse(code, date_formats=['%y%m%d'])
                    contrat_date_obj = self.env['contrat.date.client'].search(
                        [('partner_id', '=', self.partner_id.id),
                         ('product_id', '=', product.product_tmpl_id.id)], limit=1)
                    contrat_date = datetime.now() + timedelta(days=contrat_date_obj.name)
                    if contrat_date_obj and contrat_date.date() > date_due.date():
                        raise UserError(_('Verifiez Contrat date du client !'))
                    elif date_due and date_due.date() < datetime.now().date():
                        raise UserError(_('Produit expiré !'))
                    elif date_due and date_due.date() == datetime.now().date():
                        raise UserError(_('Vérifiez date expiration produit !'))

                    line.move_line_ids[n].write({"life_use_date": date_due} )
                    line.move_line_ids[n].lot_id.write({"use_date": date_due})

                elif str(barcode)[:2] in ("17"):
                    life_use_date = dateparser.parse(code, date_formats=['%y%m%d'])
                    line.move_line_ids[n].write({"life_use_date" : life_use_date})
                    line.move_line_ids[n].lot_id.write({"life_date": life_use_date})

                elif str(barcode)[:2] in ("31"):
                    decimal = int(str(barcode)[3])
                    code = float(str(barcode)[4:-decimal] + '.' + str(barcode)[-decimal:])
                    if line.move_line_ids[n].weight_uom_id.category_id.name == "Poids":
                        if not line.is_colis:
                            vals={
                                "qty_done"       : code,
                                "weight"         : code * line.move_line_ids[n].product_uom_qty,
                            }
                        else:
                            qt = code * line.move_line_ids[n].product_uom_qty
                            vals={
                                "qty_done"       : 1,
                                "weight"         : qt,
                            }
                        line.move_line_ids[n].write(vals)
                    else:
                        product_weight = code * line.move_line_ids[n].product_uom_qty
                        line.move_line_ids[n].write({'product_weight': product_weight})
                    line._cal_move_weight()
        return True


    def on_barcode_scanned(self, barcode):
        self.scans.append(barcode)
        if self.state not in ['assigned']:
            self.is_alerte="Le BL doit-être à l'état Prêt !"
            return
        if str(barcode)[:2] in ("01","02"):
            self.barcode_product_id = False
            pr_barcode =  str(barcode)[2:]
            product = self.env['product.product'].search([('barcode', '=',pr_barcode)])
            if product:
                self._add_product(product, barcode)
                self.barcode_product_id =  product.id
            else:
                self.barcode_product_id = False
                self.is_alerte="Code EAN %s non trouvé" % pr_barcode
                return
        if self.barcode_product_id and str(barcode)[:2] in ('10','15','17','31','37'):
            self._add_product(self.barcode_product_id, barcode)



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

