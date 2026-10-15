# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, date, time


class IsCommandeTransporteur(models.Model):
    _name = 'is.commande.transporteur'
    _description = "Commandes transporteurs"
    _order = 'date_debut desc'
    _rec_name = 'date_debut'


    def _default_date_debut(self):
        "Lundi de la semaine en cours"
        today = date.today()
        return today - timedelta(days=today.weekday())


    def _default_date_fin(self):
        "Vendredi de la semaine en cours"
        today = date.today()
        return today - timedelta(days=today.weekday()) + timedelta(days=4)


    date_debut  = fields.Date("Date début", required=True, default=lambda self: self._default_date_debut(), help="Date de livraison client de début des BL à transporter")
    date_fin    = fields.Date("Date fin"  , required=True, default=lambda self: self._default_date_fin()  , help="Date de livraison client de fin des BL à transporter")
    order_ids   = fields.One2many('purchase.order', 'is_commande_transporteur_id', 'Commandes transporteurs', readonly=True)
    commentaire = fields.Text("Commentaire")
    alerte      = fields.Text("Anomalies", compute='_compute_alerte')


    def name_get(self):
        res=[]
        for obj in self:
            name = "Du %s au %s"%(obj.date_debut.strftime('%d/%m/%Y'), obj.date_fin.strftime('%d/%m/%Y'))
            res.append((obj.id, name))
        return res


    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for obj in self:
            if obj.date_fin < obj.date_debut:
                raise ValidationError("La date de fin doit être supérieure ou égale à la date de début")
            filtre=[
                ('id'        , '!=', obj.id),
                ('date_debut', '<=', obj.date_fin),
                ('date_fin'  , '>=', obj.date_debut),
            ]
            autres = self.search(filtre, limit=1)
            if autres:
                raise ValidationError("La période chevauche celle de la fiche '%s'"%(autres.display_name))


    def _compute_alerte(self):
        for obj in self:
            alertes=[]
            for order in obj.order_ids:
                if order.state=='cancel':
                    continue
                for line in order.order_line:
                    picking = line.is_picking_id
                    if picking and picking.state=='done' and picking.get_nb_palettes()==0:
                        alertes.append("%s : BL %s (%s) validé sans palette"%(order.name, picking.name, picking.partner_id.display_name))
            obj.alerte = "\n".join(alertes) or False


    def generer_actualiser_action(self):
        for obj in self:
            obj._generer_actualiser()


    def voir_commandes_action(self):
        self.ensure_one()
        return {
            'name': 'Commandes transporteurs',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('is_commande_transporteur_id', '=', self.id)],
        }


    def voir_livraisons_action(self):
        self.ensure_one()
        pickings = self.order_ids.filtered(lambda o: o.state!='cancel').mapped('is_livraison_ids')
        return {
            'name': 'Livraisons transportées',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', pickings.ids)],
        }


    def _generer_actualiser(self):
        "Crée ou met à jour une commande par transporteur, avec une ligne par BL"
        self.ensure_one()
        product = self._get_product_transport()
        pickings = self._get_pickings()

        #** Lignes existantes des BL, sur toutes les commandes transporteurs non annulées
        filtre=[
            ('is_picking_id'  , 'in', pickings.ids),
            ('order_id.state' , '!=', 'cancel'),
        ]
        lines = self.env['purchase.order.line'].search(filtre)
        line_par_picking = {line.is_picking_id: line for line in lines}

        #** Retrait des lignes dont le BL n'est plus à transporter dans la période
        orders = self.order_ids.filtered(lambda o: o.state!='cancel')
        for line in orders.mapped('order_line'):
            if line.is_picking_id and line.is_picking_id not in pickings:
                self._retirer_ligne(line)

        #** Commandes de la fiche par transporteur
        order_par_partner={}
        for order in orders:
            if order.partner_id not in order_par_partner:
                order_par_partner[order.partner_id] = order

        #** Ajout ou mise à jour d'une ligne par BL
        for picking in pickings:
            partner = picking.is_transporteur_id.partner_id
            order = order_par_partner.get(partner)
            line  = line_par_picking.get(picking)
            if line and line.order_id!=order:
                #** Le BL a changé de tournée ou est sur une autre fiche => déplacé sur la bonne commande
                self._retirer_ligne(line)
                line = False
            if not order:
                order = self._creer_commande(partner)
                order_par_partner[partner] = order
            vals = self._get_vals_ligne(picking, line)
            if line:
                vals = {k: v for k, v in vals.items() if line[k]!=v}
                if vals:
                    line.write(vals)
            else:
                vals.update({
                    'order_id'     : order.id,
                    'product_id'   : product.id,
                    'product_uom'  : product.uom_po_id.id,
                    'price_unit'   : 0,
                    'date_planned' : datetime.combine(picking.is_date_livraison, time(12)),
                    'is_picking_id': picking.id,
                })
                line = self.env['purchase.order.line'].create(vals)
                line._compute_tax_id()

        #** Annulation des commandes en brouillon sans ligne et date prévue recalée sur la date de début
        date_planned = datetime.combine(self.date_debut, time(12))
        for order in self.order_ids:
            if order.state in ('draft', 'sent'):
                if not order.order_line:
                    order.button_cancel()
                elif order.date_planned!=date_planned:
                    order.date_planned = date_planned


    def _get_product_transport(self):
        product = self.env['product.product'].search([('default_code', '=', '0000000')], limit=1)
        if not product:
            raise UserError("Article de transport [0000000] non trouvé")
        return product


    def _get_pickings(self):
        "BL à transporter dont la date de livraison client est dans la période"
        self.ensure_one()
        filtre=[
            ('picking_type_code'             , '=' , 'outgoing'),
            ('state'                         , '!=', 'cancel'),
            ('sale_id'                       , '!=', False),
            ('is_transporteur_id.partner_id' , '!=', False),
            ('is_date_livraison'             , '>=', self.date_debut),
            ('is_date_livraison'             , '<=', self.date_fin),
        ]
        return self.env['stock.picking'].search(filtre, order='is_date_livraison, name')


    def _creer_commande(self, partner):
        "Commande en brouillon. La date d'enlèvement est saisie à la main"
        vals={
            'partner_id'                 : partner.id,
            'date_planned'               : datetime.combine(self.date_debut, time(12)),
            'is_commande_transporteur_id': self.id,
        }
        order = self.env['purchase.order'].create(vals)
        order.onchange_partner_id()
        order.onchange_partner_id_is_adresse_livraison_id()
        order.onchange_partner_id_warehouse()
        return order


    def _get_vals_ligne(self, picking, line=False):
        "Description et nombre de palettes de la ligne du BL"
        if picking.state=='done':
            colis = picking.is_nb_colis
            poids = picking.is_poids_net
        else:
            colis = picking.is_nb_colis_cde_total
            poids = picking.is_poids_net_cde_total
        partner = picking.partner_id
        ville   = ("%s %s"%(partner.zip or '', partner.city or '')).strip()
        name = " - ".join(x for x in [picking.name, picking.sale_id.name, partner.display_name, ville] if x)
        name += " - %.1f colis - %.1f kg"%(colis, poids)
        vals={'name': name}

        #** Palettes du BL si validé ou si saisies, sinon quantité saisie à la main conservée
        nb_palettes = picking.get_nb_palettes()
        if picking.state=='done' or nb_palettes>0:
            vals['product_qty'] = nb_palettes
        elif not line:
            vals['product_qty'] = 0
        return vals


    def _retirer_ligne(self, line):
        "Supprime la ligne si possible, sinon la met à 0 et retire le lien avec le BL"
        if line.order_id.state in ('draft', 'sent', 'to approve') and not line.invoice_lines:
            line.unlink()
        else:
            line.write({
                'product_qty'  : 0,
                'is_picking_id': False,
                'name'         : "Retiré : %s"%line.name,
            })
