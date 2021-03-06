# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools.sql import drop_view_if_exists
from datetime import timedelta


_STATE_PICKING=[
    ('draft'    , 'Bouillon'),
    ('waiting'  , 'En attente'),
    ('confirmed', 'En attente'),
    ('assigned' , 'Prêt'),
    ('done'     , 'Fait'),
    ('cancel'   , 'Annulé'),
]


class is_stock_move_line(models.Model):
    _name='is.stock.move.line'
    _description='is.stock.move.line'
    _order='product_id'
    _auto = False


    @api.depends('status_move')
    def _compute_creer_fnc_vsb(self):
        for obj in self:
            vsb = True
            fncs=self.env['is.fnc'].search([('move_line_id', '=', obj.move_line_id.id)])
            if len(fncs)>0:
                vsb=False
            obj.creer_fnc_vsb=vsb


    company_id      = fields.Many2one('res.company', 'Société')
    picking_id      = fields.Many2one('stock.picking', 'Picking')
    date_done       = fields.Date('Date effective', index=True)
    picking_type_id = fields.Many2one('stock.picking.type', 'Type')
    partner_id      = fields.Many2one('res.partner', 'Partenaire')
    product_id      = fields.Many2one('product.product', "Article")
    product_tmpl_id = fields.Many2one('product.template', "Modèle d'article")
    move_id         = fields.Many2one('stock.move', 'Mouvement de stock')
    move_line_id    = fields.Many2one('stock.move.line', 'Ligne de mouvement de stock')
    lot_id          = fields.Many2one('stock.production.lot', 'Lot')
    is_type_tracabilite = fields.Selection(string='Traçabilité', selection=[('ddm', 'DDM'), ('dlc', 'DLC')])
    is_dlc_ddm      = fields.Date('DLC / DDM', required=True)
    product_uom_id  = fields.Many2one('uom.uom', 'Unité')
    product_uom_qty = fields.Float('Réservé', digits="Product Unit of Measure")
    qty_done        = fields.Float('Fait'   , digits="Product Unit of Measure")
    is_nb_pieces_par_colis = fields.Integer(string='PCB') #, related="product_id.is_nb_pieces_par_colis")
    is_nb_colis            = fields.Float(string='Nb Colis', digits=(14,2))
    is_poids_net_estime    = fields.Float(string='Poids net estimé', digits='Stock Weight', compute='_compute_is_poids_net_estime', readonly=True, store=True, help="Poids net total (Kg)")
    is_poids_net_reel      = fields.Float(string='Poids net réel'  , digits='Stock Weight', help="Poids net réel total (Kg)")
    status_move     = fields.Selection(string='Statut', selection=[('receptionne', 'Réceptionné'),('manquant', 'Manquant'), ('abime', 'Abimé'), ('autre', 'Autre')])
    creer_fnc_vsb   = fields.Boolean(string='Créer FNC visibility', compute='_compute_creer_fnc_vsb', readonly=True, store=False)
    create_date     = fields.Datetime('Date de création')
    write_date      = fields.Datetime('Date de modification')
    state           = fields.Selection(string='Etat picking', selection=_STATE_PICKING)


