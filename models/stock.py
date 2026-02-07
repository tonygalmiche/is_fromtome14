# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class StockProductionLot(models.Model):
    _inherit = "stock.production.lot"

    is_article_actif = fields.Boolean('Article actif', related='product_id.active')
    is_dlc_ddm       = fields.Date('DLC / DDM', required=True)
    active           = fields.Boolean("Actif", default=True)


    def _check_create(self):
        "Autorise tout le temps la création des lots"
        return True


    @api.constrains('name', 'product_id', 'company_id', 'is_dlc_ddm')
    def _check_unique_lot(self):
        domain = [
            ('product_id', 'in', self.product_id.ids),
            ('company_id', 'in', self.company_id.ids),
            ('name', 'in', self.mapped('name')),
            ('is_dlc_ddm', 'in', self.mapped('is_dlc_ddm')),
        ]
        fields = ['company_id' , 'product_id', 'name', 'is_dlc_ddm']
        groupby = ['company_id', 'product_id', 'name', 'is_dlc_ddm']
        records = self.read_group(domain, fields, groupby, lazy=False)
        error_message_lines = []
        for rec in records:
            if rec['__count'] != 1:
                product_name = self.env['product.product'].browse(rec['product_id'][0]).display_name
                error_message_lines.append(_(" - Product: %s, Serial Number: %s", product_name, rec['name']))
        if error_message_lines:
            raise ValidationError(_('The combination of serial number and product must be unique across a company.\nFollowing combination contains duplicates:\n') + '\n'.join(error_message_lines))


    def archiver_lot_action_server(self):
        for obj in self:
            if obj.product_qty==0:
                obj.active=False

 
