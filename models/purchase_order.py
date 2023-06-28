# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"


    @api.depends('partner_id','is_fromtome_order_id')
    def _compute_is_fromtome_order_vsb(self):
        cr,uid,context,su = self.env.args



        for obj in self:

            print(self.env.user.company_id.partner_id,obj.partner_id)



            vsb=True
            if self.env.user.company_id.partner_id!=obj.partner_id:
                vsb=False
            if obj.is_fromtome_order_id:
                vsb=False
            obj.is_fromtome_order_vsb=vsb


    @api.depends('order_line.date_planned')
    def _compute_date_planned(self):
        for order in self:
            print(order)


    @api.depends('order_line')
    def _compute_is_maj_commande_client_vsb(self):
        company = self.env.user.company_id
        for obj in self:
            vsb = False
            if company.is_regroupe_cde=="Non":
                for line in obj.order_line:
                    if line.is_sale_order_line_id:
                        if line.is_sale_order_line_id.product_uom_qty != line.product_qty:
                            vsb=True
                            break
            obj.is_maj_commande_client_vsb=vsb


    is_commande_soldee         = fields.Boolean(string='Commande soldée', default=False, copy=False, help=u"Cocher cette case pour indiquer qu'aucune nouvelle livraison n'est prévue sur celle-ci")
    is_fromtome_order_id       = fields.Many2one('sale.order', 'Commande Fromtome', copy=False,readonly=True)
    is_fromtome_order_vsb      = fields.Boolean(string='Créer commande dans Fromtome vsb', compute='_compute_is_fromtome_order_vsb')
    is_maj_commande_client_vsb = fields.Boolean(string='MAJ commandes clients', compute='_compute_is_maj_commande_client_vsb', readonly=True, store=False)
    is_enseigne_id             = fields.Many2one('is.enseigne.commerciale', 'Enseigne', related='partner_id.is_enseigne_id')



    @api.onchange('partner_id')
    def onchange_partner_id_warehouse(self):

        print("onchange_partner_id_warehouse",self)

        if self.partner_id and self.partner_id.is_warehouse_id:
            print(self,self.partner_id.is_warehouse_id.in_type_id)
            self.picking_type_id = self.partner_id.is_warehouse_id.in_type_id.id
        else:
            if self.partner_id and self.partner_id.is_enseigne_id and self.partner_id.is_enseigne_id.warehouse_id:

                print(self,self.partner_id.is_enseigne_id.warehouse_id.in_type_id.id)


                self.picking_type_id = self.partner_id.is_enseigne_id.warehouse_id.in_type_id.id
 

    def maj_commande_client_action(self):
        for obj in self:
            for line in obj.order_line:
                if line.is_sale_order_line_id:
                    line.is_sale_order_line_id.product_uom_qty = line.product_qty


    def commande_fournisseur_entierement_facturee_action_server(self):
        for obj in self:
            obj.invoice_status = "invoiced"


    def initialisation_etat_facturee_fournisseur_action_server(self):
        for obj in self:
            obj._get_invoiced()
 

    def commande_soldee_action_server(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            solde=False
            if obj.state not in ["draft","sent","to_approve"]:
                solde=True
                filtre=[
                    ('purchase_id','=',obj.id),
                    ('state','not in',['done','cancel']),
                ]

                pickings = self.env['stock.picking'].search(filtre)
                for picking in pickings:
                    solde=False
            obj.is_commande_soldee=solde


    def creer_commande_fromtome_action(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            vals={
                #'company_id': 1,
                'partner_id': obj.partner_id.id,
                'user_id'   : uid,
            }
            order=self.env['sale.order'].create(vals)
            obj.is_fromtome_order_id=order.id
            if order:
                for line in obj.order_line:
                    vals={
                        'sequence'  : line.sequence,
                        'product_id': line.product_id.id,
                        'name'      : line.product_id.name,
                        'product_uom_qty': line.product_qty,
                        'order_id'       : order.id,
                    }
                    res=self.env['sale.order.line'].create(vals)
                    line.price_unit = res.price_unit


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.depends('product_id','product_qty')
    def _compute_is_nb_pieces_par_colis(self):
        for obj in self:
            nb        = obj.product_id.is_nb_pieces_par_colis
            poids_net = obj.product_id.is_poids_net_colis
            unite     = obj.product_uom.category_id.name
            obj.is_nb_pieces_par_colis = nb
            nb_colis  = 0
            if unite=="Poids":
                if poids_net>0:
                    nb_colis = obj.product_qty/poids_net
            else:
                if nb>0:
                    nb_colis = obj.product_qty / nb
            obj.is_nb_colis = nb_colis
            obj.is_poids_net = nb_colis * poids_net


    @api.depends('product_id','is_nb_colis','price_unit')
    def _compute_is_alerte(self):
        for obj in self:
            alerte=[]
            if obj.is_nb_colis!=round(obj.is_nb_colis):
                alerte.append("Colis incomplet")
            if obj.is_nb_colis==0:
                alerte.append("Colis à 0")
            if obj.price_unit==0:
                alerte.append("Prix à 0")
            obj.is_alerte="\n".join(alerte)


    is_sale_order_line_id  = fields.Many2one('sale.order.line', string=u'Ligne commande client', index=True)
    is_nb_pieces_par_colis = fields.Integer(string='PCB', compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_nb_colis            = fields.Float(string='Nb Colis', digits=(14,2) , compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_poids_net           = fields.Float(string='Poids net', digits='Stock Weight', compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True, help="Poids net total (Kg)")
    is_alerte              = fields.Text(string='Alerte', compute='_compute_is_alerte')
    is_client_id           = fields.Many2one('res.partner', 'Client', related='is_sale_order_line_id.order_id.partner_id')
    is_date_planned        = fields.Datetime(string="Date de réception", related='order_id.date_planned')
    is_date_enlevement     = fields.Date(related='order_id.is_date_enlevement')


    def acceder_commande_client(self):
        for obj in self:
            res= {
                'name': 'Ligne commande client',
                'view_mode': 'tree,form',
                'view_type': 'form',
                'res_model': 'sale.order.line',
                'type': 'ir.actions.act_window',
                'domain': [
                    ('id','=',obj.is_sale_order_line_id.id),
                ],
            }
            return res


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    is_date_enlevement      = fields.Date('Date Enlèvement')
    is_adresse_livraison_id = fields.Many2one('res.partner', 'Adresse Livraison', default=lambda self: self.env.user.company_id.partner_id.id)

