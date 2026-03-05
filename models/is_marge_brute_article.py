# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import date

import logging
_logger = logging.getLogger(__name__)


class IsMargeBruteArticle(models.Model):
    _name = 'is.marge.brute.article'
    _description = "Marge brute par article"
    _order = 'annee desc, product_id'

    product_id              = fields.Many2one('product.product', 'Article', readonly=True, index=True)
    default_code            = fields.Char('Référence interne', related='product_id.default_code', store=True, readonly=True)
    categ_id                = fields.Many2one('product.category', 'Catégorie', related='product_id.categ_id', store=True, readonly=True)
    is_fournisseur_id       = fields.Many2one('res.partner', 'Fournisseur', related='product_id.is_fournisseur_id', store=True, readonly=True)
    annee                   = fields.Char('Année', readonly=True, index=True)
    facturation_client      = fields.Float("Facturation client", readonly=True, help="Total HT des ventes (factures - avoirs clients)")
    facturation_fournisseur = fields.Float("Facturation fournisseur", readonly=True, help="Total HT des achats (factures - avoirs fournisseurs)")
    marge_brute_facturation = fields.Float("Marge brute", readonly=True, help="Facturation client - Facturation fournisseur")

    @api.model
    def _cron_marge_brute_article(self):
        """Tâche planifiée : recalcule la marge brute par article et par année"""
        cr = self.env.cr

        # Vider la table
        cr.execute("DELETE FROM is_marge_brute_article")

        # === Facturation client par article et par année ===
        # price_subtotal dans account_move_line est déjà signé correctement pour les factures
        # mais pour les avoirs il faut inverser le signe
        sql_client = """
            SELECT
                aml.product_id,
                EXTRACT(YEAR FROM am.invoice_date)::int AS annee,
                COALESCE(SUM(
                    CASE WHEN am.move_type = 'out_invoice' THEN aml.price_subtotal
                         WHEN am.move_type = 'out_refund'  THEN -aml.price_subtotal
                         ELSE 0 END
                ), 0) AS total
            FROM account_move_line aml
            JOIN account_move am ON aml.move_id = am.id
            WHERE am.state = 'posted'
              AND am.move_type IN ('out_invoice', 'out_refund')
              AND aml.product_id IS NOT NULL
              AND aml.exclude_from_invoice_tab = False
            GROUP BY aml.product_id, EXTRACT(YEAR FROM am.invoice_date)
        """
        cr.execute(sql_client)
        client_data = {}
        for row in cr.fetchall():
            key = (row[0], str(row[1]))
            client_data[key] = round(row[2], 2)

        # === Facturation fournisseur par article et par année ===
        sql_fournisseur = """
            SELECT
                aml.product_id,
                EXTRACT(YEAR FROM am.invoice_date)::int AS annee,
                COALESCE(SUM(
                    CASE WHEN am.move_type = 'in_invoice' THEN aml.price_subtotal
                         WHEN am.move_type = 'in_refund'  THEN -aml.price_subtotal
                         ELSE 0 END
                ), 0) AS total
            FROM account_move_line aml
            JOIN account_move am ON aml.move_id = am.id
            WHERE am.state = 'posted'
              AND am.move_type IN ('in_invoice', 'in_refund')
              AND aml.product_id IS NOT NULL
              AND aml.exclude_from_invoice_tab = False
            GROUP BY aml.product_id, EXTRACT(YEAR FROM am.invoice_date)
        """
        cr.execute(sql_fournisseur)
        fournisseur_data = {}
        for row in cr.fetchall():
            key = (row[0], str(row[1]))
            fournisseur_data[key] = round(row[2], 2)

        # === Fusionner et créer les enregistrements ===
        all_keys = set(client_data.keys()) | set(fournisseur_data.keys())
        vals_list = []
        for key in all_keys:
            product_id, annee = key
            fc = client_data.get(key, 0.0)
            ff = fournisseur_data.get(key, 0.0)
            vals_list.append({
                'product_id': product_id,
                'annee': annee,
                'facturation_client': fc,
                'facturation_fournisseur': ff,
                'marge_brute_facturation': round(fc - ff, 2),
            })

        # Création par lot
        if vals_list:
            self.create(vals_list)

        _logger.info("Cron marge brute par article : %s lignes créées", len(vals_list))
        return True