# psycopg2.errors.UndefinedColumn: ERREUR:  la colonne l.is_nb_pieces_par_colis n'existe pas
# LIGNE 38 :                     l.is_nb_pieces_par_colis,
#                                ^
# ASTUCE : Peut-être que vous souhaitiez référencer la colonne « pt.is_nb_pieces_par_colis ».



    def init(self):
        drop_view_if_exists(self.env.cr, self._table)

        self.env.cr.execute("""

            CREATE OR REPLACE FUNCTION get_prix_achat(productid integer, lotid integer) RETURNS float AS $$
            BEGIN
                RETURN (
                    select pol.price_unit
                    from purchase_order_line pol join stock_move sm on sm.purchase_line_id=pol.id
                                                 join stock_move_line sml on sml.move_id=sm.id
                    where pol.product_id=productid and sml.lot_id=lotid
                    order by pol.id desc limit 1
                );
            END;
            $$ LANGUAGE plpgsql;



            CREATE OR REPLACE view is_stock_move_line AS (
                select 
                    l.id,
                    pt.company_id,
                    m.picking_id,
                    p.date_done::TIMESTAMP::DATE,
                    p.picking_type_id,
                    p.partner_id,
                    m.product_id,
                    pp.product_tmpl_id,
                    l.move_id,
                    l.id move_line_id,
                    l.lot_id,
                    pt.is_type_tracabilite,
                    spl.is_dlc_ddm,
                    l.product_uom_id,
                    l.product_uom_qty,
                    l.qty_done,
                    l.status_move,
                    l.create_date,
                    l.write_date,
                    pt.is_nb_pieces_par_colis,
                    l.is_nb_colis,
                    l.is_poids_net_estime,
                    l.is_poids_net_reel,
                    p.state
                from stock_move_line l join stock_move m on l.move_id=m.id
                                       join stock_picking p on m.picking_id=p.id
                                       join product_product pp on m.product_id=pp.id 
                                       join product_template pt on pp.product_tmpl_id=pt.id
                                       join stock_production_lot spl on l.lot_id=spl.id
            )
        """)


    def creer_fnc_action(self):
        for obj in self:
            res=obj.move_line_id.creer_fnc_action()
            return res


    def acces_fnc_action(self):
        for obj in self:
            res=obj.move_line_id.acces_fnc_action()
            return res


















class is_stock_move_line_valorise_update(models.TransientModel):
    _name='is.stock.move.line.valorise.update'
    _description = "Mise à jour Lignes des mouvements valorisés"

    date_debut = fields.Date('Date début', required=True, default=lambda self: fields.Datetime.now()-timedelta(1))
    date_fin   = fields.Date('Date fin'  , required=True, default=lambda self: fields.Datetime.now())


    def action_ok(self):
        cr,uid,context,su = self.env.args
        filtre=[
            ('date_done','>=',self.date_debut),
            ('date_done','<=',self.date_fin),
        ]
        self.env['is.stock.move.line.valorise'].search(filtre).unlink()

        SQL="""
            select 
                l.id,
                pt.company_id,
                m.picking_id,
                p.date_done::TIMESTAMP::DATE,
                p.picking_type_id,
                p.partner_id,
                -- rp.is_enseigne_id,
                m.product_id,
                pp.product_tmpl_id,
                l.move_id,
                l.id move_line_id,
                l.lot_id,
                pt.is_type_tracabilite,
                spl.is_dlc_ddm,
                l.product_uom_id,
                l.product_uom_qty,
                l.qty_done,
                l.status_move,
                l.create_date,
                l.write_date,
                l.is_nb_pieces_par_colis,
                l.is_nb_colis,
                l.is_poids_net_estime,
                l.is_poids_net_reel,
                p.state,
                COALESCE(get_prix_achat(m.product_id,l.lot_id),sol.is_correction_prix_achat) prix_achat,
                sol.price_unit prix_vente,
                COALESCE(get_prix_achat(m.product_id,l.lot_id),sol.is_correction_prix_achat)*l.qty_done montant_achat,
                sol.price_unit*l.qty_done montant_vente,
                (sol.price_unit*l.qty_done-COALESCE(get_prix_achat(m.product_id,l.lot_id),sol.is_correction_prix_achat)*l.qty_done) marge
            from stock_move_line l join stock_move m on l.move_id=m.id
                                    join stock_picking p on m.picking_id=p.id
                                    join product_product pp on m.product_id=pp.id 
                                    join product_template pt on pp.product_tmpl_id=pt.id
                                    join stock_production_lot spl on l.lot_id=spl.id
                                    join sale_order so on p.sale_id=so.id
                                    join sale_order_line sol on m.sale_line_id=sol.id
                                    join res_partner rp on p.partner_id=rp.id
            where p.state='done' and p.date_done>=%s and p.date_done<=%s
        """
        cr.execute(SQL,[self.date_debut, self.date_fin+timedelta(1)])

        for row in cr.dictfetchall():
            vals={
                "company_id"            : row["company_id"],
                "picking_id"            : row["picking_id"],
                "date_done"             : row["date_done"],
                "picking_type_id"       : row["picking_type_id"],
                "partner_id"            : row["partner_id"],
                #"is_enseigne_id"        : row["is_enseigne_id"],
                "product_id"            : row["product_id"],
                "product_tmpl_id"       : row["product_tmpl_id"],
                "move_id"               : row["move_id"],
                "move_line_id"          : row["move_line_id"],
                "lot_id"                : row["lot_id"],
                "is_type_tracabilite"   : row["is_type_tracabilite"],
                "is_dlc_ddm"            : row["is_dlc_ddm"],
                "product_uom_id"        : row["product_uom_id"],
                "product_uom_qty"       : row["product_uom_qty"],
                "qty_done"              : row["qty_done"],
                "is_nb_pieces_par_colis": row["is_nb_pieces_par_colis"],
                "is_nb_colis"           : row["is_nb_colis"],
                "is_poids_net_estime"   : row["is_poids_net_estime"],
                "is_poids_net_reel"     : row["is_poids_net_reel"],
                "status_move"           : row["status_move"],
                "state"                 : row["state"],
                "prix_achat"            : row["prix_achat"],
                "prix_vente"            : row["prix_vente"],
                "montant_achat"         : row["montant_achat"],
                "montant_vente"         : row["montant_vente"],
                "marge"                 : row["marge"],
             }
            self.env['is.stock.move.line.valorise'].create(vals)

        res= {
            'name': 'Lignes des mouvements valorisés',
            'view_mode': 'tree,form,pivot,graph',
            'res_model': 'is.stock.move.line.valorise',
            'type': 'ir.actions.act_window',
        }
        return res









