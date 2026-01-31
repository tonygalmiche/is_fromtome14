# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools.sql import drop_view_if_exists


class is_sale_order_line(models.Model):
    _name='is.sale.order.line'
    _description='is.sale.order.line'
    _order='id desc'
    _auto = False

    company_id              = fields.Many2one('res.company', 'Société')
    date_order              = fields.Datetime('Date Commande')
    is_date_livraison       = fields.Date('Date Livraison')
    is_commande_soldee      = fields.Boolean('Commande soldée')
    partner_id              = fields.Many2one('res.partner', 'Client')
    product_id              = fields.Many2one('product.product', 'Article')
    barcode                 = fields.Char('Code barre')
    product_uom             = fields.Many2one('uom.uom', 'Unité')
    description             = fields.Char('Description')
    product_uom_qty         = fields.Float('Qt prépa'            , digits=(14,3))
    qty_delivered           = fields.Float('Qt livrée'         , digits=(14,3))
    qty_invoiced            = fields.Float('Qt facturée'       , digits=(14,3))
    price_unit              = fields.Float('Prix unitaire'       , digits=(14,4))
    discount                = fields.Float('Remise'       , digits=(14,2))
    price_subtotal          = fields.Float('Montant'       , digits=(14,2))
    order_id                = fields.Many2one('sale.order', 'Commande')
    order_line_id           = fields.Many2one('sale.order.line', 'Ligne de commande')
    is_purchase_line_id     = fields.Many2one('purchase.order.line', 'Ligne cde fournisseur')
    write_date              = fields.Datetime('Date modification')
    purchase_order_id       = fields.Many2one('purchase.order', 'Cde fournisseur')
    state                   = fields.Selection([
            ('draft', 'Brouillon'),
            ('sent', 'Envoyé'),
            ('sale', 'Confirmé'),
            ('done', 'Bloqué'),
            ('cancel', 'Annulé'),
        ], 'Etat de la commande')
    
    user_id        = fields.Many2one('res.users', 'Vendeur')
    is_enseigne_id = fields.Many2one('is.enseigne.commerciale', 'Enseigne', help="Enseigne commerciale")
    is_poids_net   = fields.Float(string='Poids net', digits='Stock Weight', help="Poids net total (Kg)")


    is_date_reception         = fields.Date(string=u'Date réception')
    is_nb_pieces_par_colis    = fields.Integer(string="PCB", help='Nb Pièces / colis', compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_nb_colis               = fields.Float(string='Nb Colis', digits=(14,2), compute='_compute_is_nb_pieces_par_colis', readonly=True, store=True)
    is_colis_cde              = fields.Float(string='Colis Prépa', digits=(14,2))
    is_colis_cde_origine      = fields.Float(string='Colis Cde'  , digits=(14,2), readonly=True, help="Ce champ permet de mémoriser la valeur du champ 'Colis Prépa' au moment de la validation de la commande")
    is_default_code           = fields.Char(string='Réf Fromtome'   , compute='_compute_ref', readonly=True, store=True)
    is_ref_fournisseur        = fields.Char(string='Réf Fournisseur', compute='_compute_ref', readonly=True, store=True)
    is_qt_cde                 = fields.Float(string='Qt Cde', digits='Product Unit of Measure',readonly=True,help="Ce champ permet de mémoriser la valeur du champ product_uom_qty au moment de la validation de la commande")
    is_ecart_qt_cde_prepa     = fields.Float(string='Qt Prépa - Qt Cde', digits='Product Unit of Measure', compute='_compute_is_ecart_qt_cde_prepa', readonly=True, store=True)
    is_colis_liv              = fields.Float(string='Colis Liv', digits=(14,2))
    is_colis_manquant         = fields.Float(string='Manquant', digits=(14,2), help="Nombre de colis manquants : max(Colis Prépa, Colis Cde) - Colis Liv")






    def init(self):
        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE view is_sale_order_line AS (
                select  
                    sol.id,
                    so.company_id,
                    sol.order_id,
                    so.is_commande_soldee,
                    so.date_order,
                    so.is_date_livraison,
                    so.partner_id, 
                    sol.product_id, 
                    pp.barcode,
                    sol.product_uom,
                    sol.name as description,
                    sol.product_uom_qty,
                    sol.qty_delivered,
                    sol.qty_invoiced ,
                    sol.price_unit,
                    sol.discount,
                    sol.price_subtotal,
                    sol.id                  as order_line_id,
                    sol.is_purchase_line_id,
                    po.id                   as purchase_order_id,
                    so.state,
                    so.user_id,
                    rp.is_enseigne_id,
                    sol.is_poids_net,
                    sol.write_date,
                    sol.is_date_reception,
                    sol.is_nb_pieces_par_colis,
                    sol.is_nb_colis,
                    sol.is_colis_cde,
                    sol.is_colis_cde_origine,
                    sol.is_default_code,
                    sol.is_ref_fournisseur,
                    sol.is_qt_cde,
                    sol.is_ecart_qt_cde_prepa,
                    sol.is_colis_liv,
                    sol.is_colis_manquant
                from sale_order so    inner join sale_order_line     sol on so.id=sol.order_id
                                      inner join product_product     pp on sol.product_id=pp.id
                                      inner join product_template    pt on pp.product_tmpl_id=pt.id
                                      inner join res_partner         rp on so.partner_id=rp.id
                                      left join purchase_order_line  pol on sol.is_purchase_line_id=pol.id
                                      left join purchase_order       po on pol.order_id=po.id
            )
        """)
