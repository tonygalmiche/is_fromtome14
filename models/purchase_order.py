# -*- coding: utf-8 -*-
from odoo import api, fields, models                           # type: ignore
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT          # type: ignore
from odoo.tools.float_utils import float_compare, float_round  # type: ignore

from datetime import datetime, timedelta, date


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.depends('partner_id','is_fromtome_order_id')
    def _compute_is_fromtome_order_vsb(self):
        cr,uid,context,su = self.env.args
        for obj in self:
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


    @api.depends('partner_id')
    def _compute_is_heure_envoi_mail(self):
        for obj in self:
            heure=False
            filtre=[
                ('model','=',self._name),
                ('res_id','=',obj.id),
                ('subject','!=',False),
                
            ]
            messages = self.env['mail.message'].search(filtre, order="date desc")
            for message in messages:
                test=True
                for notification in message.notification_ids:
                    if notification.notification_status!='sent':
                        test=False
                        break
                if test:
                    heure=message.date
                    break
            obj.is_heure_envoi_mail=heure


    is_commande_soldee         = fields.Boolean(string='Commande soldée', default=False, copy=False, help=u"Cocher cette case pour indiquer qu'aucune nouvelle livraison n'est prévue sur celle-ci")
    is_fromtome_order_id       = fields.Many2one('sale.order', 'Commande Fromtome', copy=False,readonly=True)
    is_fromtome_order_vsb      = fields.Boolean(string='Créer commande dans Fromtome vsb', compute='_compute_is_fromtome_order_vsb')
    is_maj_commande_client_vsb = fields.Boolean(string='MAJ commandes clients', compute='_compute_is_maj_commande_client_vsb', readonly=True, store=False)
    is_enseigne_id             = fields.Many2one('is.enseigne.commerciale', 'Enseigne', related='partner_id.is_enseigne_id')
    is_heure_envoi_id          = fields.Many2one(related='partner_id.is_heure_envoi_id')
    is_heure_envoi_mail        = fields.Datetime(string="Heure d'envoi du mail", compute='_compute_is_heure_envoi_mail' )
    is_fusion_order_id         = fields.Many2one('purchase.order', 'Fusionnée dans', copy=False,readonly=True)
    is_date_enlevement         = fields.Date('Date Enlèvement')
    is_adresse_livraison_id    = fields.Many2one('res.partner', 'Adresse Livraison') #, default=lambda self: self.env.user.company_id.partner_id.id)


    @api.onchange('partner_id')
    def onchange_partner_id_is_adresse_livraison_id(self):
        for obj in self:
            if obj.partner_id.is_enseigne_id:
                obj.is_adresse_livraison_id = obj.partner_id.is_enseigne_id.warehouse_id.partner_id.id


    @api.onchange('partner_id')
    def onchange_partner_id_warehouse(self):
        if self.partner_id and self.partner_id.is_warehouse_id:
            self.picking_type_id = self.partner_id.is_warehouse_id.in_type_id.id
        else:
            if self.partner_id and self.partner_id.is_enseigne_id and self.partner_id.is_enseigne_id.warehouse_id:
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
            for line in obj.order_line:
                line._compute_qty_invoiced()
            obj._get_invoiced()
 

    def commande_soldee_action_server(self):
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
        date_reception = date.today()+timedelta(days=2)
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
                        'is_date_reception': date_reception,
                        'order_id'       : order.id,
                    }
                    res=self.env['sale.order.line'].create(vals)
                    line.price_unit = res.price_unit


    def _message_auto_subscribe_notify(self, partner_ids, template):
        "Désactiver les notifications d'envoi des mails"
        return True


    def fusion_commande_action(self):
        "Permet de fusionner les commandes validées et non livrées de la même date et du même fournisseur"
        dict={}
        #** Recherche des commandes par fournissseur et par date **************
        for obj in self:
            if obj.partner_id and obj.date_planned and obj.state=='purchase':
                test=False
                for picking in obj.picking_ids:
                    if picking.state not in ['done','cancel']:
                        test=True
                        break
                if test:
                    key = "%s-%s"%(obj.partner_id.id, obj.date_planned.strftime('%Y-%m-%d'))
                    if key not in dict:
                        dict[key]=[]
                    dict[key].append(obj.id)
        #*** Suppresion des clés avec une seule commande => Pas de fusion *****
        for key in list(dict):
            if len(dict[key])==1:
                dict.pop(key)
        #** Fusion des commandes **********************************************
        for key in dict:
            first_order=False
            orders = dict[key]
            #orders.sort() #Cela permet de conserver la première commande et d'annuler les autres
            for order_id in orders:
                order = self.env['purchase.order'].browse(order_id)
                if not first_order:
                    first_order=order
                else:
                    #** Recherche sequence pour mettre la ligne à la fin ******
                    sequence=0
                    for line in first_order.order_line:
                        if line.sequence>sequence:
                            sequence=line.sequence
                    #**********************************************************
                    for line in order.order_line:

                        #** Recherche si ligne existe pour cet article ********
                        test=False
                        for l in first_order.order_line:
                            if l.product_id == line.product_id:
                                qty = line.product_qty + l.product_qty
                                l.product_qty = qty
                                l.onchange_product_qty_fromtome()
                                test=True
                                break
                        #** Création d'une nouvelle ligne *********************
                        if test==False:
                            sequence+=10
                            vals={
                                'order_id'    : first_order.id,
                                'sequence'    : sequence,
                                'product_id'  : line.product_id.id,
                                'name'        : line.name,
                                'product_qty' : line.product_qty,
                                'product_uom' : line.product_uom.id,
                                'date_planned': line.date_planned,
                                'price_unit'  : 0,
                            }
                            order_line=self.env['purchase.order.line'].create(vals)
                            order_line.onchange_product_id()
                            order_line.product_qty = line.product_qty
                            order_line.onchange_product_qty_fromtome()

                    order.button_cancel()
                    order.is_fusion_order_id = first_order.id
                    msg = "Commande annulée et fusionnée avec %s" % (first_order.name)
                    order.message_post(body=msg)
                    msg = "Fusion de la commande %s" % (order.name)
                    first_order.message_post(body=msg)


    # def _add_supplier_to_product(self):
    #     """Insert a mapping of products to PO lines to be picked up
    #     in supplierinfo's create()"""
    #     self.ensure_one()
    #     po_line_map = {
    #         line.product_id.product_tmpl_id.id: line for line in self.order_line
    #     }
    #     return super(
    #         PurchaseOrder, self.with_context(po_line_map=po_line_map)
    #     )._add_supplier_to_product()