class is_stock_move_line_valorise(models.Model):
    _name='is.stock.move.line.valorise'
    _description='is.stock.move.line.valorise'
    _order='date_done desc, picking_id'
    #_auto = False


    @api.depends('prix_achat','prix_vente','marge')
    def _compute(self):
        for obj in self:
            alerte=[]
            if not obj.prix_achat:
                alerte.append("Prix d'achat à 0")
            if not obj.prix_vente:
                alerte.append("Prix de vente à 0")
            if obj.marge<0:
                alerte.append("Marge négative")
            if len(alerte)==0:
                alerte=False
            else:
                alerte="\n".join(alerte)
            obj.alerte=alerte
            obj.enseigne=obj.partner_id.is_enseigne_id.name.name


    company_id      = fields.Many2one('res.company', 'Société')
    picking_id      = fields.Many2one('stock.picking', 'Picking')
    date_done       = fields.Date('Date livraison')
    picking_type_id = fields.Many2one('stock.picking.type', 'Type')
    partner_id      = fields.Many2one('res.partner', 'Partenaire')
    #is_enseigne_id  = fields.Many2one('is.enseigne.commerciale', 'Enseigne', help="Enseigne commerciale")
    enseigne        = fields.Char('Enseigne', compute='_compute', readonly=True, store=True, help="Enseigne commerciale")
    product_id      = fields.Many2one('product.product', "Article")
    product_tmpl_id = fields.Many2one('product.template', "Modèle d'article")
    move_id         = fields.Many2one('stock.move', 'Mouvement de stock')
    move_line_id    = fields.Many2one('stock.move.line', 'Ligne de mouvement de stock')
    lot_id          = fields.Many2one('stock.production.lot', 'Lot')
    is_type_tracabilite = fields.Selection(string='Traçabilité', selection=[('ddm', 'DDM'), ('dlc', 'DLC')])
    is_dlc_ddm      = fields.Date('DLC / DDM')
    product_uom_id  = fields.Many2one('uom.uom', 'Unité')
    product_uom_qty = fields.Float('Réservé', digits="Product Unit of Measure")
    qty_done        = fields.Float('Fait'   , digits="Product Unit of Measure")
    is_nb_pieces_par_colis = fields.Integer(string='PCB', related="product_id.is_nb_pieces_par_colis")
    is_nb_colis            = fields.Float(string='Nb Colis', digits=(14,2))
    is_poids_net_estime    = fields.Float(string='Poids net estimé', digits='Stock Weight', help="Poids net total (Kg)")
    is_poids_net_reel      = fields.Float(string='Poids net réel'  , digits='Stock Weight', help="Poids net réel total (Kg)")
    status_move     = fields.Selection(string='Statut', selection=[('receptionne', 'Réceptionné'),('manquant', 'Manquant'), ('abime', 'Abimé'), ('autre', 'Autre')])
    create_date     = fields.Datetime('Date de création')
    write_date      = fields.Datetime('Date de modification')
    state           = fields.Selection(string='Etat picking', selection=_STATE_PICKING)
    prix_achat      = fields.Float(string='Prix achat', digits=(14,4))
    prix_vente      = fields.Float(string='Prix vente', digits=(14,4))
    montant_achat   = fields.Float(string='Montant achat', digits=(14,2))
    montant_vente   = fields.Float(string='Montant vente', digits=(14,2))
    marge           = fields.Float(string='Marge', digits=(14,2))
    alerte          = fields.Text(string='Alerte', compute='_compute', readonly=True, store=True)






    # def init(self):
    #     drop_view_if_exists(self.env.cr, self._table)

    #     self.env.cr.execute("""

    #         CREATE OR REPLACE FUNCTION get_prix_achat(productid integer, lotid integer) RETURNS float AS $$
    #         BEGIN
    #             RETURN (
    #                 select pol.price_unit
    #                 from purchase_order_line pol join stock_move sm on sm.purchase_line_id=pol.id
    #                                              join stock_move_line sml on sml.move_id=sm.id
    #                 where pol.product_id=productid and sml.lot_id=lotid
    #                 order by pol.id desc limit 1
    #             );
    #         END;
    #         $$ LANGUAGE plpgsql;



    #         CREATE OR REPLACE view is_stock_move_line_valorise AS (
    #             select 
    #                 l.id,
    #                 pt.company_id,
    #                 m.picking_id,
    #                 p.date_done::TIMESTAMP::DATE,
    #                 p.picking_type_id,
    #                 p.partner_id,
    #                 rp.is_enseigne_id,
    #                 m.product_id,
    #                 pp.product_tmpl_id,
    #                 l.move_id,
    #                 l.id move_line_id,
    #                 l.lot_id,
    #                 pt.is_type_tracabilite,
    #                 spl.is_dlc_ddm,
    #                 l.product_uom_id,
    #                 l.product_uom_qty,
    #                 l.qty_done,
    #                 l.status_move,
    #                 l.create_date,
    #                 l.write_date,
    #                 l.is_nb_pieces_par_colis,
    #                 l.is_nb_colis,
    #                 l.is_poids_net_estime,
    #                 l.is_poids_net_reel,
    #                 p.state,
    #                 COALESCE(get_prix_achat(m.product_id,l.lot_id),sol.is_correction_prix_achat) prix_achat,
    #                 sol.price_unit prix_vente,
    #                 COALESCE(get_prix_achat(m.product_id,l.lot_id),sol.is_correction_prix_achat)*l.qty_done montant_achat,
    #                 sol.price_unit*l.qty_done montant_vente,
    #                 (sol.price_unit*l.qty_done-COALESCE(get_prix_achat(m.product_id,l.lot_id),sol.is_correction_prix_achat)*l.qty_done) marge
    #             from stock_move_line l join stock_move m on l.move_id=m.id
    #                                    join stock_picking p on m.picking_id=p.id
    #                                    join product_product pp on m.product_id=pp.id 
    #                                    join product_template pt on pp.product_tmpl_id=pt.id
    #                                    join stock_production_lot spl on l.lot_id=spl.id
    #                                    join sale_order so on p.sale_id=so.id
    #                                    join sale_order_line sol on m.sale_line_id=sol.id
    #                                    join res_partner rp on p.partner_id=rp.id
    #             where p.state='done'
    #         )
    #     """)
