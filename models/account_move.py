# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime, date, timedelta


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
            alertes=[]
            nb_frais_de_port=0
            for line in obj.invoice_line_ids:
                if line.product_id.categ_id.name=='TRANSPORT':
                    nb_frais_de_port+=1
                if line.price_unit==0:
                    alertes.append("Prix facturé à 0")
                if line.price_unit>=9999:
                    alertes.append("Prix facturé > 9999")

            if nb_frais_de_port>1:
                alertes.append("Il y a %s lignes de frais de port"%nb_frais_de_port)



            alerte=False
            if len(alertes)>0:
                alerte = '\n'.join(alertes)
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


    @api.depends('partner_id')
    def _compute_is_enseigne_id(self):
        for obj in self:
            obj.is_enseigne_id = obj.partner_id.is_enseigne_id.id
        

    @api.depends('state','amount_total','amount_residual')
    def _compute_is_date_delai_paiement(self):
        for obj in self:
            date_paiement = False
            delai_paiement = False
            if obj.state == 'posted' and obj.is_invoice(include_receipts=True):
                payments = obj._get_reconciled_info_JSON_values()
                for payment in payments:
                    if date_paiement==False:
                        date_paiement = payment['date']
                    if payment['date']>date_paiement:
                        date_paiement = payment['date']
            if date_paiement:
                delai_paiement=(date_paiement-obj.invoice_date).days
            obj.is_date_paiement  = date_paiement
            obj.is_delai_paiement = delai_paiement


    is_enseigne_id      = fields.Many2one('is.enseigne.commerciale', 'Enseigne', compute='_compute_is_enseigne_id', store=True, readonly=False) #, related='partner_id.is_enseigne_id')
    is_export_compta_id = fields.Many2one('is.export.compta', 'Folio', copy=False)
    is_alerte           = fields.Text('Alerte', copy=False, compute=_compute_is_alerte)
    is_ref_client       = fields.Text('Ref Client' , compute='_is_ref_client_int_cde')
    is_ref_int_cde      = fields.Text('Ref Int Cde', compute='_is_ref_client_int_cde')
    is_bl               = fields.Text('BL'         , compute='_is_is_bl')
    is_poids_net        = fields.Float(string='Poids net', digits=(14,3), compute='_compute_poids_colis')
    is_nb_colis         = fields.Float(string='Nb colis' , digits=(14,1), compute='_compute_poids_colis')
    is_date_relance     = fields.Date(string='Date dernière relance', readonly=1)
    is_date_releve      = fields.Date(string='Date dernier relevé'  , readonly=1)
    is_motif_avoir_id   = fields.Many2one('is.motif.avoir', "Motif de l'avoir")
    is_date_paiement    = fields.Date(string='Date paiement'       , compute='_compute_is_date_delai_paiement', store=True, readonly=True)
    is_delai_paiement   = fields.Integer(string='Délai de paiement', compute='_compute_is_date_delai_paiement', store=True, readonly=True)
    is_type_avoir       = fields.Selection([
        ('avoir_prix'    , 'Avoir sur prix'),
        ('avoir_quantite', 'Avoir sur quantité'),
    ], 'Type avoir', default="avoir_quantite", copy=False)


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


    def _message_auto_subscribe_notify(self, partner_ids, template):
        "Désactiver les notifications d'envoi des mails"
        return True


    def action_invoice_sent(self):
        for invoice in self:        
            invoice.sudo().message_follower_ids.unlink()
        res = super(AccountMove, self).action_invoice_sent()
        return res


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_export_compta_id = fields.Many2one('is.export.compta', 'Folio', copy=False)


class IsMotifAvoir(models.Model):
    _name = "is.motif.avoir"
    _description = "Motif avoir"
    _order = "name"
    name = fields.Char("Motif avoir", required=True)


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    is_motif_avoir_id = fields.Many2one('is.motif.avoir', "Motif de l'avoir")


    @api.onchange('is_motif_avoir_id')
    def onchange_action_curative_date(self):
        for obj in self:
            if obj.is_motif_avoir_id:
                obj.reason=obj.is_motif_avoir_id.name
