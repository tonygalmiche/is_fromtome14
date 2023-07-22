# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'


    @api.depends('product_id','quantity')
    def _compute_is_nb_pieces_par_colis(self):
        for obj in self:
            obj.is_nb_pieces_par_colis = obj.product_id.is_nb_pieces_par_colis
            poids_net = 0
            nb_colis  = 0
            if obj.purchase_line_id.move_ids:
                for line in obj.purchase_line_id.move_ids.move_line_ids:
                    poids_net+=line.is_poids_net_reel
                    nb_colis+=line.is_nb_colis
            if obj.sale_line_ids.move_ids:
                for line in obj.sale_line_ids.move_ids.move_line_ids:
                    poids_net+=line.is_poids_net_reel
                    nb_colis+=line.is_nb_colis

            # Ajout du 06/07/22 pour Le Cellier
            if nb_colis==0:
                if obj.purchase_line_id.move_ids:
                    for line in obj.purchase_line_id.move_ids:
                        nb_colis+=line.is_nb_colis
                if obj.sale_line_ids.move_ids:
                    for line in obj.sale_line_ids.move_ids:
                        nb_colis+=line.is_nb_colis
                poids_net = nb_colis* obj.product_id.is_poids_net_colis


            obj.is_poids_net = poids_net
            obj.is_nb_colis = nb_colis


    @api.depends('sale_line_ids')
    def _compute_is_lots(self):
        for obj in self:
            lots=[]
            for line in obj.sale_line_ids:
                for move in line.move_ids:
                    lots.append(move.is_lots)
            obj.is_lots= (lots and "\r".join(lots)) or False


    is_nb_pieces_par_colis = fields.Integer(string='PCB', compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_nb_colis            = fields.Float(string='Nb Colis', digits=(14,2) , compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_poids_net           = fields.Float(string='Poids net', digits=(14,4), compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True, help="Poids net total (Kg)")
    is_lots                = fields.Text('Lots', compute='_compute_is_lots')


    def stock_move_line_action(self):
        for obj in self:
            ids=[]
            if obj.sale_line_ids.move_ids:
                for line in obj.sale_line_ids.move_ids.move_line_ids:
                    ids.append(line.id)
            if obj.purchase_line_id.move_ids:
                for line in obj.purchase_line_id.move_ids.move_line_ids:
                    ids.append(line.id)
            res= {
                'name': 'Picking',
                'view_mode': 'tree,form',
                'view_type': 'form',
                'res_model': 'is.stock.move.line',
                'type': 'ir.actions.act_window',
                'domain': [
                    ('move_line_id','in',ids),
                ],
            }
            return res


class AccountMove(models.Model):
    _inherit = 'account.move'


    @api.depends('invoice_line_ids')
    def _compute_is_alerte(self):
        for obj in self:
            alerte=''
            for line in obj.invoice_line_ids:
                if line.price_unit==0:
                    alerte = "Prix facturé à 0"
                if line.price_unit>=9999:
                    alerte = "Prix facturé > 9999"
            obj.is_alerte=alerte


    @api.depends('invoice_line_ids')
    def _is_ref_client_int_cde(self):
        for obj in self:
            ref_client=[]
            ref_int=[]
            for line in obj.invoice_line_ids:
                for sale_line in line.sale_line_ids:
                    x = sale_line.order_id.name
                    if x and x not in ref_int:
                        ref_int.append(x)
                    x = sale_line.order_id.client_order_ref
                    if x and x not in ref_client:
                        ref_client.append(x)
            obj.is_ref_int_cde = (ref_int    and "\n".join(ref_int))    or False
            obj.is_ref_client  = (ref_client and "\n".join(ref_client)) or False



    @api.depends('invoice_line_ids')
    def _is_is_bl(self):
        for obj in self:
            bl=[]
            for line in obj.invoice_line_ids:
                for sale_line in line.sale_line_ids:
                    for move in sale_line.move_ids:
                        x = move.picking_id.name
                        if x and x not in bl:
                            bl.append(x)
            obj.is_bl  = (bl and "\n".join(bl)) or False


    @api.depends('invoice_line_ids')
    def _compute_poids_colis(self):
        for obj in self:
            poids=0
            colis=0
            for line in obj.invoice_line_ids:
                poids+=line.is_poids_net
                colis+=line.is_nb_colis
            obj.is_poids_net = poids
            obj.is_nb_colis  = colis


    is_enseigne_id      = fields.Many2one('is.enseigne.commerciale', 'Enseigne', related='partner_id.is_enseigne_id')
    is_export_compta_id = fields.Many2one('is.export.compta', 'Folio', copy=False)
    is_alerte           = fields.Text('Alerte', copy=False, compute=_compute_is_alerte)
    is_ref_client       = fields.Text('Ref Client' , compute='_is_ref_client_int_cde')
    is_ref_int_cde      = fields.Text('Ref Int Cde', compute='_is_ref_client_int_cde')
    is_bl               = fields.Text('BL'         , compute='_is_is_bl')
    is_poids_net        = fields.Float(string='Poids net', digits=(14,3), compute='_compute_poids_colis')
    is_nb_colis         = fields.Float(string='Nb colis' , digits=(14,1), compute='_compute_poids_colis')


    def write(self, vals):
        res = super(AccountMove, self).write(vals)
        #** Mettre la ligne des frais de port à la fin ************************
        for obj in self:
            if obj.partner_id.is_frais_port_id:
                max=0
                for line in obj.line_ids:
                    if line.product_id!=obj.partner_id.is_frais_port_id:
                        if line.sequence>max:
                            max=line.sequence
                for line in obj.line_ids:
                    if line.product_id==obj.partner_id.is_frais_port_id:
                        line.sequence=max+10
        #**********************************************************************
        return res


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_export_compta_id = fields.Many2one('is.export.compta', 'Folio', copy=False)



# class AccountInvoice(models.Model):
#     _inherit = 'account.invoice'

#     comment = fields.Text('Additional Information', translate=True , readonly=True, states={'draft': [('readonly', False)]})

#     # Load all unsold PO lines
#     @api.onchange('purchase_id')
#     def purchase_order_change(self):
#         if not self.purchase_id:
#             return {}
#         if not self.partner_id:
#             self.partner_id = self.purchase_id.partner_id.id

#         vendor_ref = self.purchase_id.partner_ref
#         if vendor_ref and (not self.reference or (
#                 vendor_ref + ", " not in self.reference and not self.reference.endswith(vendor_ref))):
#             self.reference = ", ".join([self.reference, vendor_ref]) if self.reference else vendor_ref

#         if not self.invoice_line_ids:
#             # as there's no invoice line yet, we keep the currency of the PO
#             self.currency_id = self.purchase_id.currency_id

#         new_lines = self.env['account.invoice.line']
#         for line in self.purchase_id.order_line - self.invoice_line_ids.mapped('purchase_line_id'):
#             if line.move_ids:
#                 data = self._prepare_invoice_line_from_po_line(line)
#                 new_line = new_lines.new(data)
#                 new_line._set_additional_fields(self)
#                 new_lines += new_line
#             else:
#                 continue

#         self.invoice_line_ids += new_lines
#         self.payment_term_id = self.purchase_id.payment_term_id
#         self.env.context = dict(self.env.context, from_purchase_order_change=True)
#         self.purchase_id = False
#         return {}

#     def _prepare_invoice_line_from_po_line(self, line):
#         if line.product_id.purchase_method == 'purchase':
#             qty = line.product_qty - line.qty_invoiced
#         else:
#             qty = line.qty_received - line.qty_invoiced
#         if float_compare(qty, 0.0, precision_rounding=line.product_uom.rounding) <= 0:
#             qty = 0.0
#         taxes = line.taxes_id
#         invoice_line_tax_ids = line.order_id.fiscal_position_id.map_tax(taxes, line.product_id, line.order_id.partner_id)
#         invoice_line = self.env['account.invoice.line']
#         date = self.date or self.date_invoice
#         if line.move_ids:
#             self._cr.execute("""select weight, weight_uom_id, lot_name from stock_move where id in %s and state != 'cancel' limit 1 """,
#                          (tuple(line.move_ids.ids),))


#         res = self._cr.dictfetchone()
#         weight = 0
#         lot_name = ''
#         if res and res['weight']:
#             weight = res['weight']
#         if res and res['lot_name']:
#             lot_name = res['lot_name']
#         if res and res['weight_uom_id']:
#             weight_uom_id = res['weight_uom_id']
#         else:
#             weight_uom_id = False
#         if lot_name:
#             line_name = line.order_id.name + ': ' + line.name + '\n' + lot_name + '\n'
#         else:
#             line_name = line.order_id.name + ': ' + line.name + '\n'
#         data = {
#             'purchase_line_id': line.id,
#             'name': line_name ,
#             'origin': line.order_id.origin,
#             'uom_id': weight_uom_id or line.product_uom.id,
#             'product_id': line.product_id.id,
#             'account_id': invoice_line.with_context
#                 ({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account(),
#             'price_unit': line.order_id.currency_id._convert(
#                 line.price_unit, self.currency_id, line.company_id, date or fields.Date.today(), round=False),
#             # 'quantity': qty,
#             'quantity': weight or qty,
#             'discount': 0.0,
#             'account_analytic_id': line.account_analytic_id.id,
#             'analytic_tag_ids': line.analytic_tag_ids.ids,
#             'invoice_line_tax_ids': invoice_line_tax_ids.ids
#         }
#         account = invoice_line.get_invoice_line_account('in_invoice', line.product_id, line.order_id.fiscal_position_id, self.env.user.company_id)
#         if account:
#             data['account_id'] = account.id
#         return data

#     def picking_notes(self):
#         for s in self:
#             if s.picking_note:
#                 pick_note = s.picking_note
#             else:
#                 pick_note = ""
#             for picking in s.picking_ids:
#                 for line in picking.move_ids_without_package:
#                     print('nnnnnnn', line.note)
#                     if line.note:
#                         pick_note = pick_note + line.product_id.product_tmpl_id.name +": "  + line.note + '\n'

#             s.picking_note = pick_note

#     picking_note = fields.Text('Notes Transfert Articles', compute=picking_notes)



#     def _compute_is_alerte(self):
#         for obj in self:
#             alerte=''
#             for line in obj.invoice_line_ids:
#                 if line.price_unit==0:
#                     alerte = "Prix facturé à 0"
#                 if line.price_unit>=9999:
#                     alerte = "Prix facturé > 9999"
#             obj.is_alerte=alerte

#     is_export_compta_id = fields.Many2one('is.export.compta', 'Folio', copy=False)
#     is_alerte = fields.Text('Alerte', copy=False, compute=_compute_is_alerte)


# class AccountInvoiceLine(models.Model):
#     _inherit = 'account.invoice.line'

#     def _compute_is_colise(self):
#         for obj in self:
#             colis=0
#             for move in obj.move_line_ids:
#                 colis+=move.quantity_done
#             obj.is_colis = colis


#     @api.depends('product_id','quantity')
#     def _compute_is_nb_pieces_par_colis(self):
#         for obj in self:
#             nb = obj.product_id.is_nb_pieces_par_colis
#             obj.is_nb_pieces_par_colis = obj.product_id.is_nb_pieces_par_colis
#             nb_colis = False
#             if nb>0:
#                 nb_colis = obj.quantity / nb
#             obj.is_nb_colis = nb_colis
#             obj.is_poids_net = obj.quantity * obj.product_id.is_poids_net_colis


#     is_colis = fields.Integer('Colis', compute=_compute_is_colise)
#     is_nb_pieces_par_colis = fields.Integer(string='Nb Pièces / colis'     , compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
#     is_nb_colis            = fields.Float(string='Nb Colis', digits=(14,2) , compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
#     is_poids_net           = fields.Float(string='Poids net', digits=(14,4), compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True, help="Poids net total (Kg)")


