# -*- coding: utf-8 -*-
from odoo import api, fields, models, _   # type: ignore
from odoo.exceptions import Warning       # type: ignore
import codecs
import unicodedata
import base64
from datetime import datetime, date, timedelta
from math import *
import pytz
import logging
from .product import _COLISAGE

_logger = logging.getLogger(__name__)


class is_calcul_des_besoins_ligne(models.Model):
    _name = 'is.calcul.des.besoins.ligne'
    _description = "Lignes du calcul des besoins"
    _order='sequence,id'

    calcul_besoins_id   = fields.Many2one('is.calcul.des.besoins', 'Calcul des besoins', required=True, ondelete='cascade')
    sequence            = fields.Integer("Ord")
    product_id          = fields.Many2one('product.product', 'Article')
    fournisseur_id      = fields.Many2one('res.partner', 'Fournisseur')
    uom_id              = fields.Many2one('uom.uom', "Unité article")
    nb_pieces_par_colis = fields.Integer(string='PCB')
    poids_net_colis     = fields.Float(string='Poids net colis (Kg)', digits='Stock Weight')
    colisage            = fields.Selection(_COLISAGE, string='Colisage', help="Colisage de l'article (fiche article) utilisé pour arrondir la Qt à commander au multiple supérieur")
    unite               = fields.Char("Unité calcul")
    sale_qty            = fields.Float("Qt cde client" , digits=(14,4))
    purchase_qty        = fields.Float("Qt en cde", digits=(14,4))
    product_qty         = fields.Float("Qt à cde"      , digits=(14,4), help="Sur commande : Qt cde client - Stock + Stock mini - Qt en cde\nSur historique : Moyenne 8 semaines + Colis S-1 (new) + Stock mini - Stock")
    stock               = fields.Float("Stock"         , digits=(14,2))
    #stock_lc            = fields.Float("Stock LC"      , digits=(14,2))
    stock_mini          = fields.Float("Stock mini"    , digits=(14,2))
    colis_s1            = fields.Float("Colis S-1", digits=(14,2), help="Nombre de colis vendus la semaine dernière (S-1)")
    colis_s2            = fields.Float("Colis S-2", digits=(14,2), help="Nombre de colis vendus il y a 2 semaines (S-2)")
    colis_s3            = fields.Float("Colis S-3", digits=(14,2), help="Nombre de colis vendus il y a 3 semaines (S-3)")
    colis_s4            = fields.Float("Colis S-4", digits=(14,2), help="Nombre de colis vendus il y a 4 semaines (S-4)")
    colis_s1_n1         = fields.Float("Colis S-1 (N-1)", digits=(14,2), help="Nombre de colis vendus l'année dernière, sur la même semaine calendaire que S-1")
    colis_s2_n1         = fields.Float("Colis S-2 (N-1)", digits=(14,2), help="Nombre de colis vendus l'année dernière, sur la même semaine calendaire que S-2")
    colis_s3_n1         = fields.Float("Colis S-3 (N-1)", digits=(14,2), help="Nombre de colis vendus l'année dernière, sur la même semaine calendaire que S-3")
    colis_s4_n1         = fields.Float("Colis S-4 (N-1)", digits=(14,2), help="Nombre de colis vendus l'année dernière, sur la même semaine calendaire que S-4")
    moyenne_8_semaines  = fields.Float("Moy 8S", digits=(14,2), help="Moyenne des colis vendus sur les 4 dernières semaines et sur les 4 mêmes semaines de l'année dernière (N-1)")
    colis_s1_nouveau_client = fields.Float("Colis S-1 (new)", digits=(14,2), help="Nombre de colis vendus en S-1 aux clients dont la toute première commande date de la semaine S-1 (nouveaux clients)")
    nb_col              = fields.Integer("Nb col", help="Nombre de colonnes (parmi les 8 semaines et Colis S-1 (new)) contenant une quantité différente de 0")
    order_line_id       = fields.Many2one('purchase.order.line', 'Ligne commande fournisseur', index=True)
    sale_line_ids       = fields.Many2many('sale.order.line', string='Lignes commande client')
    purchase_line_ids   = fields.Many2many('purchase.order.line', string='Lignes commande fournisseur')

    def action_view_created_purchase_line(self):
        self.ensure_one()
        return {
            'name': 'Ligne commande fournisseur créée',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order.line',
            'view_mode': 'form',
            'res_id': self.order_line_id.id,
        }

    def action_view_created_purchase_order(self):
        self.ensure_one()
        return {
            'name': 'Commande fournisseur créée',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': self.order_line_id.order_id.id,
        }

    def action_view_sale_lines(self):
        self.ensure_one()
        return {
            'name': 'Lignes de commande client',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.line',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.sale_line_ids.ids)],
        }

    def action_view_purchase_lines(self):
        self.ensure_one()
        return {
            'name': 'Lignes de commande fournisseur',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order.line',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.purchase_line_ids.ids)],
        }


