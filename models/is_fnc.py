# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class IsFNC(models.Model):
    _name = 'is.fnc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Fiche de non-conformité Client / Fournisseur"
    _order = 'name desc'

    name              = fields.Char(u"N°FNC", readonly=True)
    company_id        = fields.Many2one('res.company', 'Société'    , required=True, default=lambda self: self.env.user.company_id.id, readonly=True)
    emetteur_id       = fields.Many2one('res.users'   , 'Émetteur'  , required=True, default=lambda self: self.env.user.id, readonly=True)
    date_creation     = fields.Date("Date de création"              , required=True, default=lambda *a: fields.Date.today())
    move_line_id      = fields.Many2one('stock.move.line', 'Ligne de mouvement')
    partner_id        = fields.Many2one('res.partner', 'Partenaire', required=True, help="Client ou fournisseur")
    picking_id        = fields.Many2one('stock.picking', 'Livraison/Réception', required=True)
    product_id        = fields.Many2one('product.product', 'Produit', required=True)
    lot_id            = fields.Many2one('stock.production.lot', 'N° de lot')
    dlc_ddm           = fields.Date('DLC/DDM')
    status_move       = fields.Selection(string='Statut', selection=[('receptionne', 'Réceptionné'),('manquant', 'Manquant'), ('abime', 'Abimé'), ('autre', 'Autre')], required=True)
    description       = fields.Text('Description de la non-conformité')
    cause             = fields.Text('Causes')
    action_immediate  = fields.Text('Action immédiate')
    decision          = fields.Text('Décision')
    analyse           = fields.Text('Analyse des causes')
    action_corrective = fields.Text('Action corrective proposée')
    efficacite_action_corrective = fields.Text("Efficacité de l'action corrective")
    date_cloture      = fields.Date("Date cloture")
    state             = fields.Selection([
            ('en_cours', 'En cours'),
            ('solde'   , 'Soldé'),
        ], 'État', default="en_cours")


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.fnc')
        res = super(IsFNC, self).create(vals)
        return res


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.depends('state')
    def _compute_is_creer_fnc_vsb(self):
        for obj in self:
            vsb = True
            fncs=self.env['is.fnc'].search([('move_line_id', '=', obj.id)])
            if len(fncs)>0:
                vsb=False
            obj.is_creer_fnc_vsb=vsb

    is_creer_fnc_vsb = fields.Boolean(string='Créer FNC visibility', compute='_compute_is_creer_fnc_vsb', readonly=True, store=False)


    def creer_fnc_action(self):
        for obj in self:
            fncs=self.env['is.fnc'].search([('move_line_id', '=', obj.id)])
            fnc_id=False
            for fnc in fncs:
                fnc_id=fnc.id

            if not fnc_id:
                vals={
                    'move_line_id': obj.id,
                    'partner_id'  : obj.move_id.picking_id.partner_id.id,
                    'picking_id'  : obj.move_id.picking_id.id,
                    'product_id'  : obj.move_id.product_id.id,
                    'lot_id'      : obj.lot_id.id,
                    'dlc_ddm'     : obj.is_dlc_ddm,
                    'status_move' : obj.status_move,
                }
                fnc=self.env['is.fnc'].create(vals)
                fnc_id = fnc.id
            res= {
                'name': 'FNC',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_model': 'is.fnc',
                'type': 'ir.actions.act_window',
                'res_id':fnc_id,
            }
            return res


    def acces_fnc_action(self):
        for obj in self:
            fncs=self.env['is.fnc'].search([('move_line_id', '=', obj.id)])
            fnc_id=False
            for fnc in fncs:
                fnc_id=fnc.id
            if fnc_id:
                res= {
                    'name': 'FNC',
                    'view_mode': 'form,tree',
                    'view_type': 'form',
                    'res_model': 'is.fnc',
                    'type': 'ir.actions.act_window',
                    'res_id':fnc_id,
                }
                return res

