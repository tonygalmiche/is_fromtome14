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
    is_date_relance     = fields.Date(string='Date dernière relance')


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


    # def relance_facture_action(self):
    #     for obj in self:
    #         print(obj.name)






class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_export_compta_id = fields.Many2one('is.export.compta', 'Folio', copy=False)