class is_calcul_des_besoins(models.Model):
    _name = 'is.calcul.des.besoins'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Calcul des besoins"
    _order='name desc'

    name               = fields.Char("N°", readonly=True)
    type_calcul        = fields.Selection([('commande', 'Sur commande'), ('historique', 'Sur Historique')], string='Type de calcul', default='commande', required=True, tracking=True)
    enseigne_id        = fields.Many2one('is.enseigne.commerciale', 'Enseigne', required=False, help="Enseigne commerciale", tracking=True)
    warehouse_id       = fields.Many2one(related='enseigne_id.warehouse_id', tracking=True)
    stock_mini         = fields.Boolean("Stock mini", default=True, help=u"Si cette case est cochée, il faut tenir compte du stock mini", tracking=True)
    uniquement_articles_historique = fields.Boolean("Uniquement les articles sur historique", default=True, help="Utilisé uniquement si Type de calcul = 'Sur Historique'.\nSi cette case est cochée, seuls les articles ayant la case 'Calcul des besoins sur historique' cochée sur leur fiche article sont pris en compte dans le calcul.", tracking=True)
    ligne_ids          = fields.One2many('is.calcul.des.besoins.ligne', 'calcul_besoins_id', 'Lignes')
    date_fin           = fields.Date("Date de fin", default=lambda self: fields.Datetime.now()+timedelta(7), help="Date prise en compte:\nCommande client: Date livraison client entête\nCommande fournisseur: Date de réception entête", tracking=True)
    calcul_en_colis    = fields.Boolean("Calcul en colis", default=True, help="Le résultat affiché sera en colis", tracking=True)
    active             = fields.Boolean("Actif", default=True, tracking=True)
    state              = fields.Selection([('draft', 'En cours'), ('done', 'Terminé')], string='État', default='draft', tracking=True)
    is_heure_envoi_id  = fields.Many2one('is.heure.maxi', 'Jour / Heure limite', tracking=True, help="Heure maxi d'envoi de la commande au fournisseur")
    nb_lignes          = fields.Integer("Nombre de lignes", compute='_compute_nb_lignes', store=True)
    nb_sale_orders     = fields.Integer("Nb Cdes Clients", compute='_compute_nb_lignes', store=True)
    nb_purchase_orders = fields.Integer("Nb Cdes Fournisseurs", compute='_compute_nb_lignes', store=True)
    nb_created_purchase_orders = fields.Integer("Nb Cdes Créées", compute='_compute_nb_lignes', store=True)
    total_sale_qty      = fields.Float("Total Qt cde client", compute='_compute_totals', store=True, digits=(14,4))
    total_purchase_qty  = fields.Float("Total Qt déja en cde", compute='_compute_totals', store=True, digits=(14,4))
    total_product_qty   = fields.Float("Total Qt à cde", compute='_compute_totals', store=True, digits=(14,4))
    total_stock         = fields.Float("Total Stock", compute='_compute_totals', store=True, digits=(14,2))
    duree_calcul        = fields.Float("Durée du calcul (s)", readonly=True, copy=False)
    date_fin_calcul     = fields.Datetime("Fin du dernier calcul", readonly=True, copy=False)
    documentation       = fields.Html("Documentation", compute='_compute_documentation', help="Explique, en fonction des options cochées, comment la quantité à commander est calculée")

    @api.depends('ligne_ids')
    def _compute_nb_lignes(self):
        for record in self:
            record.nb_lignes = len(record.ligne_ids)
            record.nb_sale_orders = len(record.ligne_ids.mapped('sale_line_ids.order_id'))
            record.nb_purchase_orders = len(record.ligne_ids.mapped('purchase_line_ids.order_id'))
            record.nb_created_purchase_orders = len(record.ligne_ids.mapped('order_line_id.order_id'))

    @api.depends('ligne_ids.sale_qty', 'ligne_ids.purchase_qty', 'ligne_ids.product_qty', 'ligne_ids.stock')
    def _compute_totals(self):
        for record in self:
            record.total_sale_qty     = sum(line.sale_qty for line in record.ligne_ids)
            record.total_purchase_qty = sum(line.purchase_qty for line in record.ligne_ids)
            record.total_product_qty  = sum(line.product_qty for line in record.ligne_ids)
            record.total_stock        = sum(line.stock for line in record.ligne_ids)

    @api.depends('type_calcul', 'stock_mini', 'calcul_en_colis', 'uniquement_articles_historique', 'enseigne_id.display_name', 'is_heure_envoi_id.display_name', 'date_fin')
    def _compute_documentation(self):
        for record in self:
            unite = "colis" if record.calcul_en_colis else "unité de vente (UdV)"
            lines = ["<ul>"]
            if record.type_calcul == 'historique':
                lines.append("<li>Le calcul est fait <b>sur historique</b> : "
                              "pour chaque article, la Qt à commander = Moyenne 8 semaines + Colis S-1 (nouveaux clients) + Stock mini - Stock.</li>")
                lines.append("<li>La <b>Moyenne 8 semaines</b> est la moyenne des colis vendus sur les 4 dernières semaines "
                              "et sur les 4 mêmes semaines de l'année dernière (N-1).</li>")
                lines.append("<li><b>Colis S-1 (nouveaux clients)</b> correspond aux colis vendus en S-1 aux clients dont "
                              "la toute première commande date de cette même semaine.</li>")
                if record.stock_mini:
                    lines.append("<li>Le <b>Stock mini</b> de l'article est pris en compte dans le calcul.</li>")
                else:
                    lines.append("<li>Le <b>Stock mini</b> n'est <u>pas</u> pris en compte (Qt à commander diminuée d'autant).</li>")
                if record.calcul_en_colis:
                    lines.append("<li>La Qt à commander est arrondie au multiple de <b>Colisage</b> <u>inférieur</u> "
                                  "(champ de la fiche article : Colis entier, 1/2 colis ou 1/4 colis).</li>")
                if record.uniquement_articles_historique:
                    lines.append("<li>Seuls les articles ayant la case <i>« Calcul des besoins sur historique »</i> "
                                  "cochée sur leur fiche article sont pris en compte.</li>")
                else:
                    lines.append("<li>Tous les articles vendables sont pris en compte, sans restriction sur la fiche article.</li>")
            else:
                lines.append("<li>Le calcul est fait <b>sur commande</b> : "
                              "pour chaque article, la Qt à commander = Qt cde client - Stock + Stock mini - Qt en cde.</li>")
                if record.date_fin:
                    lines.append("<li>La <b>Date de fin</b> (%s) détermine les commandes prises en compte : "
                                  "date de livraison client jusqu'à cette date pour les commandes clients, "
                                  "date de réception jusqu'à cette date pour les commandes fournisseurs.</li>"
                                  % record.date_fin.strftime('%d/%m/%Y'))
                else:
                    lines.append("<li>Aucune <b>Date de fin</b> n'est renseignée : ce champ est pourtant requis pour ce type de calcul.</li>")
                if record.stock_mini:
                    lines.append("<li>Le <b>Stock mini</b> de l'article est pris en compte dans le calcul.</li>")
                else:
                    lines.append("<li>Le <b>Stock mini</b> n'est <u>pas</u> pris en compte (Qt à commander diminuée d'autant).</li>")
                if record.is_heure_envoi_id:
                    lines.append("<li>Seules les commandes fournisseurs sont créées pour les fournisseurs ayant "
                                  "le Jour / Heure limite « %s ».</li>" % record.is_heure_envoi_id.display_name)
            lines.append("<li>Le résultat est exprimé en <b>%s</b>.</li>" % unite)
            if record.enseigne_id:
                lines.append("<li>Le calcul est restreint à l'enseigne <b>%s</b>.</li>" % record.enseigne_id.display_name)
            else:
                lines.append("<li>Toutes les enseignes sont prises en compte.</li>")
            lines.append("</ul>")
            record.documentation = "".join(lines)

    def action_view_lines(self):
        self.ensure_one()
        if self.type_calcul == 'historique':
            tree_view = self.env.ref('is_fromtome14.is_calcul_des_besoins_ligne_tree_historique')
        else:
            tree_view = self.env.ref('is_fromtome14.is_calcul_des_besoins_ligne_tree')
        form_view = self.env.ref('is_fromtome14.is_calcul_des_besoins_ligne_form')
        return {
            'name': 'Détail des lignes',
            'type': 'ir.actions.act_window',
            'res_model': 'is.calcul.des.besoins.ligne',
            'view_mode': 'tree,form',
            'views': [(tree_view.id, 'tree'), (form_view.id, 'form')],
            'domain': [('calcul_besoins_id', '=', self.id)],
            'context': {'default_calcul_besoins_id': self.id, 'search_default_product_qty_gt_0': 1},
            'limit': 1000,
        }

    def action_view_sale_orders(self):
        self.ensure_one()
        order_ids = self.ligne_ids.mapped('sale_line_ids.order_id').ids
        return {
            'name': 'Commandes clients',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', order_ids)],
        }

    def action_view_purchase_orders(self):
        self.ensure_one()
        order_ids = self.ligne_ids.mapped('purchase_line_ids.order_id').ids
        return {
            'name': 'Commandes fournisseurs',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', order_ids)],
        }

    def action_view_created_purchase_orders(self):
        self.ensure_one()
        order_ids = self.ligne_ids.mapped('order_line_id.order_id').ids
        return {
            'name': 'Commandes fournisseurs créées',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', order_ids)],
            'views': [
                (self.env.ref('purchase.purchase_order_view_tree').id, 'tree'),
                (self.env.ref('purchase.purchase_order_form').id, 'form'),
            ],
        }

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.calcul.des.besoins')
        res = super(is_calcul_des_besoins, self).create(vals)
        return res


    def calcul_besoins_action(self):
        cr,uid,context,su = self.env.args
        warehouses = self.env['stock.warehouse'].search([])
        for obj in self:
            start_time = fields.Datetime.now()

            # if obj.order_id and obj.order_id.state!='draft':
            #     raise Warning(u"La commande Fromtome associée est déjà validée. Le calcul n'est pas autorisé !")

            obj.ligne_ids.unlink()
            now = date.today()
            filtre=[
                ('sale_ok','=',True),
                #('default_code','in',['0107001','1212017','1212022','1212035','0901019','1501008','1907005','1901010','1217002','1217001','0107002'])
                #('default_code','in',['1301002','1212020'])
            ]
            if obj.type_calcul == 'historique' and obj.uniquement_articles_historique:
                filtre.append(('is_calcul_besoins_historique', '=', True))

            #TODO : Bien penser à mettre une limite haute à la fin des tests
            limit=20000

            products = self.env['product.product'].search(filtre,order='name', limit=limit)
            nb_products = len(products)

            #** Optimisation : Recherche globale des lignes de vente ***********
            t0_sale = datetime.now()
            sale_lines_domain = [
                ('order_id.state', '=', 'sale'),
                '|', ('order_id.is_commande_soldee', '=', False), ('order_id.is_commande_soldee', '=', None),
                ('order_id.is_date_livraison', '>=', '2020-10-01'),
                ('order_id.is_date_livraison', '<=', obj.date_fin),
                ('product_id', 'in', products.ids),
                '|', ('order_id.partner_id.is_enseigne_id', '=', False), 
                ('order_id.partner_id.is_enseigne_id.calcul_des_besoins', '=', True),
            ]
            if obj.enseigne_id:
                sale_lines_domain.append(('order_id.partner_id.is_enseigne_id', '=', obj.enseigne_id.id))
            all_sale_lines = self.env['sale.order.line'].search(sale_lines_domain)
            sale_lines_by_product = {}
            for line in all_sale_lines:
                if line.product_id.id not in sale_lines_by_product:
                    sale_lines_by_product[line.product_id.id] = self.env['sale.order.line']
                sale_lines_by_product[line.product_id.id] |= line
            t1_sale = datetime.now()
            total_sale_duration = (t1_sale - t0_sale).total_seconds()
            #*******************************************************************

            #** Optimisation : Recherche globale des lignes d'achat ************
            t0_purchase = datetime.now()
            purchase_lines_domain = [
                ('order_id.state', 'not in', ('done', 'cancel', 'draft')),
                ('order_id.date_planned', '>=', '2020-10-01'),
                ('order_id.date_planned', '<=', obj.date_fin),
                ('product_id', 'in', products.ids),
                ('order_id.is_commande_soldee', '=', False)
            ]
            all_purchase_lines = self.env['purchase.order.line'].search(purchase_lines_domain)
            purchase_lines_by_product = {}
            for line in all_purchase_lines:
                if line.product_id.id not in purchase_lines_by_product:
                    purchase_lines_by_product[line.product_id.id] = self.env['purchase.order.line']
                purchase_lines_by_product[line.product_id.id] |= line
            t1_purchase = datetime.now()
            total_purchase_duration = (t1_purchase - t0_purchase).total_seconds()
            #*******************************************************************

            #** Optimisation : Recherche globale de l'historique des ventes (type_calcul = historique) ***
            historique_qty_by_product_week = {}
            historique_new_client_qty_by_product = {}
            if obj.type_calcul == 'historique':
                week_bounds = []
                for i in range(4):
                    end = now - timedelta(days=7*i)
                    start = end - timedelta(days=7)
                    week_bounds.append(('s%s' % (i+1), start, end))
                    week_bounds.append(('s%s_n1' % (i+1), start - timedelta(days=364), end - timedelta(days=364)))
                min_date = min(b[1] for b in week_bounds)
                max_date = max(b[2] for b in week_bounds)
                historique_domain = [
                    ('order_id.state', 'in', ('sale', 'done')),
                    ('order_id.is_date_livraison', '>=', str(min_date)),
                    ('order_id.is_date_livraison', '<', str(max_date)),
                    ('product_id', 'in', products.ids),
                ]
                if obj.enseigne_id:
                    historique_domain.append(('order_id.partner_id.is_enseigne_id', '=', obj.enseigne_id.id))
                all_historique_lines = self.env['sale.order.line'].search(historique_domain)
                for line in all_historique_lines:
                    line_date = line.order_id.is_date_livraison
                    if not line_date:
                        continue
                    for key, start, end in week_bounds:
                        if start <= line_date < end:
                            k = (line.product_id.id, key)
                            historique_qty_by_product_week[k] = historique_qty_by_product_week.get(k, 0.0) + line.qty_delivered
                            break

                #** Colis S-1 nouveaux clients : 1ère commande du client tombant en S-1 *
                s1_start, s1_end = next((b[1], b[2]) for b in week_bounds if b[0] == 's1')
                s1_lines_data = []
                s1_partner_ids = set()
                for line in all_historique_lines:
                    line_date = line.order_id.is_date_livraison
                    if line_date and s1_start <= line_date < s1_end:
                        s1_lines_data.append((line.product_id.id, line.order_id.partner_id.id, line.qty_delivered))
                        s1_partner_ids.add(line.order_id.partner_id.id)
                if s1_partner_ids:
                    first_order_groups = self.env['sale.order'].read_group(
                        [('partner_id', 'in', list(s1_partner_ids)), ('state', 'in', ('sale', 'done'))],
                        ['partner_id', 'is_date_livraison:min'],
                        ['partner_id'],
                    )
                    first_order_date_by_partner = {
                        g['partner_id'][0]: g['is_date_livraison']
                        for g in first_order_groups if g['partner_id']
                    }
                    new_client_partner_ids = {
                        partner_id for partner_id, first_date in first_order_date_by_partner.items()
                        if first_date and s1_start <= first_date < s1_end
                    }
                    for product_id, partner_id, qty in s1_lines_data:
                        if partner_id in new_client_partner_ids:
                            historique_new_client_qty_by_product[product_id] = historique_new_client_qty_by_product.get(product_id, 0.0) + qty
                #**************************************************************************
            #*******************************************************************************************

            sequence=1
            total_create_duration = 0
            for i, product in enumerate(products, 1):
                _logger.info("%s/%s - [%s] %s", i, nb_products, product.default_code, product.name)
                if product.default_code:
                    #** Commande client ****************************************
                    sale_lines = sale_lines_by_product.get(product.id, self.env['sale.order.line'])
                    sale_qty = sum(line.product_uom_qty - line.qty_delivered for line in sale_lines)
                    if obj.calcul_en_colis:
                        sale_qty = product.product_tmpl_id.uom2colis(sale_qty)
                    #**********************************************************

                    #** Commande Fournisseur **********************************
                    purchase_lines = purchase_lines_by_product.get(product.id, self.env['purchase.order.line'])
                    purchase_qty = 0
                    for line in purchase_lines:
                        qt = line.product_qty - (line.qty_received or 0)
                        if qt < 0:
                            qt = 0
                        purchase_qty += qt
                    #***********************************************************

                    #Convertir la quantité en UA en US *************************
                    purchase_qty = product.uom_po_id._compute_quantity(purchase_qty, product.uom_id, round=True, rounding_method='UP', raise_if_failure=True)
                    if obj.calcul_en_colis:
                        purchase_qty = product.product_tmpl_id.uom2colis(purchase_qty)
                    #***********************************************************

                    #** stock_mini *********************************************
                    stock_mini=0
                    if obj.stock_mini==True:
                        stock_mini = product.is_stock_mini
                        # if obj.warehouse_id.code=="FT":
                        #     stock_mini = product.is_stock_mini
                        # else:
                        #     stock_mini = product.is_stock_mini_lc
                    if obj.calcul_en_colis:
                        stock_mini = product.product_tmpl_id.uom2colis(stock_mini)
                    #***********************************************************

                    #** Recherche du stock dans l'Entrepôt ********************
                    stock=0
                    #stock_lc=0
                    for warehouse in warehouses:
                        location_id =  warehouse.lot_stock_id.id
                        #stock = 0
                        quants = self.env['stock.quant'].search([('product_id','=',product.id),('location_id','=',location_id)])
                        for quant in quants:
                            stock+=quant.quantity
                        #if warehouse.code=='LC':
                        #    stock_lc = stock
                        #if warehouse.code=='FT':
                        #    stock_ft = stock
                    if obj.calcul_en_colis:
                        stock    = product.product_tmpl_id.uom2colis(stock)
                        #stock_lc = product.product_tmpl_id.uom2colis(stock_lc)
                        #stock_ft = product.product_tmpl_id.uom2colis(stock_ft)
                    #***********************************************************

                    #** Calcul de la quantité à commander **********************
                    product_qty = sale_qty - stock + stock_mini - purchase_qty
                    if product_qty<0:
                        product_qty=0
                    #***********************************************************

                    #** Historique des ventes (type_calcul = historique) *******
                    if obj.type_calcul == 'historique':
                        colis_semaines = {}
                        for key in ('s1', 's2', 's3', 's4', 's1_n1', 's2_n1', 's3_n1', 's4_n1'):
                            qty = historique_qty_by_product_week.get((product.id, key), 0.0)
                            colis_semaines[key] = product.product_tmpl_id.uom2colis(qty)
                        moyenne_8_semaines = sum(colis_semaines.values()) / 8
                        colis_s1_nouveau_client = product.product_tmpl_id.uom2colis(historique_new_client_qty_by_product.get(product.id, 0.0))
                        product_qty = moyenne_8_semaines + colis_s1_nouveau_client + stock_mini - stock
                        if product_qty<0:
                            product_qty=0
                        #** Arrondi de la Qt à commander au colisage supérieur *
                        if obj.calcul_en_colis:
                            product_qty = product.product_tmpl_id.arrondi_colisage(product_qty, arrondir="floor")
                        #********************************************************
                    #***********************************************************




                    t0_create = datetime.now()
                    #** Création des lignes du calcul des besoins **************
                    if sale_qty>0 or product_qty>0:
                        unite="Colis"
                        if obj.calcul_en_colis!=True:
                            unite=product.uom_id.name
                        vals={
                            'calcul_besoins_id'  : obj.id,
                            'sequence'           : sequence,
                            'product_id'         : product.id,
                            'fournisseur_id'     : product.product_tmpl_id.is_fournisseur_id.id,
                            'uom_id'             : product.uom_id.id,
                            'nb_pieces_par_colis': product.is_nb_pieces_par_colis,
                            'poids_net_colis'    : product.is_poids_net_colis,
                            'colisage'           : product.is_colisage,
                            'unite'              : unite,
                            'sale_qty'           : sale_qty,
                            'purchase_qty'       : purchase_qty,
                            'product_qty'        : product_qty,
                            'stock'              : stock,
                            #'stock_lc'           : stock_lc,
                            'stock_mini'         : stock_mini,
                            'sale_line_ids'      : [(6, 0, sale_lines.ids)],
                            'purchase_line_ids'  : [(6, 0, purchase_lines.ids)],
                        }
                        if obj.type_calcul == 'historique':
                            nb_col = sum(1 for v in list(colis_semaines.values()) + [colis_s1_nouveau_client] if v)
                            vals.update({
                                'colis_s1'           : colis_semaines['s1'],
                                'colis_s2'           : colis_semaines['s2'],
                                'colis_s3'           : colis_semaines['s3'],
                                'colis_s4'           : colis_semaines['s4'],
                                'colis_s1_n1'        : colis_semaines['s1_n1'],
                                'colis_s2_n1'        : colis_semaines['s2_n1'],
                                'colis_s3_n1'        : colis_semaines['s3_n1'],
                                'colis_s4_n1'        : colis_semaines['s4_n1'],
                                'moyenne_8_semaines' : moyenne_8_semaines,
                                'colis_s1_nouveau_client' : colis_s1_nouveau_client,
                                'nb_col'             : nb_col,
                            })
                        ligne=self.env['is.calcul.des.besoins.ligne'].create(vals)
                        sequence+=1
                    #***********************************************************
                    t1_create = datetime.now()
                    total_create_duration += (t1_create - t0_create).total_seconds()


            t0_create_po = datetime.now()
            #** Création des commandes fournisseurs ****************************
            company = self.env.user.company_id
            for line in obj.ligne_ids:
                if line.product_qty > 0:
                    suppliers = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', line.product_id.product_tmpl_id.id)])
                    supplierinfo = False
                    for s in suppliers:
                        if now >= s.date_start and now <= s.date_end:
                            supplierinfo = s
                            break
                    
                    if supplierinfo:
                        if supplierinfo.name.active and supplierinfo.name.is_warehouse_id:
                            if supplierinfo.name.is_heure_envoi_id == obj.is_heure_envoi_id or not obj.is_heure_envoi_id:
                                partner_id = supplierinfo.name.id
                                #date_reception = str(obj.date_fin)
                                date_reception = str(date.today()+timedelta(days=2))
                                date_planned = date_reception + ' 08:00:00'
                                filtre = [
                                    ('partner_id', '=', partner_id),
                                    ('state', '=', 'draft'),
                                    ('date_planned', '>=', date_reception + ' 00:00:00'),
                                    ('date_planned', '<=', date_reception + ' 23:59:59'),
                                ]
                                orders = self.env['purchase.order'].search(filtre, limit=1)
                                if orders:
                                    order = orders[0]
                                else:
                                    vals = {
                                        'partner_id': partner_id,
                                        'date_planned': date_planned,
                                        'picking_type_id': supplierinfo.name.is_warehouse_id.in_type_id.id,
                                        'is_adresse_livraison_id': supplierinfo.name.is_enseigne_id.warehouse_id.partner_id.id,
                                    }
                                    order = self.env['purchase.order'].create(vals)
                                    if order:
                                        order.onchange_partner_id()

                                #** Création des lignes ************************
                                if company.is_regroupe_cde == "Oui":
                                    filtre = [
                                        ('order_id', '=', order.id),
                                        ('product_id', '=', line.product_id.id),
                                    ]
                                else:
                                    filtre = [
                                        ('order_id', '=', order.id),
                                        ('product_id', '=', line.product_id.id),
                                    ]
                                order_lines = self.env['purchase.order.line'].search(filtre, limit=1)
                                
                                qty_to_order = line.product_qty

                                if not order_lines:
                                    if order:
                                        vals = {
                                            'order_id': order.id,
                                            'product_id': line.product_id.id,
                                            'name': line.product_id.name,
                                            'product_qty': 0,
                                            'product_uom': line.product_id.uom_po_id.id,
                                            'date_planned': date_planned,
                                            'price_unit': 0,
                                        }
                                        order_line = self.env['purchase.order.line'].create(vals)
                                        order_line.onchange_product_id()
                                        
                                        if obj.calcul_en_colis:
                                            order_line.is_nb_colis = qty_to_order
                                            order_line.onchange_is_nb_colis()
                                        else:
                                            # Conversion uom_id -> uom_po_id
                                            qty_po = line.uom_id._compute_quantity(qty_to_order, line.product_id.uom_po_id)
                                            order_line.product_qty = qty_po
                                            order_line.onchange_product_qty_fromtome()
                                        
                                        order_line._compute_is_nb_pieces_par_colis()
                                else:
                                    order_line = order_lines[0]
                                    if company.is_regroupe_cde == "Oui":
                                        if obj.calcul_en_colis:
                                            order_line.is_nb_colis += qty_to_order
                                            order_line.onchange_is_nb_colis()
                                        else:
                                            qty_po = line.uom_id._compute_quantity(qty_to_order, line.product_id.uom_po_id)
                                            order_line.product_qty += qty_po
                                            order_line.onchange_product_qty_fromtome()
                                
                                if order_line:
                                    line.order_line_id = order_line.id
            #*******************************************************************
            t1_create_po = datetime.now()
            total_create_po_duration = (t1_create_po - t0_create_po).total_seconds()

            end_time = fields.Datetime.now()
            duration = (end_time - start_time).total_seconds()
            obj.write({
                'duree_calcul': duration,
                'date_fin_calcul': end_time,
                'state': 'done',
            })

            # Conversion pour l'affichage
            paris_tz = pytz.timezone('Europe/Paris')
            start_time_paris = pytz.utc.localize(start_time).astimezone(paris_tz)
            end_time_paris = pytz.utc.localize(end_time).astimezone(paris_tz)

            obj.message_post(body=_(
                "Calcul des besoins terminé:<br/>"
                "- Début : %s<br/>"
                "- Fin : %s<br/>"
                "- Durée : %.2f secondes<br/>"
                "- Nombre de lignes : %s<br/>"
                "- Durée Total : %.2f s"
            ) % (
                start_time_paris.strftime('%d/%m/%Y %H:%M:%S'), 
                end_time_paris.strftime('%d/%m/%Y %H:%M:%S'), 
                duration, 
                len(obj.ligne_ids),
                total_sale_duration + total_purchase_duration + total_create_duration + total_create_po_duration
            ))






