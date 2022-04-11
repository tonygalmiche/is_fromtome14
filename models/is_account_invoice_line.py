# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools.sql import drop_view_if_exists


class is_account_invoice_line(models.Model):
    _name='is.account.invoice.line'
    _description='is.account.invoice.line'
    _order='id desc'
    _auto = False

    company_id              = fields.Many2one('res.company', 'Société')
    line_id                 = fields.Many2one('account.move.line', 'Ligne de facture')
    invoice_id              = fields.Many2one('account.move', 'Facture')
    number                  = fields.Char("N°Facture")
    date_invoice            = fields.Date("Date facture")
    partner_id              = fields.Many2one('res.partner', 'Partenaire')
    enseigne_id             = fields.Many2one('is.enseigne.commerciale', 'Enseigne')
    product_id              = fields.Many2one('product.product', 'Article')
    description             = fields.Char('Description')
    quantity                = fields.Float('Quantité'              , digits=(14,4))
    nb_pieces_par_colis     = fields.Integer(string='PCB')
    nb_colis                = fields.Float(string='Nb Colis', digits=(14,2))
    poids_net               = fields.Float(string='Poids net', digits=(14,4))
    price_unit              = fields.Float('Prix unitaire'         , digits=(14,4))
    discount                = fields.Float('Remise'                , digits=(14,2))
    price_subtotal          = fields.Float('Montant HT'            , digits=(14,2))
    invoice_type             = fields.Selection([
        ('in_invoice' , 'Facture fournisseur'),
        ('in_refound' , 'Avoir fournisseur'),
        ('out_invoice', 'Facture client'),
        ('out_refund' , 'Avoir client'),
    ], 'Type de facture')


    def init(self):
        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE FUNCTION fsens(t text) RETURNS integer AS $$
            BEGIN
                RETURN (
                    SELECT
                    CASE
                    WHEN t::text = ANY (ARRAY['out_refund'::character varying::text, 'in_refund'::character varying::text])
                        THEN -1::int
                        ELSE 1::int
                    END
                );
            END;
            $$ LANGUAGE plpgsql;

            CREATE OR REPLACE view is_account_invoice_line AS (
                select 
                    ail.id          id,
                    ail.id          line_id,
                    ail.name        description,
                    ai.company_id,
                    ai.id           invoice_id,
                    ai.name         number,
                    ai.move_type         invoice_type,
                    ai.invoice_date date_invoice,
                    ai.partner_id,
                    rp.is_enseigne_id enseigne_id,
                    ail.product_id,
                    fsens(ai.move_type)*ail.quantity quantity,
                    ail.is_nb_pieces_par_colis nb_pieces_par_colis,
                    fsens(ai.move_type)*ail.is_nb_colis            nb_colis,
                    fsens(ai.move_type)*ail.is_poids_net           poids_net,
                    ail.price_unit,
                    ail.discount,
                    fsens(ai.move_type)*price_subtotal price_subtotal,
                    ai.state
                from account_move ai inner join account_move_line ail on ai.id=ail.move_id
                                        inner join res_partner              rp on ai.partner_id=rp.id
                                        inner join product_product          pp on ail.product_id=pp.id
                                        inner join product_template         pt on pp.product_tmpl_id=pt.id
                where ai.state='posted'
            )
        """)