class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.depends('product_id','product_qty','is_nb_colis')
    def _compute_is_nb_pieces_par_colis(self):
        for obj in self:
            nb        = obj.product_id.is_nb_pieces_par_colis
            poids_net = obj.product_id.is_poids_net_colis
            obj.is_nb_pieces_par_colis = nb
            obj.is_poids_net = obj.is_nb_colis * poids_net


    @api.onchange('is_nb_colis')
    def onchange_is_nb_colis(self):
        unite = self.product_uom.category_id.name
        if unite=="Poids":
            self.product_qty =  self.is_nb_colis * self.product_id.is_poids_net_colis
        else:
            self.product_qty =  self.is_nb_colis * self.is_nb_pieces_par_colis


    @api.onchange('product_qty')
    def onchange_product_qty_fromtome(self):
        if self.is_nb_pieces_par_colis>0:
            self.is_nb_colis = self.get_nb_colis()


    def get_nb_colis(self):
        nb        = self.product_id.is_nb_pieces_par_colis
        poids_net = self.product_id.is_poids_net_colis
        unite     = self.product_uom.category_id.name
        nb_colis  = 0
        if unite=="Poids":
            if poids_net>0:
                nb_colis = self.product_qty/poids_net
        else:
            if nb>0:
                nb_colis = self.product_qty / nb
        return round(nb_colis)


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


    @api.depends('product_id','name')
    def _compute_ref(self):
        for obj in self:
            filtre=[
                ('product_tmpl_id', '=', obj.product_id.product_tmpl_id.id),
                ('name'           , '=', obj.order_id.partner_id.id),
            ]
            ref=False
            suppliers=self.env['product.supplierinfo'].search(filtre,limit=1)
            for s in suppliers:
                ref=s.product_code
            obj.is_ref_fournisseur = ref
            obj.is_default_code = obj.product_id.default_code


    is_sale_order_line_id  = fields.Many2one('sale.order.line', string=u'Ligne commande client', index=True)
    is_nb_pieces_par_colis = fields.Integer(string='PCB', compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    #is_nb_colis            = fields.Float(string='Nb Colis', digits=(14,2) , compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_nb_colis            = fields.Float(string='Nb Colis', digits=(14,2))
    is_poids_net           = fields.Float(string='Poids net', digits='Stock Weight', compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True, help="Poids net total (Kg)")
    is_alerte              = fields.Text(string='Alerte', compute='_compute_is_alerte')
    is_client_id           = fields.Many2one('res.partner', 'Client', related='is_sale_order_line_id.order_id.partner_id')
    is_date_planned        = fields.Datetime(string="Date de réception", related='order_id.date_planned')
    is_date_enlevement     = fields.Date(related='order_id.is_date_enlevement')
    is_default_code        = fields.Char(string='Réf Fromtome'   , compute='_compute_ref', readonly=True, store=True)
    is_ref_fournisseur     = fields.Char(string='Réf Fournisseur', compute='_compute_ref', readonly=True, store=True)
    discount               = fields.Float(string="Remise (%)", digits="Discount")

    _sql_constraints = [
        (
            "discount_limit",
            "CHECK (discount <= 100.0)",
            "Discount must be lower than 100%.",
        )
    ]


    # adding discount to depends
    @api.depends("discount")
    def _compute_amount(self):
        return super()._compute_amount()

    def _prepare_compute_all_values(self):
        vals = super()._prepare_compute_all_values()
        vals.update({"price_unit": self._get_discounted_price_unit()})
        return vals


    def _get_discounted_price_unit(self):
        """Inheritable method for getting the unit price after applying
        discount(s).

        :rtype: float
        :return: Unit price after discount(s).
        """
        self.ensure_one()
        if self.discount:
            return self.price_unit * (1 - self.discount / 100)
        return self.price_unit

    def _get_stock_move_price_unit(self):
        """Get correct price with discount replacing current price_unit
        value before calling super and restoring it later for assuring
        maximum inheritability.

        HACK: This is needed while https://github.com/odoo/odoo/pull/29983
        is not merged.
        """
        price_unit = False
        price = self._get_discounted_price_unit()
        if price != self.price_unit:
            # Only change value if it's different
            price_unit = self.price_unit
            self.price_unit = price
        price = super()._get_stock_move_price_unit()
        if price_unit:
            self.price_unit = price_unit
        return price

    @api.onchange("product_qty", "product_uom")
    def _onchange_quantity(self):
        """
        Check if a discount is defined into the supplier info and if so then
        apply it to the current purchase order line
        """
        res = super()._onchange_quantity()
        if self.product_id:
            date = None
            if self.order_id.date_order:
                date = self.order_id.date_order.date()
            seller = self.product_id._select_seller(
                partner_id=self.partner_id,
                quantity=self.product_qty,
                date=date,
                uom_id=self.product_uom,
            )
            self._apply_value_from_seller(seller)
        return res

    @api.model
    def _apply_value_from_seller(self, seller):
        """Overload this function to prepare other data from seller,
        like in purchase_triple_discount module"""
        if not seller:
            return
        self.discount = seller.discount

    def _prepare_account_move_line(self, move=False):
        vals = super(PurchaseOrderLine, self)._prepare_account_move_line(move)
        vals["discount"] = self.discount
        return vals

    @api.model
    def _prepare_purchase_order_line(
        self, product_id, product_qty, product_uom, company_id, supplier, po
    ):
        """Apply the discount to the created purchase order"""
        res = super()._prepare_purchase_order_line(
            product_id, product_qty, product_uom, company_id, supplier, po
        )
        partner = supplier.name
        uom_po_qty = product_uom._compute_quantity(product_qty, product_id.uom_po_id)
        seller = product_id.with_company(company_id)._select_seller(
            partner_id=partner,
            quantity=uom_po_qty,
            date=po.date_order and po.date_order.date(),
            uom_id=product_id.uom_po_id,
        )
        res.update(self._prepare_purchase_order_line_from_seller(seller))
        return res

    @api.model
    def _prepare_purchase_order_line_from_seller(self, seller):
        """Overload this function to prepare other data from seller,
        like in purchase_triple_discount module"""
        if not seller:
            return {}
        return {"discount": seller.discount}


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


    def _create_or_update_picking(self):
        """"
            Remplacement de cette methode standard le 06/08/2025 pour revoir 
            la mise à jour du picking lors de la mise à jour de la commande
        """
        for line in self:
            qty = line.product_qty - line.qty_received
            if qty<0:
                qty=0

            #** Ne pas modifier le picking si la ligne est déja facturée
            if line.qty_invoiced==0:
                domain=[
                    ('purchase_line_id', '=', line.id),
                ]
                moves=self.env['stock.move'].search(domain)
                create=True
                for move in moves:
                    #Modifier le mouvement uniquement si le picking et le stock.move sont en cours
                    if move.picking_id not in ['draft','done', 'cancel']:
                        if move.state not in ['draft','done', 'cancel']:
                            create=False
                            move.product_uom_qty = qty
                            break
                #** Création du stock.move si non trouvé précédemment
                if create:
                    pickings = line.order_id.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel') and x.location_dest_id.usage in ('internal', 'transit', 'customer'))
                    for picking in pickings:
                        vals={
                            "picking_id"        : picking.id,
                            "product_id"        : line.product_id.id,
                            "company_id"        : picking.company_id.id,
                            "product_uom_id"    : line.product_id.uom_id.id,
                            "location_id"       : picking.location_id.id,
                            "location_dest_id"  : picking.location_dest_id.id,
                        }
                        res = self.env['stock.move.line'].create(vals)
                        res.move_id.product_uom_qty = qty
                        res.move_id.purchase_line_id = line.id
                        break


