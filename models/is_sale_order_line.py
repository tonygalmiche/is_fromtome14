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
    product_uom_qty         = fields.Float('Qt cde'            , digits=(14,3))
    qty_delivered           = fields.Float('Qt livrée'         , digits=(14,3))
    qty_invoiced            = fields.Float('Qt facturée'       , digits=(14,3))
    price_unit              = fields.Float('Prix unitaire'       , digits=(14,4))
    discount                = fields.Float('Remise'       , digits=(14,2))
    price_subtotal          = fields.Float('Montant'       , digits=(14,2))
    order_id                = fields.Many2one('sale.order', 'Commande')
    order_line_id           = fields.Many2one('sale.order.line', 'Ligne de commande')
    is_purchase_line_id     = fields.Many2one('purchase.order.line', 'Ligne cde fournisseur')
    purchase_order_id       = fields.Many2one('purchase.order', 'Cde fournisseur')
    state                   = fields.Selection([
            ('draft', 'Brouillon'),
            ('sent', 'Envoyé'),
            ('sale', 'Confirmé'),
            ('done', 'Bloqué'),
            ('cancel', 'Annulé'),
        ], 'Etat de la commande')

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
                    so.state
                from sale_order so    inner join sale_order_line     sol on so.id=sol.order_id
                                      inner join product_product     pp on sol.product_id=pp.id
                                      inner join product_template    pt on pp.product_tmpl_id=pt.id
                                      inner join res_partner         rp on so.partner_id=rp.id
                                      left join purchase_order_line  pol on sol.is_purchase_line_id=pol.id
                                      left join purchase_order       po on pol.order_id=po.id
            )
        """)
