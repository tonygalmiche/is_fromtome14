# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime, timedelta, date


_MOVE_TYPE={
    'out_invoice': 'Facture client',
    'out_refund' : 'Avoir client',
    'in_invoice' : 'Facture fournisseur',
    'in_refund'  : 'Avoir fournisseur',
    'rebut'      : 'Rebut',
}


class IsAnalyseFacturationUpdate(models.TransientModel):
    _name = 'is.analyse.facturation.update'
    _description = "Mise à jour analyse de facturation"

    date_debut = fields.Date('Date début', required=True, default=lambda self: fields.Datetime.now()-timedelta(30))
    date_fin   = fields.Date('Date fin'  , required=True, default=lambda self: fields.Datetime.now())

    def action_ok(self):
        filtre=[
            ('invoice_date','>=',self.date_debut),
            ('invoice_date','<=',self.date_fin),
        ]
        self.env['is.analyse.facturation'].search(filtre).unlink()
        filtre=[
            ('invoice_date','>=',self.date_debut),
            ('invoice_date','<=',self.date_fin),
            ('state','=','posted'),
        ]
        invoices = self.env['account.move'].search(filtre)
        for invoice in invoices:
            for line in invoice.invoice_line_ids:
                 if line.price_subtotal>0.0:
                    sens=1
                    if invoice.move_type in ["out_refund","in_invoice"]:
                        sens=-1
                    vals={
                        "invoice_id"    : invoice.id,
                        "invoice_date"  : invoice.invoice_date,
                        "partner_id"    : invoice.partner_id.id,
                        "user_id"       : invoice.partner_id.user_id.id,
                        "enseigne"      : invoice.partner_id.is_enseigne_id.name.name,
                        "product_id"    : line.product_id.id,
                        "product_uom_id": line.product_uom_id.id,
                        "libelle"       : line.name,
                        "quantity"      : line.quantity,
                        "nb_colis"      : line.is_nb_colis,
                        "poids_net"     : line.is_poids_net,
                        "price_unit"    : line.price_unit,
                        "price_subtotal": line.price_subtotal*sens,
                        "move_type"     : _MOVE_TYPE[invoice.move_type],
                    }
                    self.env['is.analyse.facturation'].create(vals)

        filtre=[
            ('date_done','>=',self.date_debut),
            ('date_done','<',self.date_fin+timedelta(1)),
            ('state','=','done'),
        ]
        scraps = self.env['stock.scrap'].search(filtre)
        for scrap in scraps:
            price_unit = 0
            partner_id=enseigne_id=user_id=False
            for purchase in scrap.lot_id.purchase_order_ids:
                partner_id  = purchase.partner_id.id
                enseigne    = purchase.partner_id.is_enseigne_id.name.name
                user_id     = purchase.partner_id.user_id.id
                for line in purchase.order_line:
                    if line.product_id == scrap.product_id:
                        price_unit=line.price_unit
            price_subtotal = -price_unit * scrap.scrap_qty
            vals={
                "scrap_id"      : scrap.id,
                "invoice_date"  : scrap.date_done,
                "partner_id"    : partner_id,
                "user_id"       : user_id,
                "enseigne"      : enseigne,
                "product_id"    : scrap.product_id.id,
                "product_uom_id": scrap.product_id.uom_id.id,
                "libelle"       : scrap.name+" / "+(scrap.origin or ''),
                "quantity"      : scrap.scrap_qty,
                "price_unit"    : price_unit,
                "price_subtotal": price_subtotal,
                "move_type"     : "Rebut",
            }
            self.env['is.analyse.facturation'].create(vals)

        res= {
            'name': 'Analyse facturation',
            'view_mode': 'tree,form,pivot,graph',
            'res_model': 'is.analyse.facturation',
            'type': 'ir.actions.act_window',
        }
        return res


class IsAnalyseFacturation(models.Model):
    _name = 'is.analyse.facturation'
    _description = "Analyse facturation"
    _order = 'invoice_date desc,move_type'


    invoice_date      = fields.Date('Date facture / Rebut', required=True)
    invoice_id        = fields.Many2one('account.move', 'Facture')
    scrap_id          = fields.Many2one('stock.scrap', 'Rebut')
    partner_id        = fields.Many2one('res.partner', 'Partenaire')
    user_id           = fields.Many2one('res.users', 'Vendeur')
    #enseigne_id       = fields.Many2one('is.enseigne.commerciale', 'Enseigne')
    enseigne          = fields.Char('Enseigne')
    product_id        = fields.Many2one('product.product', 'Article')
    product_uom_id    = fields.Many2one('uom.uom', 'Unité')
    libelle           = fields.Text('Libellé')
    quantity          = fields.Float("Quantité", digits='Product Unit of Measure')
    poids_net         = fields.Float(string='Poids net', digits=(14,3))
    nb_colis          = fields.Float(string='Nb colis' , digits=(14,1))
    price_unit        = fields.Float("Prix"    , digits='Product Price')
    price_subtotal    = fields.Float("Montant HT")
    move_type         = fields.Selection([
            ('Facture client'     , 'Facture client'),
            ('Avoir client'       , 'Avoir client'),
            ('Facture fournisseur', 'Facture fournisseur'),
            ('Avoir fournisseur'  , 'Avoir fournisseur'),
            ('Rebut'              , 'Rebut'),
        ], 'Type')

