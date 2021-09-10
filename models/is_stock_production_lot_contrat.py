# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools.sql import drop_view_if_exists
from datetime import timedelta


class is_stock_production_lot_contrat(models.Model):
    _name='is.stock.production.lot.contrat'
    _description='is.stock.production.lot.contrat'
    _order='partner_id,product_id,lot_id'
    _auto = False


    # @api.depends('product_id')
    # def _compute_date_limite(self):
    #     for obj in self:
    #         date_limite=False
    #         if obj.use_date:
    #             date_limite=obj.use_date
    #         if obj.life_date:
    #             date_limite=obj.life_date
    #         if date_limite:
    #             date_limite-=timedelta(days=obj.contrat_id.name)
    #         obj.date_limite=date_limite


    company_id      = fields.Many2one('res.company', 'Société')
    product_id      = fields.Many2one('product.product', "Article")
    product_tmpl_id = fields.Many2one('product.template', "Modèle d'article")
    lot_id          = fields.Many2one('stock.production.lot', 'Lot')
    product_uom_id  = fields.Many2one('uom.uom', 'Unité')
    #life_date       = fields.Datetime("Date limite de consommation")
    #use_date        = fields.Datetime("Date limite d'utilisation optimale")
    partner_id      = fields.Many2one('res.partner', 'Client')
    contrat_id      = fields.Many2one('contrat.date.client', 'Contrat date')
    #date_limite     = fields.Datetime("Date limite contrat", compute=_compute_date_limite, store=False)
    product_qty     = fields.Float('Quantité', related='lot_id.product_qty')


    def init(self):
        drop_view_if_exists(self.env.cr, self._table)

        self.env.cr.execute("""
            CREATE OR REPLACE view is_stock_production_lot_contrat AS (

                select 
                    row_number() over(order by l.id ) as id,
                    pt.company_id,
                    l.product_id,
                    pp.product_tmpl_id,
                    l.id as lot_id,
                    l.product_uom_id,
                    -- l.life_date,
                    -- l.use_date,
                    c.partner_id,
                    c.id as contrat_id
                from stock_production_lot l join product_product pp on l.product_id=pp.id 
                                            join product_template pt on pp.product_tmpl_id=pt.id
                                            join contrat_date_client c on c.product_id=pp.product_tmpl_id
                where l.active='t'
            )
        """)
