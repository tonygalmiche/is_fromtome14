# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import date


class IsFNC(models.Model):
    _name = 'is.fnc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Fiche de non-conformité Client / Fournisseur"
    _order = 'name desc'

    name    = fields.Char("N°FNC", readonly=True)
    origine = fields.Selection([
            ('client'      , 'Client'),
            ('fournisseur' , 'Fournisseur'),
            ('transporteur', 'Transporteur'),
            ('interne'     , 'Interne'),
        ], 'Origine FNC', required=True, default="fournisseur")
    
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

    action_immediate     = fields.Text('Action curative')
    action_curative_date = fields.Date("Date action curative", copy=False)
    action_curative_responsable_id = fields.Many2one('res.users', 'Responsable action curative', copy=False)
    action_curative_statut = fields.Selection([
            ('en_cours' , 'En cours'),
            ('en_retard', 'En retard'),
            ('fait'     , 'Fait'),
        ], 'Statut action curative', default="en_cours", copy=False)
    decision          = fields.Text('Décision', copy=False)
    analyse           = fields.Text('Analyse des causes', copy=False)

    action_corrective = fields.Text('Action corrective proposée', copy=False)
    action_corrective_responsable_id = fields.Many2one('res.users', 'Responsable action corrective')
    action_corrective_date_prevue    = fields.Date("Date prévue action corrective", copy=False)
    action_corrective_date_effective = fields.Date("Date éffective action corrective", copy=False)
    action_corrective_statut = fields.Selection([
            ('en_cours' , 'En cours'),
            ('en_retard', 'En retard'),
            ('fait'     , 'Fait'),
        ], 'Statut action corrective', default="en_cours", copy=False)

    efficacite_action_corrective     = fields.Text("Efficacité de l'action corrective", copy=False)
    efficacite_action_date           = fields.Date("Date de vérification", copy=False)
    efficacite_action_responsable_id = fields.Many2one('res.users', 'Responsable vérification')
    efficacite_action_date_validee   = fields.Date("Date efficacité validée", copy=False)

    date_cloture      = fields.Date("Date cloture", copy=False)
    state             = fields.Selection([
            ('en_cours', 'En cours'),
            ('solde'   , 'Soldé'),
        ], 'État', default="en_cours", copy=False)


    fnc_origine_id    = fields.Many2one('is.fnc', "FNC client d'origine", copy=False)
    fnc_associees_ids = fields.One2many('is.fnc', 'fnc_origine_id', 'FNC associées', copy=False)


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.fnc')
        res = super(IsFNC, self).create(vals)
        return res


    def creer_fnc_fournisseur_action(self):
        for obj in self:
            copy = obj.copy()
            copy.origine = 'fournisseur'
            copy.fnc_origine_id = obj.id
            filtre=[
                ('date','<=',obj.move_line_id.date),
                ('lot_id','=',obj.lot_id.id),
            ]
            lines = self.env['stock.move.line'].search(filtre, order="date desc")
            for line in lines:
                if line.move_id.picking_type_id.id==1:
                    copy.move_line_id = line.id
                    copy.picking_id = line.move_id.picking_id.id
                    copy.partner_id = line.move_id.picking_id.partner_id.id
                    break
            return copy.voir_fnc_action()


    def voir_fnc_action(self):
        for obj in self:
            return {
                "name": obj.name,
                "view_mode": "form,tree",
                "res_model": "is.fnc",
                "res_id"   : obj.id,
                "type": "ir.actions.act_window",
            }


    @api.model
    def fnc_update_ir_cron(self):
        fncs=self.env['is.fnc'].search([])
        for fnc in fncs:
            fnc.fnc_update_action()
        return True
    

    @api.onchange('action_corrective_date_effective', 'action_corrective_date_prevue')
    def fnc_update_action(self):
        for obj in self:
            statut = obj.get_statut()
            if statut:
                if obj.action_corrective_statut != statut:
                    obj.action_corrective_statut = statut


    def get_statut(self):
        statut = False
        for obj in self:
            if obj.action_corrective_date_effective:
                statut =  'fait'
            if obj.action_corrective_date_prevue and not obj.action_corrective_date_effective:
                if obj.action_corrective_date_prevue < date.today():
                    statut = 'en_retard'
                else:
                    statut = 'en_cours'
        return statut


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

