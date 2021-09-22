# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, tools
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from dateutil import relativedelta
from itertools import groupby
from operator import itemgetter
from datetime import datetime
from datetime import timedelta
from dateutil.parser import parse
import dateparser
import dateutil

from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, pycompat


#TODO : A revoir


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"


    def get_nb_colis(self):
        nb        = self.product_id.is_nb_pieces_par_colis
        poids_net = self.product_id.is_poids_net_colis
        unite     = self.product_uom_id.category_id.name
        nb_colis  = 0
        if unite=="Poids":
            if poids_net>0:
                nb_colis = self.qty_done/poids_net
        else:
            if nb>0:
                nb_colis = self.qty_done / nb
        return round(nb_colis)


    @api.onchange('product_id','qty_done')
    def _onchange_product_id_qty_done(self):
        for obj in self:
            nb_colis = obj.get_nb_colis()
            obj.is_nb_colis = nb_colis
            unite = self.product_uom_id.category_id.name
            if unite=="Poids":
                poids = obj.qty_done
            else:
                poids = nb_colis*obj.product_id.is_poids_net_colis
            obj.is_poids_net_reel = poids


    @api.depends('product_id','qty_done')
    def _compute_is_poids_net_estime(self):
        for obj in self:
            nb_colis = obj.get_nb_colis()
            obj.is_poids_net_estime = nb_colis * obj.product_id.is_poids_net_colis


    is_type_tracabilite    = fields.Selection(string='Traçabilité', related="product_id.is_type_tracabilite")
    is_dlc_ddm             = fields.Date('DLC / DDM', related="lot_id.is_dlc_ddm")
    status_move            = fields.Selection(string='Statut', selection=[('receptionne', 'Réceptionné'), ('manquant', 'Manquant'), ('abime', 'Abimé'), ('autre', 'Autre')], default='receptionne')
    is_nb_pieces_par_colis = fields.Integer(string='Nb Pièces / colis'    , compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_nb_colis            = fields.Float(string='Nb Colis', digits=(14,2))
    is_poids_net_estime    = fields.Float(string='Poids net estimé', digits=(14,4), compute='_compute_is_poids_net_estime', readonly=True, store=True, help="Poids net total (Kg)")
    is_poids_net_reel      = fields.Float(string='Poids net réel', digits=(14,4), help="Poids net réel total (Kg)")


#     def split_qty(self):
#         move_lines_to_pack = self.env['stock.move.line']
#         qty_done = 0
#         for l in self.move_id.move_line_ids:
#             qty_done += l.qty_done
#         quantity_left_todo = self.move_id.product_uom_qty - qty_done
#         done_to_keep = self.qty_done
#         new_move_line = self.copy(
#             default={'product_uom_qty': 0, 'qty_done': self.qty_done})
#         self.write({'product_uom_qty': quantity_left_todo,'qty_done': 0.0, 'life_use_date':False, 'lot_id':False})
#         new_move_line.write({'product_uom_qty': done_to_keep,'weight_uom_id':self.weight_uom_id.id})
#         move_lines_to_pack |= new_move_line


#     @api.multi
#     @api.depends('product_id','create_date')
#     def get_weight_uom(self):
#         for line in self:
#             line.weight_uom_id = line.product_id.weight_uom_id.id

#     @api.onchange('qty_done')
#     def get_weight(self):
#         if self.is_colis:
#             weight = self.product_id.weight * self.qty_done
#         else:
#             weight = self.qty_done

#         if weight:
#             self.weight = weight
#         else:
#                 return True


#     @api.multi
#     @api.depends('product_id', 'create_date', 'qty_done')
#     def get_product_weight(self):
#         for line in self:
#             product_weight = 0
#             if line.qty_done>0:
#                 if line.is_colis:
#                     if line.weight_uom_id.name != 'KG':
#                         product_weight = line.product_id.product_weight * line.qty_done
#                     else:
#                         product_weight = line.product_id.product_weight
#                 else:
#                     if line.weight_uom_id.name != 'KG':
#                         product_weight = (line.product_id.product_weight/line.product_id.weight) * line.qty_done
#                     else:
#                         product_weight = line.qty_done
#             line.product_weight = product_weight




#     weight=fields.Float(string='Quant réelle', readonly=False, digits=dp.get_precision('Stock Weight'))
#                         # , compute=get_weight, store=True, readonly=False , copy=True, digits=dp.get_precision('Stock Weight'))
#     weight_uom_id = fields.Many2one('uom.uom', 'Unité', compute=get_weight_uom, store=True, readonly=False, copy=True)
#     life_use_date = fields.Datetime('DLC/DDM')
#     product_weight = fields.Float('Poids estimé', digits=dp.get_precision('Stock Weight'), compute=get_product_weight,  copy=True)
#     company_id = fields.Many2one('res.company','Company', default=lambda self: self.env.user.company_id)
#     is_colis = fields.Boolean('Colis', related='company_id.inv_is_colis')

#     def _action_done(self):
#         """ This method is called during a move's `action_done`. It'll actually move a quant from
#         the source location to the destination location, and unreserve if needed in the source
#         location.

#         This method is intended to be called on all the move lines of a move. This method is not
#         intended to be called when editing a `done` move (that's what the override of `write` here
#         is done.
#         """
#         Quant = self.env['stock.quant']

#         # First, we loop over all the move lines to do a preliminary check: `qty_done` should not
#         # be negative and, according to the presence of a picking type or a linked inventory
#         # adjustment, enforce some rules on the `lot_id` field. If `qty_done` is null, we unlink
#         # the line. It is mandatory in order to free the reservation and correctly apply
#         # `action_done` on the next move lines.
#         ml_to_delete = self.env['stock.move.line']
#         for ml in self:
#             # Check here if `ml.qty_done` respects the rounding of `ml.product_uom_id`.
#             uom_qty = float_round(ml.qty_done, precision_rounding=ml.product_uom_id.rounding, rounding_method='HALF-UP')
#             precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
#             qty_done = float_round(ml.qty_done, precision_digits=precision_digits, rounding_method='HALF-UP')
#             if float_compare(uom_qty, qty_done, precision_digits=precision_digits) != 0:
#                 raise UserError(_('The quantity done for the product "%s" doesn\'t respect the rounding precision \
#                                   defined on the unit of measure "%s". Please change the quantity done or the \
#                                   rounding precision of your unit of measure.') % (ml.product_id.display_name, ml.product_uom_id.name))

#             qty_done_float_compared = float_compare(ml.qty_done, 0, precision_rounding=ml.product_uom_id.rounding)
#             if qty_done_float_compared > 0:
#                 if ml.product_id.tracking != 'none':
#                     picking_type_id = ml.move_id.picking_type_id
#                     if picking_type_id:
#                         if picking_type_id.use_create_lots:
#                             # If a picking type is linked, we may have to create a production lot on
#                             # the fly before assigning it to the move line if the user checked both
#                             # `use_create_lots` and `use_existing_lots`.
#                             if ml.lot_name and not ml.lot_id:
#                                 lot = self.env['stock.production.lot'].create(
#                                     {'name': ml.lot_name,
#                                      'product_id': ml.product_id.id,
#                                      'use_date': ml.life_use_date if ml.product_id.type_traçabilite=='dlc' else False,
#                                      'life_date': ml.life_use_date if ml.product_id.type_traçabilite == 'ddm' else False,
#                                      }
#                                 )
#                                 ml.write({'lot_id': lot.id})
#                         elif not picking_type_id.use_create_lots and not picking_type_id.use_existing_lots:
#                             # If the user disabled both `use_create_lots` and `use_existing_lots`
#                             # checkboxes on the picking type, he's allowed to enter tracked
#                             # products without a `lot_id`.
#                             continue
#                     elif ml.move_id.inventory_id:
#                         # If an inventory adjustment is linked, the user is allowed to enter
#                         # tracked products without a `lot_id`.
#                         continue

#                     if not ml.lot_id:
#                         print('You need to supply a Lot/Serial number for product in base module')
#                         # raise UserError(_('You need to supply a Lot/Serial number for product %s.') % ml.product_id.display_name)
#             elif qty_done_float_compared < 0:
#                 raise UserError(_('No negative quantities allowed'))
#             else:
#                 ml_to_delete |= ml
#         ml_to_delete.unlink()

#         # Now, we can actually move the quant.
#         done_ml = self.env['stock.move.line']
#         for ml in self - ml_to_delete:
#             if ml.product_id.type == 'product':
#                 rounding = ml.product_uom_id.rounding

#                 # if this move line is force assigned, unreserve elsewhere if needed
#                 if not ml.location_id.should_bypass_reservation() and float_compare(ml.qty_done, ml.product_qty, precision_rounding=rounding) > 0:
#                     extra_qty = ml.qty_done - ml.product_qty
#                     ml._free_reservation(ml.product_id, ml.location_id, extra_qty, lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id, ml_to_ignore=done_ml)
#                 # unreserve what's been reserved
#                 if not ml.location_id.should_bypass_reservation() and ml.product_id.type == 'product' and ml.product_qty:
#                     try:
#                         Quant._update_reserved_quantity(ml.product_id, ml.location_id, -ml.product_qty, lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
#                     except UserError:
#                         Quant._update_reserved_quantity(ml.product_id, ml.location_id, -ml.product_qty, lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)

#                 # move what's been actually done
#                 quantity = ml.product_uom_id._compute_quantity(ml.qty_done, ml.move_id.product_id.uom_id, rounding_method='HALF-UP')
#                 available_qty, in_date = Quant._update_available_quantity(ml.product_id, ml.location_id, -quantity, lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id)
#                 if available_qty < 0 and ml.lot_id:
#                     # see if we can compensate the negative quants with some untracked quants
#                     untracked_qty = Quant._get_available_quantity(ml.product_id, ml.location_id, lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
#                     if untracked_qty:
#                         taken_from_untracked_qty = min(untracked_qty, abs(quantity))
#                         Quant._update_available_quantity(ml.product_id, ml.location_id, -taken_from_untracked_qty, lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id)
#                         Quant._update_available_quantity(ml.product_id, ml.location_id, taken_from_untracked_qty, lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id)
#                 Quant._update_available_quantity(ml.product_id, ml.location_dest_id, quantity, lot_id=ml.lot_id, package_id=ml.result_package_id, owner_id=ml.owner_id, in_date=in_date)
#             done_ml |= ml


#         # Reset the reserved quantity as we just moved it to the destination location.
#         (self - ml_to_delete).with_context(bypass_reservation_update=True).write({
#             'product_uom_qty': 0.00,
#             'date': fields.Datetime.now(),
#         })




#     @api.onchange('lot_id')
#     def onchage_lot_life_use_date(self):
#         if self.lot_id:
#             if self.lot_id.use_date:
#                 self.life_use_date = self.lot_id.use_date
#             elif self.lot_id.life_date:
#                 self.life_use_date = self.lot_id.life_date

#     @api.onchange('life_use_date')
#     def onchage_life_use_date_lot(self):
#         if self.life_use_date and self.lot_id:
#             if self.lot_id.type_traçabilite == 'dlc':
#                 self.lot_id.write({'life_date': self.life_use_date})
#             if self.lot_id.type_traçabilite == 'ddm':
#                 self.lot_id.write({'use_date': self.life_use_date})






# class StockMove(models.Model):
#     _inherit = "stock.move"



#     @api.multi
#     def get_ddm_lot(self):
#         for move in self:
#             ddms={}
#             for line in move.move_line_ids:
#                 key = str(move.id)+"-"+str(line.lot_id.id or '')+"-"+((line.life_use_date and str(line.life_use_date)[:10]) or '')
#                 if key not in ddms:
#                     ddms[key]={}
#                     ddms[key]["lot"]=line.lot_id.name
#                     ddms[key]["type_tracabilite"]=move.product_id.type_traçabilite
#                     ddms[key]["life_use_date"]=line.life_use_date and line.life_use_date.strftime('%d/%m/%Y') or ''
#                     ddms[key]["weight"]=0
#                     ddms[key]["qty_done"]=0
#                 ddms[key]["weight"]+=line.weight
#                 ddms[key]["qty_done"]+=line.qty_done
#             return ddms


#     @api.multi
#     def move_lot(self):
#         for move in self:
#             list=[]

#             for line in move.move_line_ids:
#                 if line.lot_id.id:
#                     list.append(line.lot_id.id)

#             move.lot_ids=[(6, 0,list)]

#     @api.multi
#     @api.depends('lot_ids','move_line_ids','quantity_done')
#     def lot_names(self):
#         for move in self:
#             if move.lot_ids:
#                 ch = ''
#                 lang = self._context.get("lang")
#                 lang_params = {}
#                 if lang:
#                     record_lang = self.env['res.lang'].with_context(active_test=False).search([("code", "=", lang)],
#                                                                                               limit=1)
#                     lang_params = {
#                         'date_format': record_lang.date_format,
#                         'time_format': record_lang.time_format
#                     }

#                 format_date = pycompat.to_native(lang_params.get("date_format") or '%d/%m/%Y')
#                 # for lot in move.lot_ids:
#                 #     ch += 'Lot N° ' + lot.name
#                 #     if lot.use_date:
#                 #         ch += ' ' + 'DDM : ' + str(lot.use_date.date().strftime(format_date))
#                 #     elif lot.life_date:
#                 #         ch += ' ' + 'DLC : ' + str(lot.life_date.date().strftime(format_date))
#                 #     lot_qty = 0
#                 #     for line in move.move_line_ids:
#                 #         if line.lot_id == lot:
#                 #             lot_qty += line.qty_done
#                 #     ch += ' ' + 'Qte :' + ' ' + str(lot_qty) + ' ' + move.product_uom.name
#                 #     ch += '\n'


#                 ddms={}
#                 for line in move.move_line_ids:
#                     key = str(move.id)+"-"+str(line.lot_id.id or '')+"-"+((line.life_use_date and str(line.life_use_date)[:10]) or '')
#                     if key not in ddms:
#                         ddms[key]={}
#                         ddms[key]["lot"]=line.lot_id.name
#                         ddms[key]["type_tracabilite"]=move.product_id.type_traçabilite
#                         ddms[key]["life_use_date"]=line.life_use_date and line.life_use_date.strftime(format_date) or ''
#                         ddms[key]["weight"]=0
#                         ddms[key]["qty_done"]=0
#                     ddms[key]["weight"]+=line.weight
#                     ddms[key]["qty_done"]+=line.qty_done
#                 lot_name=[]
#                 for ddm in ddms:
#                     if ddms[ddm]["lot"]:
#                         lot = 'Lot: ' + ddms[ddm]["lot"]
#                         lot += ' ' + ddms[ddm]["type_tracabilite"].upper()
#                         lot += ': ' + ddms[ddm]["life_use_date"]
#                         lot += ' Quant: ' + str(ddms[ddm]["weight"])
#                         lot += ' Colis: ' + str(ddms[ddm]["qty_done"])
#                         lot_name.append(lot)
#                 lot_name="\n".join(lot_name)
#                 move.lot_name = lot_name



#     note = fields.Text('Notes')
#     lot_ids = fields.Many2many('stock.production.lot','stock_move_production_lot_rel', string="lots", compute=move_lot)
#     lot_name = fields.Text('Lots Détails',compute=lot_names, store=True)
#     is_colis = fields.Boolean('Colis', related='company_id.inv_is_colis')

#     def put_in_pack(self):
#         package = False
#         move_lines_to_pack = self.env['stock.move.line']

#         for ml in self.move_line_ids:
#             if not ml.result_package_id:
#                 package = self.env['stock.quant.package'].create({})
#                 if float_compare(ml.qty_done, ml.product_uom_qty,
#                                  precision_rounding=ml.product_uom_id.rounding) >= 0:
#                     move_lines_to_pack = ml
#                 else:
#                     quantity_left_todo = float_round(
#                         ml.product_uom_qty - ml.qty_done,
#                         precision_rounding=ml.product_uom_id.rounding,
#                         rounding_method='UP')
#                     done_to_keep = ml.qty_done
#                     new_move_line = ml.copy(
#                         default={'product_uom_qty': 0, 'qty_done': ml.qty_done, 'weight':ml.weight})
#                     ml.write({'product_uom_qty': quantity_left_todo, 'qty_done': 0.0})
#                     new_move_line.write({'product_uom_qty': done_to_keep, 'weight':ml.weight})
#                     move_lines_to_pack |= new_move_line

#                 package_level = self.env['stock.package_level'].create({
#                     'package_id': package.id,
#                     'picking_id': ml.picking_id.id,
#                     'location_id': False,
#                     'location_dest_id': self.mapped('location_dest_id').id,
#                     'self': [(6, 0, move_lines_to_pack.ids)]
#                 })
#                 package.write({
#                     # 'weight': ml.weight,
#                     'shipping_weight': ml.weight,
#                 })
#                 self._cr.execute("""UPDATE stock_quant_package SET weight = %s WHERE id = %s""",
#                                  (ml.weight, package.id))

#                 move_lines_to_pack.write({
#                     'result_package_id': package.id,
#                 })
#             else:
#                 return True



#     weight = fields.Float('Quantité',compute='_cal_move_weight', digits=dp.get_precision('Stock Weight'),store=True)
#     weight_uom_id = fields.Many2one('uom.uom', 'UV',compute='_cal_move_weight',store=True)
#     vendor_id = fields.Many2one('res.partner','Fournisseur',related='created_purchase_line_id.partner_id')

#     product_weight = fields.Float('Poids(Kg)', digits=dp.get_precision('Stock Weight'),compute='_cal_move_weight', copy=True)


#     @api.multi
#     @api.depends('product_id', 'product_uom_qty', 'product_uom','move_line_ids','move_line_ids.weight','quantity_done')
#     def _cal_move_weight(self):
#         for move in self:
#             weight = 0
#             product_weight = 0
#             for line in move.move_line_ids:
#                 weight += line.weight
#                 product_weight += line.product_weight
#             if weight:
#                 move.weight = weight
#                 move.weight_uom_id =  move.move_line_ids[0].weight_uom_id.id
#                 move.product_weight = product_weight


#     def action_show_details(self):
#         """ Returns an action that will open a form view (in a popup) allowing to work on all the
#         move lines of a particular move. This form view is used when "show operations" is not
#         checked on the picking type.
#         """
#         self.ensure_one()

#         # If "show suggestions" is not checked on the picking type, we have to filter out the
#         # reserved move lines. We do this by displaying `move_line_nosuggest_ids`. We use
#         # different views to display one field or another so that the webclient doesn't have to
#         # fetch both.
#         if self.picking_id.picking_type_id.show_reserved:
#             view = self.env.ref('stock.view_stock_move_operations')
#         else:
#             view = self.env.ref('stock.view_stock_move_nosuggest_operations')

#         return {
#             'name': _('Detailed Operations'),
#             'type': 'ir.actions.act_window',
#             'view_type': 'form',
#             'view_mode': 'form',
#             'res_model': 'stock.move',
#             'views': [(view.id, 'form')],
#             'view_id': view.id,
#             'target': 'current',
#             'res_id': self.id,
#             'context': dict(
#                 self.env.context,
#                 show_lots_m2o=self.has_tracking != 'none' and (self.picking_type_id.use_existing_lots or self.state == 'done' or self.origin_returned_move_id.id),  # able to create lots, whatever the value of ` use_create_lots`.
#                 show_lots_text=self.has_tracking != 'none' and self.picking_type_id.use_create_lots and not self.picking_type_id.use_existing_lots and self.state != 'done' and not self.origin_returned_move_id.id,
#                 show_source_location=self.location_id.child_ids and self.picking_type_id.code != 'incoming',
#                 show_destination_location=self.location_dest_id.child_ids and self.picking_type_id.code != 'outgoing',
#                 show_package=not self.location_id.usage == 'supplier',
#                 show_reserved_quantity=self.state != 'done',
#                 form_view_initial_mode = 'edit',
#                 force_detailed_view = True
#             ),
#         }

#     def _quantity_done_set(self):
#         quantity_done = self[0].quantity_done  # any call to create will invalidate `move.quantity_done`
#         for move in self:
#             move_lines = move._get_move_lines()
#             if not move_lines:
#                 if quantity_done:
#                     # do not impact reservation here
#                     move_line = self.env['stock.move.line'].create(
#                         dict(move._prepare_move_line_vals(), qty_done=quantity_done))
#                     move.write({'move_line_ids': [(4, move_line.id)]})
#             elif len(move_lines) == 1:
#                 move_lines[0].qty_done = quantity_done
#             # else:
#             #     raise UserError(_("Cannot set the done quantity from this stock move, work directly with the move lines."))


#     def _action_assign(self):
#         """ Reserve stock moves by creating their stock move lines. A stock move is
#         considered reserved once the sum of `product_qty` for all its move lines is
#         equal to its `product_qty`. If it is less, the stock move is considered
#         partially available.
#         """
#         assigned_moves = self.env['stock.move']
#         partially_available_moves = self.env['stock.move']
#         # Read the `reserved_availability` field of the moves out of the loop to prevent unwanted
#         # cache invalidation when actually reserving the move.
#         reserved_availability = {move: move.reserved_availability for move in self}
#         roundings = {move: move.product_id.uom_id.rounding for move in self}
#         for move in self.filtered(lambda m: m.state in ['confirmed', 'waiting', 'partially_available']):
#             rounding = roundings[move]
#             missing_reserved_uom_quantity = move.product_uom_qty - reserved_availability[move]
#             missing_reserved_quantity = move.product_uom._compute_quantity(missing_reserved_uom_quantity, move.product_id.uom_id, rounding_method='HALF-UP')
#             if move.product_id.tracking == 'serial' and (move.picking_type_id.use_create_lots or move.picking_type_id.use_existing_lots):
#                 for i in range(0, int(missing_reserved_quantity)):
#                     self.env['stock.move.line'].create(move._prepare_move_line_vals(quantity=1))
#             else:
#                 to_update = move.move_line_ids.filtered(lambda ml: ml.product_uom_id == move.product_uom and
#                                                         ml.location_id == move.location_id and
#                                                         ml.location_dest_id == move.location_dest_id and
#                                                         ml.picking_id == move.picking_id and
#                                                         not ml.lot_id and
#                                                         not ml.package_id and
#                                                         not ml.owner_id)
#                 if to_update:
#                     to_update[0].product_uom_qty += missing_reserved_uom_quantity
#                 else:
#                     self.env['stock.move.line'].create(move._prepare_move_line_vals(quantity=missing_reserved_quantity))
#             assigned_moves |= move

#         partially_available_moves.write({'state': 'partially_available'})
#         assigned_moves.write({'state': 'assigned'})
#         self.mapped('picking_id')._check_entire_pack()

#     picking_user_id = fields.Many2one(
#         'res.users',
#         related='picking_id.user_id',
#         string="Responsable Livraison",
#     )

