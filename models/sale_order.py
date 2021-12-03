# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, Warning
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
import time
from odoo.osv import expression
import datetime


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

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
    is_poids_net              = fields.Float(string='Poids net', digits='Stock Weight', compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True, help="Poids net total (Kg)")
    is_correction_prix_achat  = fields.Float(string="Correction Prix d'achat", digits='Product Price', help="Utilsé dans 'Lignes des mouvements valorisés'")


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

    is_date_livraison        = fields.Date('Date Livraison (ancien champ non utilisé')
    is_commande_soldee       = fields.Boolean(string=u'Commande soldée', default=False, copy=False, help=u"Cocher cette case pour indiquer qu'aucune nouvelle livraison n'est prévue sur celle-ci")
    is_frequence_facturation = fields.Selection(string='Fréquence facturation', related="partner_id.is_frequence_facturation", selection=[('au_mois', 'Au mois'),('a_la_livraison', 'A la livraison')])

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


    def commande_soldee_action_server(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            solde=False
            if obj.state not in ["draft","sent"]:
                solde=True
                SQL="""
                    SELECT id, sale_id, state
                    FROM stock_picking
                    WHERE state not in ('done','cancel') and sale_id=%s
                    limit 1
                """
                cr.execute(SQL,[obj.id])
                for row in cr.fetchall():
                    solde=False
            obj.is_commande_soldee=solde



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
                            filtre.append(('is_adresse_livraison_id','=', obj.partner_shipping_id.id))
                        orders=self.env['purchase.order'].search(filtre,limit=1)
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
                                    order.is_adresse_livraison_id = obj.partner_shipping_id.id

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





