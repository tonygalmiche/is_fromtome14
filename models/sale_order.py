# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, Warning
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
import time
from odoo.osv import expression
import datetime


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"


    # @api.depends('product_id')
    # def _compute_purchase_order_line_id(self):
    #     for obj in self:
    #         filtre=[
    #             ('is_sale_order_line_id','=',obj.id),
    #         ]
    #         order_lines=self.env['purchase.order.line'].search(filtre)
    #         order_id = False
    #         for line in order_lines:
    #             if line.order_id.state!='cancel':
    #                 order_id=line.id
    #                 break
    #         obj.is_purchase_order_line_id = order_id

    # is_purchase_order_line_id = fields.Many2one('purchase.order.line', string=u'Ligne commande fournisseur', compute='_compute_purchase_order_line_id', readonly=True, store=False)



    def get_nb_colis(self):
        nb        = self.product_id.is_nb_pieces_par_colis
        poids_net = self.product_id.is_poids_net_colis
        unite     = self.product_uom.category_id.name
        nb_colis  = 0
        if unite=="Poids":
            if poids_net>0:
                nb_colis = self.product_uom_qty/poids_net
        else:
            if nb>0:
                nb_colis = self.product_uom_qty / nb
        return round(nb_colis)


    @api.depends('product_id','product_uom_qty')
    def _compute_is_nb_pieces_par_colis(self):
        for obj in self:
            nb_colis = obj.get_nb_colis()
            obj.is_nb_colis = nb_colis

            unite = obj.product_uom.category_id.name
            if unite=="Poids":
                poids = obj.product_uom_qty
            else:
                poids = nb_colis*obj.product_id.is_poids_net_colis
            obj.is_poids_net = poids
            obj.is_nb_pieces_par_colis=obj.product_id.is_nb_pieces_par_colis


    is_purchase_line_id       = fields.Many2one('purchase.order.line', string=u'Ligne commande fournisseur', index=True, copy=False)
    is_date_reception         = fields.Date(string=u'Date réception')
    is_livraison_directe      = fields.Boolean(string=u'Livraison directe', help=u"Si cette case est cochée, une commande fournisseur spécifique pour ce client sera créée",default=False)
    is_nb_pieces_par_colis    = fields.Integer(string='Nb Pièces / colis', compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_nb_colis               = fields.Float(string='Nb Colis', digits=(14,2), compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_poids_net              = fields.Float(string='Poids net', digits=(14,4), compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True, help="Poids net total (Kg)")




    def get_fournisseur_par_defaut(self):
        now = datetime.date.today()
        suppliers=self.env['product.supplierinfo'].search([('product_tmpl_id', '=', self.product_id.product_tmpl_id.id)])
        partner=False
        for s in suppliers:
            if now>=s.date_start and now<= s.date_end:
                partner=s.name
                break
        return partner


    @api.onchange('product_id','is_livraison_directe')
    def onchange_product_id_for_date_reception(self):
        if self.is_livraison_directe:
            if self.order_id.is_date_livraison:
                self.is_date_reception = self.order_id.is_date_livraison
        else:
            partner = self.get_fournisseur_par_defaut()
            if partner and partner.is_date_reception:
                self.is_date_reception = partner.is_date_reception


    @api.onchange('is_date_reception')
    def onchange_is_date_reception(self):
        if self.is_date_reception:
            partner = self.get_fournisseur_par_defaut()
            if partner:
                partner.write({'is_date_reception': self.is_date_reception})


    def acceder_commande_fournisseur(self):
        for obj in self:
            res= {
                'name': 'Ligne commande fournisseur',
                'view_mode': 'tree,form',
                'view_type': 'form',
                'res_model': 'purchase.order.line',
                'type': 'ir.actions.act_window',
                'domain': [
                    ('id','=',obj.is_purchase_line_id.id),
                ],
            }
            return res


class SaleOrder(models.Model):
    _inherit = "sale.order"


    is_date_livraison  = fields.Date('Date Livraison')
    is_commande_soldee = fields.Boolean(string=u'Commande soldée', default=False, copy=False, help=u"Cocher cette case pour indiquer qu'aucune nouvelle livraison n'est prévue sur celle-ci")

    @api.depends('order_line')
    def _compute_is_creer_commande_fournisseur_vsb(self):
        for obj in self:
            vsb = False
            for line in obj.order_line:
                if not line.is_purchase_line_id.id:
                    vsb=True
                    break
            obj.is_creer_commande_fournisseur_vsb=vsb


    is_creer_commande_fournisseur_vsb = fields.Boolean(string=u'Créer commande fournisseur', compute='_compute_is_creer_commande_fournisseur_vsb', readonly=True, store=False)


    def creer_commande_fournisseur_action(self):
        for obj in self:
            if not len(obj.order_line):
                raise Warning(u"Il n'y a aucune ligne de commandes à traiter !")
            for line in obj.order_line:
                if not line.is_date_reception:
                    raise Warning(u"La date de réception n'est pas renseignée sur toutes les lignes")
            now = datetime.date.today()
            for line in obj.order_line:
                if not line.is_purchase_line_id:
                    suppliers=self.env['product.supplierinfo'].search([('product_tmpl_id', '=', line.product_id.product_tmpl_id.id)])
                    partner_id=False
                    supplierinfo=False
                    for s in suppliers:
                        if now>=s.date_start and now<= s.date_end:
                            supplierinfo=s
                            break
                    if supplierinfo:
                        partner_id = supplierinfo.name.id
                        date_reception = str(line.is_date_reception)
                        date_planned  = date_reception+' 08:00:00'
                        filtre=[
                            ('partner_id'  ,'='   , partner_id),
                            ('state'       ,'='   , 'draft'),
                            ('date_planned','>=', date_reception+' 00:00:00'),
                            ('date_planned','<=', date_reception+' 23:59:59'),
                        ]
                        if line.is_livraison_directe:
                            filtre.append(('delivery_adress','=', obj.partner_shipping_id.id))
                        orders=self.env['purchase.order'].search(filtre,limit=1)

                        print(orders)


                        if orders:
                            order=orders[0]
                        else:
                            vals={
                                'partner_id'  : partner_id,
                                #'date_planned': date_planned,
                            }
                            order=self.env['purchase.order'].create(vals)
                            if order:
                                order.onchange_partner_id()
                                if line.is_livraison_directe:
                                    order.delivery_adress = obj.partner_shipping_id.id

                        #** Création des lignes ************************************
                        filtre=[
                            ('order_id'  ,'=', order.id),
                            ('product_id','=', line.product_id.id),

                        ]
                        order_lines=self.env['purchase.order.line'].search(filtre,limit=1)
                        if not order_lines:
                            if order:
                                vals={
                                    'order_id'    : order.id,
                                    'product_id'  : line.product_id.id,
                                    'name'        : line.name,
                                    'product_qty' : line.product_uom_qty,
                                    'product_uom' : line.product_uom.id,
                                    'date_planned': date_planned,
                                    'price_unit'  : line.price_unit,
                                    #'is_sale_order_line_id': line.id,
                                }
                                order_line=self.env['purchase.order.line'].create(vals)
                                order_line.onchange_product_id()
                                order_line.date_planned = date_planned
                                print(vals,order_line.date_planned)
                        else:
                            order_line = order_lines[0]

                        if order_line:
                            line.is_purchase_line_id=order_line.id
                            filtre=[
                                ('is_purchase_line_id'  ,'=', order_line.id),
                            ]
                            order_lines=self.env['sale.order.line'].search(filtre)
                            qty=0
                            for l in order_lines:
                                qty+=l.product_uom_qty
                            order_line.product_qty = qty
                        # ***********************************************************




    # @api.multi
    # def creer_commande_fournisseur_action(self):
    #     for obj in self:
    #         if not len(obj.order_line):
    #             raise Warning(u"Il n'y a aucune ligne de commandes à traiter !")
    #         for line in obj.order_line:
    #             if not line.is_date_reception:
    #                 raise Warning(u"La date de réception n'est pas renseignée sur toutes les lignes")
    #         now = datetime.date.today()
    #         for line in obj.order_line:
    #             suppliers=self.env['product.supplierinfo'].search([('product_tmpl_id', '=', line.product_id.product_tmpl_id.id)])
    #             partner_id=False
    #             supplierinfo=False
    #             for s in suppliers:
    #                 if now>=s.date_start and now<= s.date_end:
    #                     supplierinfo=s
    #                     break
    #             if supplierinfo:
    #                 partner_id = supplierinfo.name.id
    #                 date_reception = str(line.is_date_reception)
    #                 date_planned  = date_reception+' 08:00:00'
    #                 filtre=[
    #                     ('partner_id'  ,'='   , partner_id),
    #                     ('state'       ,'='   , 'draft'),
    #                     ('date_planned','>=', date_reception+' 00:00:00'),
    #                     ('date_planned','<=', date_reception+' 23:59:59'),
    #                 ]
    #                 if line.is_livraison_directe:
    #                     filtre.append(('delivery_adress','=', obj.partner_shipping_id.id))
    #                 orders=self.env['purchase.order'].search(filtre,limit=1)
    #                 if orders:
    #                     order=orders[0]
    #                 else:
    #                     vals={
    #                         'partner_id'  : partner_id,
    #                     }
    #                     order=self.env['purchase.order'].create(vals)
    #                     if order:
    #                         order.onchange_partner_id()
    #                         if line.is_livraison_directe:
    #                             order.delivery_adress = obj.partner_shipping_id.id

    #                 #** Création des lignes ************************************
    #                 filtre=[
    #                     ('order_id'  ,'='   , order.id),
    #                     ('is_sale_order_line_id','=',line.id),
    #                 ]
    #                 order_lines=self.env['purchase.order.line'].search(filtre)
    #                 if not order_lines:
    #                     if order:
    #                         vals={
    #                             'order_id'    : order.id,
    #                             'product_id'  : line.product_id.id,
    #                             'name'        : line.name,
    #                             'product_qty' : line.product_uom_qty,
    #                             'product_uom' : line.product_uom.id,
    #                             'date_planned': date_planned,
    #                             'price_unit'  : line.price_unit,
    #                             'is_sale_order_line_id': line.id,
    #                         }
    #                         order_line=self.env['purchase.order.line'].create(vals)
    #                         order_line.onchange_product_id()
    #                         order_line.product_qty = line.product_uom_qty
    #                 #***********************************************************







#TODO : A revoir

# class SaleOrderLine(models.Model):
#     _inherit = "sale.order.line"

#     echantillion = fields.Boolean(string='Echantillon')

#     @api.multi
#     def _prepare_invoice_line(self, qty):
#         vals = super(SaleOrderLine, self)._prepare_invoice_line(qty)
#         move_ids = self.mapped('move_ids').filtered(
#             lambda x: x.state == 'done' and
#             not x.invoice_line_id and
#             not x.scrapped and (
#                 x.location_dest_id.usage == 'customer' or
#                 (x.location_id.usage == 'customer' and
#                  x.to_refund)
#             )).ids
#         vals['move_line_ids'] = [(6, 0, move_ids)]
#         move_obj = self.env['stock.move'].browse(move_ids)
#         move_weight = 0
#         for move in move_obj :
#             if move.is_colis and move.state != 'cancel':
#                 move_weight += move.weight
#             elif move.state != 'cancel':
#                 move_weight += move.quantity_done
#             else:
#                 continue

#         lot_name = ''
#         for move in move_obj:
#             if move.lot_name:
#                 lot_name += ' ' + move.lot_name
#         uom = False
#         if move_obj :
#             uom = move_obj[0].weight_uom_id.id
#         vals['name'] = vals['name'] + '\n' + lot_name
#         vals['quantity']= move_weight
#         vals['uom_id'] =  uom
#         vals['price_unit'] = self.price_unit or self.product_id.lst_price
#         return vals

#     @api.multi
#     @api.onchange('product_id')
#     def product_id_change(self):
#         vals = super(SaleOrderLine, self).product_id_change()
#         if self.product_id:
#             self.name = self.product_id.display_name


#     @api.onchange('product_id', 'product_uom')
#     def product_id_change_margin(self):
#         for line in self:
#             if not line.order_id.pricelist_id or not line.product_id or not line.product_uom:
#                 return
#             line.purchase_price = line._compute_margin(line.order_id, line.product_id, line.product_uom)


# class SaleOrder(models.Model):
#     _inherit = "sale.order"

#     picking_policy = fields.Selection([
#         ('direct', 'Deliver each product when available'),
#         ('one', 'Deliver all products at once')],
#         string='Shipping Policy', required=True, readonly=True, default='one',
#         states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}
#         , help="If you deliver all products at once, the delivery order will be scheduled based on the greatest "
#                "product lead time. Otherwise, it will be based on the shortest.")

#     mode_facturation = fields.Selection([('cmde','A la commande'),('mensuel','Mensuel')], string="Mode Facturation")

#     @api.onchange('partner_id')
#     def onchange_mode_facturation(self):
#         if self.partner_id and self.partner_id.mode_facturation:
#             self.mode_facturation = self.partner_id.mode_facturation

#     def count_sale_line(self):
#         for s in self:
#             s.sale_line_count = len(s.order_line)
#             s.sale_total_qty = sum([line.product_uom_qty for line in s.order_line])


#     sale_line_count = fields.Integer('NB lignes', compute=count_sale_line)
#     sale_total_qty = fields.Integer('NB Colis', compute=count_sale_line)

#     delivery_date = fields.Datetime('Date Livraison')

#     @api.onchange('pricelist_id','partner_id')
#     @api.multi
#     def onchage_pricelist(self):
#         if self.pricelist_id and self.partner_id and not self.partner_id.property_product_pricelist:
#             self.partner_id.write({'property_product_pricelist' : self.pricelist_id.id})
#         if not self.pricelist_id and self.partner_id and self.partner_id.property_product_pricelist:
#             self.pricelist_id = self.partner_id.property_product_pricelist.id

#     invoice_status = fields.Selection([
#         ('upselling', 'Upselling Opportunity'),
#         ('invoiced', 'Fully Invoiced'),
#         ('parial invoiced', 'Partiellement facturé'),
#         ('to invoice', 'To Invoice'),
#         ('no', 'Nothing to Invoice')
#     ], string='Invoice Status', compute='_get_invoiced', store=True, readonly=True)

#     @api.depends('state', 'order_line.invoice_status', 'order_line.invoice_lines')
#     def _get_invoiced(self):
#         # Ignore the status of the deposit product
#         deposit_product_id = self.env['sale.advance.payment.inv']._default_product_id()
#         line_invoice_status_all = [(d['order_id'][0], d['invoice_status']) for d in
#                                    self.env['sale.order.line'].read_group(
#                                        [('order_id', 'in', self.ids), ('product_id', '!=', deposit_product_id.id)],
#                                        ['order_id', 'invoice_status'], ['order_id', 'invoice_status'], lazy=False)]
#         for order in self:
#             invoice_ids = order.order_line.mapped('invoice_lines').mapped('invoice_id').filtered(
#                 lambda r: r.type in ['out_invoice', 'out_refund'])
#             # Search for invoices which have been 'cancelled' (filter_refund = 'modify' in
#             # 'account.invoice.refund')
#             # use like as origin may contains multiple references (e.g. 'SO01, SO02')
#             refunds = invoice_ids.search([('origin', 'like', order.name), ('company_id', '=', order.company_id.id),
#                                           ('type', 'in', ('out_invoice', 'out_refund'))])
#             invoice_ids |= refunds.filtered(lambda r: order.name in [origin.strip() for origin in r.origin.split(',')])

#             # Search for refunds as well
#             domain_inv = expression.OR([
#                 ['&', ('origin', '=', inv.number), ('journal_id', '=', inv.journal_id.id)]
#                 for inv in invoice_ids if inv.number
#             ])
#             if domain_inv:
#                 refund_ids = self.env['account.invoice'].search(expression.AND([
#                     ['&', ('type', '=', 'out_refund'), ('origin', '!=', False)],
#                     domain_inv
#                 ]))
#             else:
#                 refund_ids = self.env['account.invoice'].browse()

#             line_invoice_status = [d[1] for d in line_invoice_status_all if d[0] == order.id]

#             if order.state not in ('sale', 'done'):
#                 invoice_status = 'no'

#             elif all(invoice_status == 'invoiced' for invoice_status in line_invoice_status):
#                 invoice_status = 'invoiced'
#             elif any(invoice_status == 'invoiced' for invoice_status in line_invoice_status):
#                 invoice_status = 'parial invoiced'
#             elif any(invoice_status == 'to invoice' for invoice_status in line_invoice_status):
#                 invoice_status = 'to invoice'
#             elif all(invoice_status in ['invoiced', 'upselling'] for invoice_status in line_invoice_status):
#                 invoice_status = 'upselling'
#             else:
#                 invoice_status = 'no'

#             order.update({
#                 'invoice_count': len(set(invoice_ids.ids + refund_ids.ids)),
#                 'invoice_ids': invoice_ids.ids + refund_ids.ids,
#                 'invoice_status': invoice_status
#             })

# class Picking(models.Model):
#     _inherit = "stock.picking"

#     is_colis = fields.Boolean('Colis', related='company_id.inv_is_colis')


#     @api.one
#     @api.depends('sale_id','sale_id.delivery_date','purchase_id','purchase_id.date_planned')
#     def _compute_scheduled_date(self):
#         if self.sale_id:
#             self.scheduled_date = self.sale_id.delivery_date
#         elif self.purchase_id:
#             self.scheduled_date = self.purchase_id.date_planned

#     @api.multi
#     def button_validate(self):
#         self.ensure_one()
#         if not self.move_lines and not self.move_line_ids:
#             raise UserError(_('Please add some items to move.'))

#         # If no lots when needed, raise error
#         picking_type = self.picking_type_id
#         precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
#         no_quantities_done = all(float_is_zero(move_line.qty_done, precision_digits=precision_digits) for move_line in
#                                  self.move_line_ids.filtered(lambda m: m.state not in ('done', 'cancel')))
#         no_reserved_quantities = all(
#             float_is_zero(move_line.product_qty, precision_rounding=move_line.product_uom_id.rounding) for move_line in
#             self.move_line_ids)
#         if no_reserved_quantities and no_quantities_done:
#             # raise UserError(_(
#             #     'You cannot validate a transfer if no quantites are reserved nor done. To force the transfer, switch in edit more and encode the done quantities.'))

#         if picking_type.use_create_lots or picking_type.use_existing_lots:
#             lines_to_check = self.move_line_ids
#             if not no_quantities_done:
#                 lines_to_check = lines_to_check.filtered(
#                     lambda line: float_compare(line.qty_done, 0,
#                                                precision_rounding=line.product_uom_id.rounding)
#                 )

#             for line in lines_to_check:
#                 product = line.product_id
#                 if product and product.tracking != 'none':
#                     if not line.lot_name and not line.lot_id:
#                         raise UserError(
#                             _('You need to supply a Lot/Serial number for product %s.') % product.display_name)

#         if no_quantities_done:
#             view = self.env.ref('stock.view_immediate_transfer')
#             wiz = self.env['stock.immediate.transfer'].create({'pick_ids': [(4, self.id)]})
#             return {
#                 'name': _('Immediate Transfer?'),
#                 'type': 'ir.actions.act_window',
#                 'view_type': 'form',
#                 'view_mode': 'form',
#                 'res_model': 'stock.immediate.transfer',
#                 'views': [(view.id, 'form')],
#                 'view_id': view.id,
#                 'target': 'new',
#                 'res_id': wiz.id,
#                 'context': self.env.context,
#             }

#         if self._get_overprocessed_stock_moves() and not self._context.get('skip_overprocessed_check'):
#             view = self.env.ref('stock.view_overprocessed_transfer')
#             wiz = self.env['stock.overprocessed.transfer'].create({'picking_id': self.id})
#             return {
#                 'type': 'ir.actions.act_window',
#                 'view_type': 'form',
#                 'view_mode': 'form',
#                 'res_model': 'stock.overprocessed.transfer',
#                 'views': [(view.id, 'form')],
#                 'view_id': view.id,
#                 'target': 'new',
#                 'res_id': wiz.id,
#                 'context': self.env.context,
#             }

#         # Check backorder should check for other barcodes
#         if self._check_backorder():
#             return self.action_generate_backorder_wizard()
#         self.action_done()
#         return


# class SaleAdvancePaymentInv(models.TransientModel):
#     _inherit = "sale.advance.payment.inv"

#     @api.multi
#     def create_invoices(self):
#         sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
#         for sale in sale_orders:
#             for picking in sale.picking_ids:
#                 if picking.state in ('draft', 'waiting', 'confirmed', 'assigned'):
#                     raise UserError(_(
#                         "Validez votre Livraison avant de creer la facture!"))

#         if self.advance_payment_method == 'delivered':
#             sale_orders.action_invoice_create()
#         elif self.advance_payment_method == 'all':
#             sale_orders.action_invoice_create(final=True)
#         else:
#             # Create deposit product if necessary
#             if not self.product_id:
#                 vals = self._prepare_deposit_product()
#                 self.product_id = self.env['product.product'].create(vals)
#                 self.env['ir.config_parameter'].sudo().set_param('sale.default_deposit_product_id', self.product_id.id)

#             sale_line_obj = self.env['sale.order.line']
#             for order in sale_orders:
#                 if self.advance_payment_method == 'percentage':
#                     amount = order.amount_untaxed * self.amount / 100
#                 else:
#                     amount = self.amount
#                 if self.product_id.invoice_policy != 'order':
#                     raise UserError(_(
#                         'The product used to invoice a down payment should have an invoice policy set to "Ordered quantities". Please update your deposit product to be able to create a deposit invoice.'))
#                 if self.product_id.type != 'service':
#                     raise UserError(_(
#                         "The product used to invoice a down payment should be of type 'Service'. Please use another product or update this product."))


#                 taxes = self.product_id.taxes_id.filtered(
#                     lambda r: not order.company_id or r.company_id == order.company_id)
#                 if order.fiscal_position_id and taxes:
#                     tax_ids = order.fiscal_position_id.map_tax(taxes, self.product_id, order.partner_shipping_id).ids
#                 else:
#                     tax_ids = taxes.ids
#                 context = {'lang': order.partner_id.lang}
#                 analytic_tag_ids = []
#                 for line in order.order_line:
#                     analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]
#                 so_line = sale_line_obj.create({
#                     'name': _('Advance: %s') % (time.strftime('%m %Y'),),
#                     'price_unit': amount,
#                     'product_uom_qty': 0.0,
#                     'order_id': order.id,
#                     'discount': 0.0,
#                     'product_uom': self.product_id.uom_id.id,
#                     'product_id': self.product_id.id,
#                     'analytic_tag_ids': analytic_tag_ids,
#                     'tax_id': [(6, 0, tax_ids)],
#                     'is_downpayment': True,
#                 })
#                 del context
#                 self._create_invoice(order, so_line, amount)

#         if self._context.get('open_invoices', False):
#             return sale_orders.action_view_invoice()



#         return {'type': 'ir.actions.act_window_close'}
