# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import timedelta
import time
from odoo.addons.is_fromtome14.models.account_move import _TYPE_AVOIR

import logging
_logger = logging.getLogger(__name__)


_TYPE_LIGNE = [
    ('Facture client', 'Facture client'),
    ('Avoir client'  , 'Avoir client'),
    ('Rebut'         , 'Rebut'),
    ('Avoir fournisseur', 'Avoir fournisseur'),
]

_ORIGINE_PRIX = [
    ('lot'    , 'Lot'),     # Facture d'achat du lot
    ('article', 'Article'), # Dernière facture d'achat de l'article
    ('aucun'  , 'Aucun'),   # Aucun prix d'achat
]


class IsAnalyseMargeLot(models.Model):
    _name = 'is.analyse.marge.lot'
    _description = "Analyse marge brute sur les lots facturés"
    _inherit = ['mail.thread']
    _order = 'id desc'

    @api.depends('ligne_ids')
    def _compute_totaux(self):
        # Calcul en SQL pour ne pas charger les dizaines de milliers de lignes
        cr = self.env.cr
        for obj in self:
            nb_lignes = nb_anomalies = nb_lots_sans_facture = montant_vente = montant_achat = marge_brute = 0
            if isinstance(obj.id, int):
                cr.execute("""
                    SELECT
                        count(*),
                        count(anomalie),
                        count(anomalie) filter (where type_ligne='Facture client'),
                        sum(montant_vente), sum(montant_achat), sum(marge_brute)
                    FROM is_analyse_marge_lot_ligne
                    WHERE analyse_id=%s
                """, [obj.id])
                nb_lignes, nb_anomalies, nb_lots_sans_facture, montant_vente, montant_achat, marge_brute = cr.fetchone()
            obj.nb_lignes     = nb_lignes
            obj.nb_anomalies  = nb_anomalies
            obj.nb_lots_sans_facture = nb_lots_sans_facture
            obj.montant_vente = montant_vente or 0
            obj.montant_achat = montant_achat or 0
            obj.marge_brute   = marge_brute or 0
            obj.taux_marge    = montant_vente and 100*(marge_brute or 0)/montant_vente or 0

    name          = fields.Char('N°Analyse', readonly=True, copy=False)
    date_debut    = fields.Date('Date début', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_fin      = fields.Date('Date fin'  , required=True, default=lambda self: fields.Date.today())
    date_calcul   = fields.Datetime('Date du calcul', readonly=True, copy=False)
    duree_calcul  = fields.Float('Temps de calcul (s)', digits=(14,1), readonly=True, copy=False)
    client        = fields.Char('Client', help="Filtre facultatif pour limiter le calcul : tous les clients dont le nom contient ce texte")
    enseigne_id   = fields.Many2one('is.enseigne.commerciale', 'Enseigne', help="Filtre facultatif pour limiter le calcul")
    user_id       = fields.Many2one('res.users', 'Commercial', help="Filtre facultatif pour limiter le calcul")
    product_id    = fields.Many2one('product.product', 'Produit', help="Filtre facultatif pour limiter le calcul")
    invoice_id    = fields.Many2one('account.move', 'Facture client', domain=[('move_type','in',['out_invoice','out_refund'])], help="Filtre facultatif pour limiter le calcul")
    exclure_hors_lot           = fields.Boolean("Exclure les articles non gérés par lot", default=True, help="Exclure les articles non gérés par lot (transport...) : ils n'ont ni lot ni facture d'achat")
    exclure_services           = fields.Boolean("Exclure les articles de type service", default=True, help="Exclure les articles de type service (vente de véhicule, commissions...) : ils ne relèvent pas de la marge sur les marchandises")
    ligne_ids     = fields.One2many('is.analyse.marge.lot.ligne', 'analyse_id', 'Lignes', copy=False)
    nb_lignes     = fields.Integer('Nb lignes'       , compute='_compute_totaux')
    nb_anomalies  = fields.Integer('Nb anomalies'    , compute='_compute_totaux')
    nb_lots_sans_facture = fields.Integer("Nb lots sans facture d'achat", compute='_compute_totaux', help="Lignes de factures client en anomalie (CDC 2.5)")
    montant_vente = fields.Float('Montant vente lot' , compute='_compute_totaux')
    montant_achat = fields.Float('Montant achat lot' , compute='_compute_totaux')
    marge_brute   = fields.Float('Marge brute lot'   , compute='_compute_totaux')
    taux_marge    = fields.Float('Taux de marge lot (%)', digits=(14,1), compute='_compute_totaux', help="Marge brute lot / Montant vente lot")

    # Contrôle avec la marge brute comptable (factures sans tenir compte des lots), calculé seulement sans filtre facultatif
    vente_facturee         = fields.Float('Ventes facturées'     , readonly=True, copy=False, help="Factures - avoirs clients de la période (sans tenir compte des lots)")
    achat_facture          = fields.Float('Achats facturés'      , readonly=True, copy=False, help="Factures - avoirs fournisseurs de la période (sans tenir compte des lots)")
    rebut                  = fields.Float('Rebuts'               , readonly=True, copy=False, help="Coût des rebuts de la période (pour information : déjà compris dans les achats facturés)")
    marge_brute_comptable  = fields.Float('Marge brute comptable', readonly=True, copy=False, help="Ventes facturées - Achats facturés")
    taux_marge_comptable   = fields.Float('Taux de marge comptable (%)', digits=(14,1), readonly=True, copy=False, help="Marge brute comptable / Ventes facturées")
    ecart_marge_brute      = fields.Float('Écart marge brute'    , readonly=True, copy=False, help="Marge brute lot - Marge brute comptable")


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.analyse.marge.lot')
        res = super(IsAnalyseMargeLot, self).create(vals)
        return res


    #** Recherche des prix d'achat *********************************************
    def _preload_achat_lots(self, cache, lot_ids):
        "Charge en une seule requête la dernière facture d'achat validée de chaque lot (via les réceptions de ces lots)"
        cr = self.env.cr
        lot_ids = list(set(lot_ids)-cache['lots_charges'])
        for i in range(0, len(lot_ids), 5000):
            ids = tuple(lot_ids[i:i+5000])
            sql = """
                SELECT DISTINCT ON (sml.lot_id, aml.product_id)
                    sml.lot_id, aml.product_id, aml.price_unit, aml.discount, am.invoice_date, aml.id, am.partner_id
                FROM stock_move_line sml join stock_move sm        on sml.move_id=sm.id
                                         join account_move_line aml on aml.purchase_line_id=sm.purchase_line_id
                                         join account_move am       on aml.move_id=am.id
                WHERE
                    sml.lot_id in %s and
                    sml.state='done' and
                    am.move_type='in_invoice' and
                    am.state='posted'
                ORDER BY sml.lot_id, aml.product_id, am.invoice_date desc, aml.id desc
            """
            cr.execute(sql, [ids])
            for row in cr.fetchall():
                cache['achat_lot'][(row[0], row[1])] = row[2:]
        cache['lots_charges'].update(lot_ids)


    def _get_achat_lot(self, cache, lot_id, product_id):
        "Dernière facture d'achat validée du lot"
        self._preload_achat_lots(cache, [lot_id])
        return cache['achat_lot'].get((lot_id, product_id), False)


    def _preload_achat_articles(self, cache, product_ids):
        """Charge en une seule requête toutes les factures d'achat validées de ces articles
        => cache['achat_article'][article] = factures d'achat par date décroissante.
        Une requête par article serait très lente (environ 100 ms chacune, car PostgreSQL parcourt toutes les factures fournisseur)"""
        debut = time.time()
        cr = self.env.cr
        product_ids = [product_id for product_id in set(product_ids) if product_id not in cache['achat_article']]
        for product_id in product_ids:
            cache['achat_article'][product_id] = []
        for i in range(0, len(product_ids), 5000):
            ids = tuple(product_ids[i:i+5000])
            sql = """
                SELECT aml.product_id, aml.price_unit, aml.discount, am.invoice_date, aml.id, am.partner_id
                FROM account_move_line aml inner join account_move am on aml.move_id=am.id
                WHERE
                    aml.product_id in %s and
                    am.move_type='in_invoice' and
                    am.state='posted'
                ORDER BY aml.product_id, am.invoice_date desc, aml.id desc
            """
            cr.execute(sql, [ids])
            for row in cr.fetchall():
                cache['achat_article'][row[0]].append(row[1:])
        cache['duree_achat_article'] += time.time()-debut


    def _get_achat_article(self, cache, product_id, date):
        "Dernière facture d'achat de l'article à cette date (sans tenir compte du lot) comme dans l'analyse facturation"
        self._preload_achat_articles(cache, [product_id])
        # Les factures sont triées par date décroissante : la première à date <= date recherchée est la bonne
        for row in cache['achat_article'][product_id]:
            if row[2] and row[2]<=date:
                return row
        return False


    def _get_prix_achat(self, cache, lot_id, product_id, date):
        "Retourne le prix d'achat avec son origine et l'anomalie éventuelle"
        anomalie = False
        row = False
        origine = 'aucun'
        if lot_id:
            row = self._get_achat_lot(cache, lot_id, product_id)
            if row:
                origine = 'lot'
            else:
                anomalie = "Lot sans facture d'achat"
        if not row:
            row = self._get_achat_article(cache, product_id, date)
            if row:
                origine = 'article'
            elif not anomalie:
                anomalie = "Article sans facture d'achat"
        vals = {
            'origine_prix'                : origine,
            'prix_achat'                  : row and row[0] or 0,
            'discount_fournisseur'        : row and row[1] or 0,
            'date_facture_fournisseur'    : row and row[2] or False,
            'ligne_facture_fournisseur_id': row and row[3] or False,
            'fournisseur_id'              : row and row[4] or False,
        }
        vals['prix_achat_net'] = vals['prix_achat']*(1-vals['discount_fournisseur']/100)
        return vals, anomalie
    #***************************************************************************


    #** Filtres pour limiter le calcul *****************************************
    def _calcul_marge_comptable(self):
        """Marge brute comptable de la période à partir des factures et avoirs (sans tenir compte des lots),
        pour vérifier que, sur une période assez longue, elle est proche de la marge brute sur les lots.
        Calculée seulement si aucun filtre facultatif n'est saisi"""
        vals = {
            'vente_facturee'       : 0,
            'achat_facture'        : 0,
            'rebut'                : 0,
            'marge_brute_comptable': 0,
            'taux_marge_comptable' : 0,
            'ecart_marge_brute'    : 0,
        }
        if not (self._has_filtre_client() or self.product_id):
            cr = self.env.cr
            sql = """
                SELECT
                    sum(case when am.move_type='out_invoice' then aml.price_subtotal when am.move_type='out_refund' then -aml.price_subtotal else 0 end),
                    sum(case when am.move_type='in_invoice'  then aml.price_subtotal when am.move_type='in_refund'  then -aml.price_subtotal else 0 end)
                FROM account_move_line aml join account_move am      on am.id=aml.move_id
                                           join product_product pp   on pp.id=aml.product_id
                                           join product_template pt  on pt.id=pp.product_tmpl_id
                WHERE
                    am.state='posted' and
                    am.move_type in ('out_invoice','out_refund','in_invoice','in_refund') and
                    am.invoice_date>=%s and
                    am.invoice_date<=%s and
                    aml.exclude_from_invoice_tab=false and
                    aml.display_type is null and
                    (not %s or pt.type<>'service') and
                    (not %s or pt.tracking<>'none')
            """
            cr.execute(sql, [self.date_debut, self.date_fin, self.exclure_services, self.exclure_hors_lot])
            vente, achat = cr.fetchone()
            cr.execute("SELECT sum(montant_achat) FROM is_analyse_marge_lot_ligne WHERE analyse_id=%s and type_ligne='Rebut'", [self.id])
            rebut = cr.fetchone()[0]
            vals['vente_facturee']        = vente or 0
            vals['achat_facture']         = achat or 0
            vals['rebut']                 = rebut or 0
            vals['marge_brute_comptable'] = vals['vente_facturee']-vals['achat_facture']
            vals['taux_marge_comptable']  = vals['vente_facturee'] and 100*vals['marge_brute_comptable']/vals['vente_facturee'] or 0
            vals['ecart_marge_brute']     = self.marge_brute-vals['marge_brute_comptable']
        self.write(vals)


    def _has_filtre_client(self):
        return bool(self.client or self.enseigne_id or self.user_id or self.invoice_id)


    def _get_domain_factures(self):
        "Domaine sur account.move correspondant aux filtres saisis"
        domain = []
        if self.client:
            domain.append(('partner_id.name','ilike',self.client))
        if self.enseigne_id:
            domain.append(('is_enseigne_id','=',self.enseigne_id.id))
        if self.user_id:
            domain.append(('partner_id.user_id','=',self.user_id.id))
        if self.invoice_id:
            domain.append(('id','=',self.invoice_id.id))
        if self.product_id:
            domain.append(('invoice_line_ids.product_id','=',self.product_id.id))
        return domain


    def _partner_ok(self, partner, enseigne_id, user_id):
        "Indique si le client, l'enseigne et le commercial de la vente correspondent aux filtres saisis (répartition des rebuts et des avoirs fournisseurs)"
        if self.client and self.client.lower() not in (partner.name or '').lower():
            return False
        if self.enseigne_id and enseigne_id!=self.enseigne_id.id:
            return False
        if self.user_id and user_id!=self.user_id.id:
            return False
        if self.invoice_id and partner!=self.invoice_id.partner_id:
            return False
        return True


    def _get_lots_factures_filtre(self):
        "Lots facturés (toutes dates confondues) sur les factures client correspondant aux filtres"
        filtre = [
            ('state','=','posted'),
            ('move_type','=','out_invoice'),
        ]+self._get_domain_factures()
        invoice_ids = self.env['account.move'].search(filtre).ids
        if not invoice_ids:
            return []
        cr = self.env.cr
        sql = """
            SELECT DISTINCT sml.lot_id
            FROM stock_move_line sml join stock_move sm on sml.move_id=sm.id
                                     join sale_order_line_invoice_rel rel on rel.order_line_id=sm.sale_line_id
                                     join account_move_line aml on aml.id=rel.invoice_line_id
            WHERE
                sml.lot_id is not null and
                sml.state='done' and
                aml.move_id in %s
        """
        cr.execute(sql, [tuple(invoice_ids)])
        return [row[0] for row in cr.fetchall()]
    #***************************************************************************


    def _preload_lots_lignes(self, cache, line_ids):
        """Charge en une seule requête les mouvements par lot des lignes de factures client
        => cache['lots_ligne'][ligne facture] = liste de (lot, picking, code du type de picking, quantité dans l'unité de l'article)"""
        cr = self.env.cr
        line_ids = [line_id for line_id in set(line_ids) if line_id not in cache['lots_ligne']]
        if not line_ids:
            return
        for line_id in line_ids:
            cache['lots_ligne'][line_id] = []
        for i in range(0, len(line_ids), 5000):
            ids = tuple(line_ids[i:i+5000])
            sql = """
                SELECT rel.invoice_line_id, sml.lot_id, sml.picking_id, spt.code, sum(sml.qty_done/u1.factor*u2.factor)
                FROM sale_order_line_invoice_rel rel join account_move_line aml  on aml.id=rel.invoice_line_id
                                                     join stock_move sm          on sm.sale_line_id=rel.order_line_id
                                                     join stock_move_line sml    on sml.move_id=sm.id
                                                     join stock_picking sp       on sp.id=sml.picking_id
                                                     join stock_picking_type spt on spt.id=sp.picking_type_id
                                                     join product_product pp     on pp.id=aml.product_id
                                                     join product_template pt    on pt.id=pp.product_tmpl_id
                                                     join uom_uom u1             on u1.id=sml.product_uom_id
                                                     join uom_uom u2             on u2.id=pt.uom_id
                WHERE
                    rel.invoice_line_id in %s and
                    sml.state='done' and
                    sml.lot_id is not null and
                    sml.product_id=aml.product_id
                GROUP BY rel.invoice_line_id, sml.lot_id, sml.picking_id, spt.code
            """
            cr.execute(sql, [ids])
            for row in cr.fetchall():
                cache['lots_ligne'][row[0]].append(row[1:])


    def _get_repartition(self, cache, line_id, move_type, is_picking_id):
        """Répartition de la ligne de facture client par lot => liste de (lot, ratio)
        Pour les factures, ce sont les livraisons, et pour les avoirs, les retours"""
        self._preload_lots_lignes(cache, [line_id])
        code = 'outgoing'
        if move_type=='out_refund':
            code = 'incoming'
        rows = [row for row in cache['lots_ligne'][line_id] if row[2]==code]
        if not rows and move_type=='out_refund':
            # Avoir sans retour de marchandise (ex : avoir qualité) : lots livrés sur la ligne de commande
            rows = [row for row in cache['lots_ligne'][line_id] if row[2]=='outgoing']
        if is_picking_id:
            filtered = [row for row in rows if row[1]==is_picking_id]
            if filtered:
                rows = filtered
        lots = {}
        for lot_id, picking_id, code, qty in rows:
            lots.setdefault(lot_id, 0)
            lots[lot_id] += qty
        total = sum(lots.values())
        if not total:
            return []
        return [(lot_id, qty/total) for lot_id, qty in lots.items() if qty]


    def _avoir_sans_retour(self, cache, line_id):
        "Avoir client sans retour de marchandise (aucun mouvement d'entrée sur la ligne de commande)"
        self._preload_lots_lignes(cache, [line_id])
        return not [row for row in cache['lots_ligne'][line_id] if row[2]=='incoming']


    def _calcul_factures(self, cache):
        date_debut = self.date_debut
        date_fin   = self.date_fin
        filtre=[
            ('invoice_date','>=',date_debut),
            ('invoice_date','<=',date_fin),
            ('state','=','posted'),
            ('move_type','in',['out_invoice','out_refund']),
        ]+self._get_domain_factures()
        debut = time.time()
        invoices = self.env['account.move'].search(filtre, order='invoice_date,id')
        nb=len(invoices)

        #** Chargement en quelques requêtes des lots et des prix d'achat de ces lots
        self._preload_lots_lignes(cache, invoices.mapped('invoice_line_ids').ids)
        lot_ids = set(row[0] for rows in cache['lots_ligne'].values() for row in rows)
        self._preload_achat_lots(cache, lot_ids)
        self._preload_achat_articles(cache, invoices.mapped('invoice_line_ids.product_id').ids)
        _logger.info("Analyse marge lot %s : chargement des lots et des prix d'achat en %.1fs"%(self.name, time.time()-debut))
        #**********************************************************************

        ct=0
        vals_list=[]
        for invoice in invoices:
            ct+=1
            if ct%100==0 or ct==nb:
                _logger.info("Analyse marge lot %s : %s/%s : %s (%.1fs)"%(self.name,ct,nb,invoice.name,time.time()-debut))
            sens = 1
            type_ligne = 'Facture client'
            is_type_avoir = False
            if invoice.move_type=='out_refund':
                sens = -1
                type_ligne = 'Avoir client'
                is_type_avoir = invoice.is_type_avoir
            for line in invoice.invoice_line_ids:
                if line.display_type or not line.product_id:
                    continue
                if line.price_subtotal==0.0 and line.quantity==0.0:
                    continue
                if self.product_id and line.product_id!=self.product_id:
                    continue
                if self.exclure_services and line.product_id.type=='service':
                    continue
                if self.exclure_hors_lot and line.product_id.tracking=='none':
                    continue

                # Articles non gérés par lot ou de type service (transport, ...) : jamais d'anomalie
                sans_anomalie = line.product_id.tracking=='none' or line.product_id.type=='service'

                #** Répartition par lot ***************************************
                repartition = []
                anomalie_lot = False
                if is_type_avoir!='avoir_prix':
                    repartition = self._get_repartition(cache, line.id, invoice.move_type, line.is_picking_id.id)
                    if not repartition and line.product_id.tracking!='none':
                        anomalie_lot = "Aucun lot sur les livraisons"
                if not repartition:
                    repartition = [(False, 1)]
                #**************************************************************

                # Avoir sur quantité sans retour de marchandise : la marchandise est perdue, le coût
                # d'achat est gardé (un éventuel avoir fournisseur est traité dans _calcul_avoirs_fournisseurs)
                sans_retour = invoice.move_type=='out_refund' and is_type_avoir!='avoir_prix' and self._avoir_sans_retour(cache, line.id)

                for lot_id, ratio in repartition:
                    quantity      = sens*line.quantity*ratio
                    montant_vente = sens*line.price_subtotal*ratio
                    if is_type_avoir=='avoir_prix':
                        # Avoir sur prix : pas de coût d'achat comme dans l'analyse facturation
                        vals_achat = {'origine_prix': 'aucun'}
                        anomalie = False
                        montant_achat = 0
                    else:
                        vals_achat, anomalie = self._get_prix_achat(cache, lot_id, line.product_id.id, invoice.invoice_date)
                        montant_achat = vals_achat['prix_achat_net']*quantity
                        if sans_retour:
                            montant_achat = 0
                    vals={
                        "analyse_id"     : self.id,
                        "type_ligne"     : type_ligne,
                        "is_type_avoir"  : is_type_avoir,
                        "sans_retour"    : sans_retour,
                        "date"           : invoice.invoice_date,
                        "invoice_id"     : invoice.id,
                        "invoice_line_id": line.id,
                        "partner_id"     : invoice.partner_id.id,
                        "user_id"        : invoice.partner_id.user_id.id,
                        "enseigne_id"    : invoice.is_enseigne_id.id,
                        "product_id"     : line.product_id.id,
                        "product_uom_id" : line.product_uom_id.id,
                        "lot_id"         : lot_id,
                        "libelle"        : line.name,
                        "quantity"       : quantity,
                        "price_unit"     : line.price_unit,
                        "discount"       : line.discount,
                        "montant_vente"  : montant_vente,
                        "montant_achat"  : montant_achat,
                        "marge_brute"    : montant_vente-montant_achat,
                        "anomalie"       : not sans_anomalie and (anomalie_lot or anomalie) or False,
                    }
                    vals.update(vals_achat)
                    vals_list.append(vals)
        duree_recherche = time.time()-debut
        self.env['is.analyse.marge.lot.ligne'].create(vals_list)
        _logger.info("Analyse marge lot %s : factures terminées : %s factures, %s lignes en %.1fs (recherche %.1fs dont factures d'achat par article %.1fs pour %s articles + création %.1fs)"%(
            self.name, nb, len(vals_list), time.time()-debut, duree_recherche, cache['duree_achat_article'], len(cache['achat_article']), time.time()-debut-duree_recherche))
        return nb, time.time()-debut


    def _preload_quantites_facturees_lots(self, cache, lot_ids):
        """Charge en quelques requêtes les quantités facturées aux clients sur ces lots (toutes dates confondues)
        => cache['qt_lot'][lot] = {(client, enseigne, commercial): quantité}
        L'enseigne est celle de la facture client (au moment de la vente), comme pour les lignes de factures"""
        cr = self.env.cr
        lot_ids = [lot_id for lot_id in set(lot_ids) if lot_id not in cache['qt_lot']]
        for lot_id in lot_ids:
            cache['qt_lot'][lot_id] = {}
        for i in range(0, len(lot_ids), 5000):
            ids = tuple(lot_ids[i:i+5000])
            sql = """
                SELECT DISTINCT sml.lot_id, aml.id, am.partner_id, am.is_enseigne_id, rp.user_id, aml.quantity, aml.is_picking_id
                FROM stock_move_line sml join stock_move sm on sml.move_id=sm.id
                                         join sale_order_line_invoice_rel rel on rel.order_line_id=sm.sale_line_id
                                         join account_move_line aml on aml.id=rel.invoice_line_id
                                         join account_move am on aml.move_id=am.id
                                         join res_partner rp on rp.id=am.partner_id
                WHERE
                    sml.lot_id in %s and
                    sml.state='done' and
                    am.move_type='out_invoice' and
                    am.state='posted'
            """
            cr.execute(sql, [ids])
            rows = cr.fetchall()
            self._preload_lots_lignes(cache, [row[1] for row in rows])
            for lot_id, line_id, partner_id, enseigne_id, user_id, quantity, is_picking_id in rows:
                for l, ratio in self._get_repartition(cache, line_id, 'out_invoice', is_picking_id):
                    if l==lot_id:
                        key = (partner_id, enseigne_id, user_id)
                        qt_partners = cache['qt_lot'][lot_id]
                        qt_partners.setdefault(key, 0)
                        qt_partners[key] += quantity*ratio


    def _get_repartition_clients(self, cache, lot_id):
        """Répartition d'un coût du lot (rebut, avoir fournisseur) sur les clients qui ont acheté ce lot,
        au prorata des quantités facturées => liste de ((client, enseigne, commercial), ratio)
        Avec un filtre client, seules les parts correspondant aux filtres sont conservées"""
        qt_partners = cache['qt_lot'].get(lot_id, {})
        total = sum(qt_partners.values())
        if not total:
            return []
        repartition = [(key, qty/total) for key, qty in qt_partners.items() if qty]
        if self._has_filtre_client():
            repartition = [(key, ratio) for key, ratio in repartition if self._partner_ok(self.env['res.partner'].browse(key[0]), key[1], key[2])]
        return repartition


    def _calcul_rebuts(self, cache):
        debut = time.time()
        filtre=[
            ('date_done','>=',self.date_debut),
            ('date_done','<',self.date_fin+timedelta(1)),
            ('state','=','done'),
        ]
        if self.product_id:
            filtre.append(('product_id','=',self.product_id.id))
        if self.exclure_hors_lot:
            filtre.append(('product_id.tracking','!=','none'))
        if self._has_filtre_client():
            filtre.append(('lot_id','in',self._get_lots_factures_filtre()))
        scraps = self.env['stock.scrap'].search(filtre, order='date_done,id')
        nb=len(scraps)

        #** Chargement en quelques requêtes des prix d'achat et des quantités facturées des lots
        self._preload_achat_lots(cache, scraps.mapped('lot_id').ids)
        self._preload_achat_articles(cache, scraps.mapped('product_id').ids)
        self._preload_quantites_facturees_lots(cache, scraps.mapped('lot_id').ids)
        _logger.info("Analyse marge lot %s : chargement des lots des rebuts en %.1fs"%(self.name, time.time()-debut))
        #**********************************************************************

        ct=0
        vals_list=[]
        for scrap in scraps:
            ct+=1
            if ct%100==0 or ct==nb:
                _logger.info("Analyse marge lot %s : rebut %s/%s : %s (%.1fs)"%(self.name,ct,nb,scrap.name,time.time()-debut))
            product   = scrap.product_id
            date      = scrap.date_done.date()
            scrap_qty = scrap.product_uom_id._compute_quantity(scrap.scrap_qty, product.uom_id)
            vals_achat, anomalie = self._get_prix_achat(cache, scrap.lot_id.id, product.id, date)
            cout = vals_achat['prix_achat_net']*scrap_qty

            #** Répartition du coût par client ********************************
            repartition = []
            if not scrap.lot_id:
                anomalie = "Rebut sans lot"
            else:
                repartition = self._get_repartition_clients(cache, scrap.lot_id.id)
                if not sum(cache['qt_lot'][scrap.lot_id.id].values()):
                    anomalie = "Lot sans facture client"
            if not repartition and not self._has_filtre_client():
                repartition = [((False, False, False), 1)]
            #******************************************************************

            for (partner_id, enseigne_id, user_id), ratio in repartition:
                montant_achat = cout*ratio
                vals={
                    "analyse_id"     : self.id,
                    "type_ligne"     : 'Rebut',
                    "date"           : date,
                    "scrap_id"       : scrap.id,
                    "partner_id"     : partner_id,
                    "user_id"        : user_id,
                    "enseigne_id"    : enseigne_id,
                    "product_id"     : product.id,
                    "product_uom_id" : product.uom_id.id,
                    "lot_id"         : scrap.lot_id.id,
                    "libelle"        : scrap.name+" / "+(scrap.origin or ''),
                    "quantity"       : scrap_qty*ratio,
                    "montant_vente"  : 0,
                    "montant_achat"  : montant_achat,
                    "marge_brute"    : -montant_achat,
                    # Articles non gérés par lot ou de type service : jamais d'anomalie
                    "anomalie"       : product.tracking!='none' and product.type!='service' and anomalie or False,
                }
                vals.update(vals_achat)
                vals_list.append(vals)
        duree_recherche = time.time()-debut
        self.env['is.analyse.marge.lot.ligne'].create(vals_list)
        _logger.info("Analyse marge lot %s : rebuts terminés : %s rebuts, %s lignes en %.1fs (recherche %.1fs + création %.1fs)"%(
            self.name, nb, len(vals_list), time.time()-debut, duree_recherche, time.time()-debut-duree_recherche))
        return nb, time.time()-debut


    def _preload_lots_achats(self, cache, purchase_line_ids):
        """Charge en une seule requête les mouvements par lot des lignes de commande d'achat
        => cache['lots_achat'][ligne de commande] = liste de (lot, code du type de picking, quantité)
        Un mouvement de sortie sur une ligne de commande d'achat est un retour au fournisseur"""
        cr = self.env.cr
        purchase_line_ids = [pol_id for pol_id in set(purchase_line_ids) if pol_id not in cache['lots_achat']]
        for pol_id in purchase_line_ids:
            cache['lots_achat'][pol_id] = []
        for i in range(0, len(purchase_line_ids), 5000):
            ids = tuple(purchase_line_ids[i:i+5000])
            sql = """
                SELECT sm.purchase_line_id, sml.lot_id, spt.code, sum(sml.qty_done)
                FROM stock_move sm join stock_move_line sml    on sml.move_id=sm.id
                                   join stock_picking sp       on sp.id=sml.picking_id
                                   join stock_picking_type spt on spt.id=sp.picking_type_id
                WHERE
                    sm.purchase_line_id in %s and
                    sml.state='done'
                GROUP BY sm.purchase_line_id, sml.lot_id, spt.code
            """
            cr.execute(sql, [ids])
            for row in cr.fetchall():
                cache['lots_achat'][row[0]].append(row[1:])
            # Factures fournisseur de ces lignes de commande (pour détecter les refacturations après un avoir)
            sql = """
                SELECT aml.purchase_line_id, am.id, am.invoice_date
                FROM account_move_line aml join account_move am on am.id=aml.move_id
                WHERE
                    aml.purchase_line_id in %s and
                    am.move_type='in_invoice' and
                    am.state='posted'
            """
            cr.execute(sql, [ids])
            for row in cr.fetchall():
                cache['factures_achat'].setdefault(row[0], []).append(row[1:])


    def _avoir_fournisseur_refacture(self, cache, line):
        """Avoir fournisseur suivi d'une nouvelle facture sur la même ligne de commande (ex : extourne pour erreur de tarif
        puis refacturation) : le coût du lot est déjà calculé avec le prix de la nouvelle facture, l'avoir ne doit pas être déduit"""
        refund = line.move_id
        for move_id, invoice_date in cache['factures_achat'].get(line.purchase_line_id.id, []):
            if invoice_date and (invoice_date>refund.invoice_date or (invoice_date==refund.invoice_date and move_id>refund.id)):
                return True
        return False


    def _calcul_avoirs_fournisseurs(self, cache):
        """Avoirs fournisseurs de la période : le montant de l'avoir diminue le coût d'achat des lots reçus
        sur la ligne de commande d'achat, réparti sur les clients qui ont acheté ces lots (comme les rebuts)"""
        debut = time.time()
        filtre=[
            ('move_id.move_type','=','in_refund'),
            ('move_id.state','=','posted'),
            ('move_id.invoice_date','>=',self.date_debut),
            ('move_id.invoice_date','<=',self.date_fin),
            ('exclude_from_invoice_tab','=',False),
            ('display_type','=',False),
            ('product_id','!=',False),
        ]
        if self.product_id:
            filtre.append(('product_id','=',self.product_id.id))
        if self.exclure_services:
            filtre.append(('product_id.type','!=','service'))
        if self.exclure_hors_lot:
            filtre.append(('product_id.tracking','!=','none'))
        lines = self.env['account.move.line'].search(filtre, order='date,id')
        nb = len(lines.mapped('move_id'))

        #** Chargement en quelques requêtes des lots reçus et des quantités facturées de ces lots
        purchase_line_ids = lines.mapped('purchase_line_id').ids
        self._preload_lots_achats(cache, purchase_line_ids)
        lot_ids = set(row[0] for pol_id in purchase_line_ids for row in cache['lots_achat'][pol_id] if row[0] and row[1]=='incoming')
        self._preload_quantites_facturees_lots(cache, lot_ids)
        lots_filtre = self._has_filtre_client() and set(self._get_lots_factures_filtre())
        _logger.info("Analyse marge lot %s : chargement des lots des avoirs fournisseurs en %.1fs"%(self.name, time.time()-debut))
        #**********************************************************************

        vals_list=[]
        nb_retour = nb_refacture = 0
        for line in lines:
            refund  = line.move_id
            product = line.product_id
            montant = line.price_subtotal
            if not montant:
                continue

            #** Répartition par lot puis par client => liste de (lot, (client, enseigne, commercial), ratio, anomalie)
            repartition = []
            if not line.purchase_line_id:
                repartition = [(False, (False, False, False), 1, "Avoir fournisseur sans commande")]
            else:
                rows = cache['lots_achat'][line.purchase_line_id.id]
                if [row for row in rows if row[1]=='outgoing']:
                    # Marchandise renvoyée au fournisseur : jamais vendue, son coût n'a pas été imputé aux clients
                    nb_retour += 1
                    continue
                if self._avoir_fournisseur_refacture(cache, line):
                    nb_refacture += 1
                    continue
                lots = {}
                for lot_id, code, qty in rows:
                    if lot_id and code=='incoming':
                        lots.setdefault(lot_id, 0)
                        lots[lot_id] += qty
                total = sum(lots.values())
                if not total:
                    repartition = [(False, (False, False, False), 1, "Avoir fournisseur sans lot")]
                for lot_id, qty in lots.items():
                    if not total or not qty:
                        continue
                    if lots_filtre is not False and lot_id not in lots_filtre:
                        continue
                    clients = self._get_repartition_clients(cache, lot_id)
                    for key, ratio in clients:
                        repartition.append((lot_id, key, qty/total*ratio, False))
                    if not clients:
                        repartition.append((lot_id, (False, False, False), qty/total, "Lot sans facture client"))
            if self._has_filtre_client():
                # Avec un filtre client, les lignes sans client ne sont pas reprises
                repartition = [r for r in repartition if r[1][0]]
            #******************************************************************

            # Articles non gérés par lot ou de type service : jamais d'anomalie
            sans_anomalie = product.tracking=='none' or product.type=='service'
            for lot_id, (partner_id, enseigne_id, user_id), ratio, anomalie in repartition:
                montant_achat = -montant*ratio
                vals={
                    "analyse_id"     : self.id,
                    "type_ligne"     : 'Avoir fournisseur',
                    "date"           : refund.invoice_date,
                    "invoice_id"     : refund.id,
                    "invoice_line_id": line.id,
                    "partner_id"     : partner_id,
                    "user_id"        : user_id,
                    "enseigne_id"    : enseigne_id,
                    "product_id"     : product.id,
                    "product_uom_id" : line.product_uom_id.id,
                    "lot_id"         : lot_id,
                    "libelle"        : "%s / %s"%(refund.name, refund.ref or ''),
                    "quantity"       : -line.quantity*ratio,
                    "montant_vente"  : 0,
                    "fournisseur_id" : refund.partner_id.id,
                    "prix_achat"     : line.price_unit,
                    "discount_fournisseur": line.discount,
                    "prix_achat_net" : line.quantity and montant/line.quantity or 0,
                    "montant_achat"  : montant_achat,
                    "marge_brute"    : -montant_achat,
                    "anomalie"       : not sans_anomalie and anomalie or False,
                }
                vals_list.append(vals)
        duree_recherche = time.time()-debut
        self.env['is.analyse.marge.lot.ligne'].create(vals_list)
        _logger.info("Analyse marge lot %s : avoirs fournisseurs terminés : %s avoirs (lignes non reprises : %s avec retour au fournisseur, %s refacturées), %s lignes en %.1fs (recherche %.1fs + création %.1fs)"%(
            self.name, nb, nb_retour, nb_refacture, len(vals_list), time.time()-debut, duree_recherche, time.time()-debut-duree_recherche))
        return nb, time.time()-debut


    def calculer_action(self):
        for obj in self:
            debut = time.time()
            _logger.info("===== DEBUT ANALYSE MARGE LOT %s DU %s AU %s ====="%(obj.name, obj.date_debut, obj.date_fin))
            obj.ligne_ids.unlink()
            _logger.info("Analyse marge lot %s : suppression des anciennes lignes en %.1fs"%(obj.name, time.time()-debut))
            cache = {
                'achat_lot'    : {},    # (lot, article) => facture d'achat du lot
                'lots_charges' : set(), # lots dont les factures d'achat sont déjà chargées
                'achat_article': {},    # article => factures d'achat de l'article par date décroissante
                'duree_achat_article': 0, # temps de chargement des factures d'achat par article (pour les logs)
                'lots_ligne'   : {},    # ligne de facture client => mouvements par lot
                'qt_lot'       : {},    # lot => {(client, enseigne, commercial): quantité facturée}
                'lots_achat'   : {},    # ligne de commande d'achat => mouvements par lot
                'factures_achat': {},   # ligne de commande d'achat => factures fournisseur (id, date)
            }
            nb_factures, duree_factures = obj._calcul_factures(cache)
            nb_rebuts  , duree_rebuts   = obj._calcul_rebuts(cache)
            nb_avoirs_fournisseurs, duree_avoirs_fournisseurs = obj._calcul_avoirs_fournisseurs(cache)
            obj.date_calcul = fields.Datetime.now()
            duree = time.time()-debut
            obj.duree_calcul = duree
            obj._calcul_marge_comptable()
            _logger.info("===== FIN ANALYSE MARGE LOT %s : %s LIGNES EN %.1fs ====="%(obj.name, obj.nb_lignes, duree))

            #** Résumé du calcul dans le chatter ******************************
            infos = [
                ("Temps de calcul"           , "%.1fs (factures %.1fs, rebuts %.1fs, avoirs fournisseurs %.1fs)"%(duree, duree_factures, duree_rebuts, duree_avoirs_fournisseurs)),
                ("Factures et avoirs traités", nb_factures),
                ("Rebuts traités"            , nb_rebuts),
                ("Avoirs fournisseurs traités", nb_avoirs_fournisseurs),
                ("Lignes créées"             , obj.nb_lignes),
                ("Lignes en anomalie"        , obj.nb_anomalies),
                ("Marge brute"               , "%.2f"%obj.marge_brute),
            ]
            body = "<b>Calcul terminé</b><ul>%s</ul>"%"".join("<li>%s : %s</li>"%(k, v) for k, v in infos)
            obj.message_post(body=body)
            #******************************************************************


    #** Accès aux résultats ****************************************************
    def _action_lignes(self, name, context={}, domain=[], view_mode='pivot,tree,form,graph'):
        self.ensure_one()
        return {
            'name'     : "%s (%s)"%(name, self.name),
            'view_mode': view_mode,
            'res_model': 'is.analyse.marge.lot.ligne',
            'type'     : 'ir.actions.act_window',
            'domain'   : [('analyse_id','=',self.id)]+domain,
            'context'  : context,
        }


    def _action_pivot(self, name, groupby):
        context = {
            'pivot_row_groupby'   : [groupby],
            'pivot_column_groupby': [],
            'pivot_measures'      : ['marge_brute'],
            # Mêmes données pour la vue graphique
            'graph_groupbys'      : [groupby],
            'graph_measure'       : 'marge_brute',
        }
        return self._action_lignes(name, context=context)


    def marge_par_client_action(self):
        return self._action_pivot('Marge brute par client', 'partner_id')


    def marge_par_enseigne_action(self):
        return self._action_pivot('Marge brute par enseigne', 'enseigne_id')


    def marge_par_commercial_action(self):
        return self._action_pivot('Marge brute par commercial', 'user_id')


    def marge_par_produit_action(self):
        return self._action_pivot('Marge brute par produit', 'product_id')


    def marge_par_facture_action(self):
        return self._action_pivot('Marge brute par facture client', 'invoice_id')


    def lignes_action(self):
        return self._action_lignes('Lignes', view_mode='tree,form,pivot,graph')


    def anomalies_lot_action(self):
        "Lots facturés aux clients sur la période sans facture d'achat associée"
        domain = [
            ('type_ligne','=','Facture client'),
            ('anomalie','!=',False),
        ]
        return self._action_lignes("Lots sans facture d'achat", domain=domain, view_mode='tree,form')


    def anomalies_action(self):
        "Toutes les lignes en anomalie (factures, avoirs et rebuts) : correspond au compteur Anomalies"
        return self._action_lignes("Anomalies", domain=[('anomalie','!=',False)], view_mode='tree,form')
    #***************************************************************************


class IsAnalyseMargeLotLigne(models.Model):
    _name = 'is.analyse.marge.lot.ligne'
    _description = "Ligne analyse marge brute sur les lots facturés"
    _order = 'date desc, type_ligne, id'

    analyse_id      = fields.Many2one('is.analyse.marge.lot', 'Analyse', required=True, ondelete='cascade', index=True)
    type_ligne      = fields.Selection(_TYPE_LIGNE, 'Type', index=True)
    is_type_avoir   = fields.Selection(_TYPE_AVOIR, 'Type avoir')
    sans_retour     = fields.Boolean('Avoir sans retour', help="Avoir client sur quantité sans retour de marchandise : le coût d'achat est gardé (marchandise perdue)")
    date            = fields.Date("Date", help="Date facture, avoir ou rebut")
    invoice_id      = fields.Many2one('account.move', 'Facture')
    invoice_line_id = fields.Many2one('account.move.line', 'Ligne de facture')
    scrap_id        = fields.Many2one('stock.scrap', 'Rebut')
    partner_id      = fields.Many2one('res.partner', 'Client')
    user_id         = fields.Many2one('res.users', 'Commercial')
    enseigne_id     = fields.Many2one('is.enseigne.commerciale', 'Enseigne')
    product_id      = fields.Many2one('product.product', 'Article')
    categ_id        = fields.Many2one('product.category', 'Catégorie', related='product_id.categ_id', store=True)
    product_uom_id  = fields.Many2one('uom.uom', 'Unité')
    lot_id          = fields.Many2one('stock.production.lot', 'Lot')
    libelle         = fields.Text('Libellé')
    quantity        = fields.Float("Quantité", digits='Product Unit of Measure')
    price_unit      = fields.Float("Prix de vente", digits='Product Price')
    discount        = fields.Float("Remise", digits='Discount')
    montant_vente   = fields.Float("Vente", help="Montant de vente HT")

    origine_prix                 = fields.Selection(_ORIGINE_PRIX, "Origine prix", help="Origine du prix d'achat : facture d'achat du lot, dernière facture d'achat de l'article ou aucun prix")
    prix_achat                   = fields.Float("Prix d'achat", digits='Product Price')
    discount_fournisseur         = fields.Float("Remise fournisseur", digits='Discount')
    prix_achat_net               = fields.Float("Prix d'achat net", digits='Product Price', help="Prix d'achat avec la remise fournisseur")
    ligne_facture_fournisseur_id = fields.Many2one('account.move.line', 'Ligne facture fournisseur')
    date_facture_fournisseur     = fields.Date("Date facture fournisseur")
    fournisseur_id               = fields.Many2one('res.partner', 'Fournisseur')
    montant_achat                = fields.Float("Achat", help="Montant d'achat avec remise fournisseur (coût du rebut pour les rebuts)")
    marge_brute                  = fields.Float("Marge brute")
    anomalie                     = fields.Text("Anomalie") # Text pour le retour à la ligne dans les listes