class StockMove(models.Model):
    _inherit = "stock.move"

    created_purchase_line_id = fields.Many2one('purchase.order.line',
        'Created Purchase Order Line', ondelete='set null', readonly=True, copy=False, index=True)

    @api.depends('move_line_ids')
    def _compute_is_alerte(self):
        for obj in self:
            if obj.picking_id:
                alerte=False
                state=obj.picking_id.state
                if state in ['draft', 'cancel', 'waiting', 'confirmed']:
                    alerte=False
                else:
                    if obj.picking_id.scheduled_date:
                        date=obj.picking_id.scheduled_date.date()
                        if state=='assigned' and date<datetime.now().date():
                            date=datetime.now().date()
                        alerte=[]
                        if len(alerte)>0:
                            alerte='\n'.join(alerte)
                        else:
                            alerte=False
                obj.is_alerte=alerte


    @api.depends('move_line_ids')
    def _compute_is_lots(self):
        for obj in self:
            lots={}
            for line in obj.move_line_ids:
                if line.lot_id:
                    cle="%s-%s-%s"%(obj.product_id.id,line.lot_id.name,line.is_dlc_ddm)
                    if cle not in lots:
                        dlc = (line.is_dlc_ddm and line.is_dlc_ddm.strftime('%d/%m/%Y')) or ''
                        lots[cle]=[(line.lot_id.name or ''),(line.is_type_tracabilite or '').upper(),dlc,0,0,0]
                    lots[cle][3]+=line.qty_done
                    lots[cle][4]+=line.is_nb_colis
                    lots[cle][5]+=line.is_poids_net_reel
            t=[]
            for lot in lots:
                l=lots[lot]
                x="Lot:%s - %s:%s - Colis:%.1f - Poids:%.1f"%(l[0],l[1],l[2],l[4],l[5])
                t.append(x)
            obj.is_lots = "\n".join(t)


    @api.depends('move_line_ids','move_line_ids.is_nb_colis','move_line_ids.is_poids_net_reel','quantity_done')
    def _compute_is_nb_colis_poids(self):
        for obj in self:
            nb=0
            poids=poids_net=0
            for line in obj.move_line_ids:
                nb+=line.is_nb_colis
                poids+=line.is_poids_net_reel
            # Ajout du 06/07/22 pour Le Cellier
            if nb==0:
                nb        = obj.product_id.is_nb_pieces_par_colis
                poids_net = obj.product_id.is_poids_net_colis
                unite     = obj.product_uom.category_id.name
                nb_colis  = 0
                if unite=="Poids":
                    if poids_net>0:
                        nb_colis = obj.quantity_done/poids_net
                else:
                    if nb>0:
                        nb_colis = obj.quantity_done / nb
                nb=nb_colis
                poids = nb_colis * poids_net
            obj.is_nb_colis       = nb
            obj.is_poids_net_reel = poids
 

    @api.depends('product_uom_qty','product_id')
    def _compute_is_nb_colis_cde(self):
        for obj in self:
            nb        = obj.product_id.is_nb_pieces_par_colis
            poids_net = obj.product_id.is_poids_net_colis
            unite     = obj.product_uom.category_id.name
            nb_colis  = 0
            if unite=="Poids":
                if poids_net>0:
                    nb_colis = obj.product_uom_qty/poids_net
            else:
                if nb>0:
                    nb_colis = obj.product_uom_qty / nb
            obj.is_nb_colis_cde=nb_colis


    @api.onchange('product_id')
    def _compute_is_description_cde(self):
        for obj in self:
            description = obj.description_picking
            if obj.sale_line_id:
                description = obj.sale_line_id.name
            if obj.purchase_line_id:
                description = obj.purchase_line_id.name
            obj.is_description_cde=description



    @api.depends('product_id','name')
    def _compute_is_ref_fournisseur(self):
        for obj in self:
            filtre=[
                ('product_tmpl_id', '=', obj.product_id.product_tmpl_id.id),
                #('name'           , '=', obj.order_id.partner_id.id),
            ]
            ref=False
            suppliers=self.env['product.supplierinfo'].search(filtre,limit=1)
            for s in suppliers:
                ref=s.product_code
            obj.is_ref_fournisseur = ref


    @api.depends('sale_line_id', 'sale_line_id.is_nb_colis')
    def _compute_is_nb_colis_cde_from_sale(self):
        """Récupère le nombre de colis de la ligne de commande client"""
        for obj in self:
            obj.is_nb_colis_cde_from_sale = obj.sale_line_id.is_nb_colis if obj.sale_line_id else 0.0


    @api.depends('sale_line_id', 'sale_line_id.is_poids_net')
    def _compute_is_poids_net_cde_from_sale(self):
        """Récupère le poids net de la ligne de commande client"""
        for obj in self:
            obj.is_poids_net_cde_from_sale = obj.sale_line_id.is_poids_net if obj.sale_line_id else 0.0


    is_alerte          = fields.Text('Alerte', copy=False, compute=_compute_is_alerte)
    is_lots            = fields.Text('Lots'  , copy=False, compute=_compute_is_lots)
    is_nb_colis_cde    = fields.Float('Nb Colis Cde'  , digits=(14,2), compute=_compute_is_nb_colis_cde)
    is_nb_colis        = fields.Float('Nb Colis'      , digits=(14,2), compute=_compute_is_nb_colis_poids, readonly=True, store=True)
    is_poids_net_reel  = fields.Float('Poids net réel', digits=(14,4), compute=_compute_is_nb_colis_poids, readonly=True, store=True)
    is_nb_colis_cde_from_sale = fields.Float('Nb Colis commandé', digits=(14,2), compute='_compute_is_nb_colis_cde_from_sale', readonly=True, store=True, help="Nombre de colis de la ligne de commande client")
    is_poids_net_cde_from_sale = fields.Float('Poids net commandé', digits=(14,4), compute='_compute_is_poids_net_cde_from_sale', readonly=True, store=True, help="Poids net de la ligne de commande client")
    is_description_cde = fields.Text('Description commande', compute=_compute_is_description_cde)
    is_ref_fournisseur = fields.Char(string='Réf fournisseur', compute='_compute_is_ref_fournisseur', readonly=True, store=True)
    is_fournisseur_id          = fields.Many2one('res.partner', 'Fournisseur', readonly=True)
    is_emplacement_fournisseur = fields.Integer(string="Emplacement", help="Emplacement palette fournisseur", readonly=True)
    is_poids_net_colis         = fields.Float(string='Poids net colis (Kg)', digits='Stock Weight', readonly=True)
    is_ecart_demande_fait      = fields.Float('Ecart', digits=(14,4), compute="_compute_is_ecart_demande_fait", help="Ecart entre 'Demande' et 'Fait'")
    is_bio_id                  = fields.Many2one('is.bio', 'BIO', copy=False)


    @api.depends('product_uom_qty','quantity_done')
    def _compute_is_ecart_demande_fait(self):
        for obj in self:
            ecart = round((obj.product_uom_qty or 0.0) - (obj.quantity_done or 0.0),4)
            obj.is_ecart_demande_fait = ecart


    @api.model
    def create(self, vals):
        """Lors de la création d'un mouvement, recopie is_bio_id depuis l'article"""
        res = super(StockMove, self).create(vals)
        for move in res:
            if move.product_id and move.product_id.is_bio_id:
                move.is_bio_id = move.product_id.is_bio_id.id
        return res


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


    def voir_mouvement_action(self):
        for obj in self:
            res= {
                'name': 'Mouvement',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_model': 'stock.move',
                'type': 'ir.actions.act_window',
                'res_id':obj.id,
            }
            return res





class StockScrap(models.Model):
    _inherit = "stock.scrap"

    @api.depends('product_id','lot_id','scrap_qty')
    def _compute_is_dernier_prix_achat(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            x = 0
            montant = 0
            SQL="""
                SELECT get_prix_achat(product_id,lot_id)
                FROM stock_scrap
                WHERE id=%s
            """
            cr.execute(SQL,[obj.id])
            for row in cr.fetchall():
                x=row[0] or 0
                montant = obj.scrap_qty * x
            obj.is_dernier_prix_achat = x
            obj.is_montant_rebut      = montant
  

    is_dernier_prix_achat = fields.Float(string="Dernier prix d'achat", compute='_compute_is_dernier_prix_achat', readonly=True, store=False)
    is_montant_rebut      = fields.Float(string="Montant des rebuts"  , compute='_compute_is_dernier_prix_achat', readonly=True, store=False)



