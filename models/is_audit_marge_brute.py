# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta, date

import logging
_logger = logging.getLogger(__name__)


class IsAuditMargeBrute(models.Model):
    _name = 'is.audit.marge.brute'
    _description = "Audit marge brute"
    _order = 'semaine desc'
    _rec_name = 'semaine'

    semaine = fields.Char('Semaine', required=True, readonly=True, help="Format AAAA-Sxx (ex: 2026-S10)")
    champ_date = fields.Selection([
        ('date', 'Date comptable'),
        ('invoice_date', 'Date de facturation'),
    ], string='Date', default='invoice_date', required=True, readonly=False, help="Champ date utilisé pour les requêtes")

    facturation_client       = fields.Float("Facturation client", readonly=True, help="Total HT des factures et avoirs des clients")
    facturation_fournisseur  = fields.Float("Facturation fournisseur", readonly=True, help="Total HT des factures et avoirs des fournisseurs")
    marge_brute_facturation  = fields.Float("Marge brute facturation", readonly=True, help="Facturation client - Facturation fournisseur")

    analyse_facturation_client       = fields.Float("Analyse facturation client", readonly=True, help="Total du champ Montant HT dans Analyse facturation des factures et avoirs des clients")
    analyse_facturation_fournisseur  = fields.Float("Analyse facturation fournisseur", readonly=True, help="Total du champ Montant achat avec remise dans Analyse facturation des factures et avoirs des clients")
    marge_brute_analyse_facturation  = fields.Float("Marge brute analyse facturation", readonly=True, help="Analyse facturation client - Analyse facturation fournisseur")

    ecart_facturation_client       = fields.Float("Écart facturation client", readonly=True)
    ecart_facturation_fournisseur  = fields.Float("Écart facturation fournisseur", readonly=True)
    ecart_marge_brute              = fields.Float("Écart marge brute", readonly=True)

    date_lundi = fields.Date('Lundi', compute='_compute_date_lundi', store=True, readonly=True)
    annee      = fields.Char('Année', compute='_compute_date_lundi', store=True, readonly=True)
    annee_comptable = fields.Char('Année comptable', compute='_compute_date_lundi', store=True, readonly=True)

    @api.depends('semaine')
    def _compute_date_lundi(self):
        for rec in self:
            if rec.semaine:
                try:
                    parts = rec.semaine.upper().replace(' ', '').split('-S')
                    year = int(parts[0])
                    week = int(parts[1])
                    monday = datetime.strptime(f'{year}-W{week:02d}-1', '%G-W%V-%u').date()
                    rec.date_lundi = monday
                    rec.annee = str(year)
                    # Exercice comptable du 1er juillet N au 30 juin N+1 => année comptable = N
                    if monday.month >= 7:
                        rec.annee_comptable = str(monday.year)
                    else:
                        rec.annee_comptable = str(monday.year - 1)
                except (ValueError, IndexError):
                    rec.date_lundi = False
                    rec.annee = False
                    rec.annee_comptable = False
            else:
                rec.date_lundi = False
                rec.annee = False
                rec.annee_comptable = False

    def _get_dates_from_semaine(self):
        """Convertit le champ semaine (AAAA-Sxx) en dates début (lundi) et fin (dimanche)"""
        self.ensure_one()
        if not self.semaine:
            raise UserError(_("Le champ Semaine doit être renseigné."))
        try:
            parts = self.semaine.upper().replace(' ', '').split('-S')
            year = int(parts[0])
            week = int(parts[1])
        except (ValueError, IndexError):
            raise UserError(_("Le format de la semaine doit être AAAA-Sxx (ex: 2026-S10)."))
        try:
            monday = datetime.strptime(f'{year}-W{week:02d}-1', '%G-W%V-%u').date()
        except ValueError:
            raise UserError(_("Semaine invalide : %s") % self.semaine)
        sunday = monday + timedelta(days=6)
        return monday, sunday

    def action_actualiser(self):
        """Bouton Actualiser : recalcule via sudo pour contourner les droits en lecture seule"""
        self.sudo().action_calculer()

    def action_recalculer_analyse_facturation(self):
        """Lance la mise à jour de l'analyse facturation sur la semaine puis recalcule l'audit"""
        for rec in self:
            date_debut, date_fin = rec._get_dates_from_semaine()
            self.env['is.analyse.facturation.update'].sudo().update(date_debut, date_fin)
        self.sudo().action_calculer()

    def action_calculer(self):
        """Calcule tous les champs à partir du champ Semaine"""
        for rec in self:
            date_debut, date_fin = rec._get_dates_from_semaine()
            cr = self.env.cr
            champ_date = rec.champ_date or 'date'

            # === Facturation client (account.move) ===
            sql = """
                SELECT COALESCE(SUM(
                    CASE WHEN move_type = 'out_invoice' THEN amount_untaxed
                         WHEN move_type = 'out_refund'  THEN -amount_untaxed
                         ELSE 0 END
                ), 0)
                FROM account_move
                WHERE state = 'posted'
                  AND {date_col} >= %s AND {date_col} <= %s
                  AND move_type IN ('out_invoice', 'out_refund')
            """.format(date_col=champ_date)
            cr.execute(sql, [date_debut, date_fin])
            facturation_client = cr.fetchone()[0]

            # === Facturation fournisseur (account.move) ===
            sql = """
                SELECT COALESCE(SUM(
                    CASE WHEN move_type = 'in_invoice' THEN amount_untaxed
                         WHEN move_type = 'in_refund'  THEN -amount_untaxed
                         ELSE 0 END
                ), 0)
                FROM account_move
                WHERE state = 'posted'
                  AND {date_col} >= %s AND {date_col} <= %s
                  AND move_type IN ('in_invoice', 'in_refund')
            """.format(date_col=champ_date)
            cr.execute(sql, [date_debut, date_fin])
            facturation_fournisseur = cr.fetchone()[0]

            # === Analyse facturation client (is.analyse.facturation) ===
            if champ_date == 'invoice_date':
                sql = """
                    SELECT COALESCE(SUM(price_subtotal), 0)
                    FROM is_analyse_facturation
                    WHERE invoice_date >= %s AND invoice_date <= %s
                      AND move_type IN ('Facture client', 'Avoir client')
                """
                cr.execute(sql, [date_debut, date_fin])
            else:
                sql = """
                    SELECT COALESCE(SUM(iaf.price_subtotal), 0)
                    FROM is_analyse_facturation iaf
                    LEFT JOIN account_move am ON iaf.invoice_id = am.id
                    WHERE am.date >= %s AND am.date <= %s
                      AND iaf.move_type IN ('Facture client', 'Avoir client')
                """
                cr.execute(sql, [date_debut, date_fin])
            analyse_facturation_client = cr.fetchone()[0]

            # === Analyse facturation fournisseur (is.analyse.facturation) ===
            # Total du champ montant_achat_avec_remise pour les factures et avoirs clients uniquement
            if champ_date == 'invoice_date':
                sql = """
                    SELECT COALESCE(SUM(montant_achat_avec_remise), 0)
                    FROM is_analyse_facturation
                    WHERE invoice_date >= %s AND invoice_date <= %s
                      AND move_type IN ('Facture client', 'Avoir client')
                """
                cr.execute(sql, [date_debut, date_fin])
            else:
                sql = """
                    SELECT COALESCE(SUM(iaf.montant_achat_avec_remise), 0)
                    FROM is_analyse_facturation iaf
                    LEFT JOIN account_move am ON iaf.invoice_id = am.id
                    WHERE am.date >= %s AND am.date <= %s
                      AND iaf.move_type IN ('Facture client', 'Avoir client')
                """
                cr.execute(sql, [date_debut, date_fin])
            analyse_facturation_fournisseur = cr.fetchone()[0]

            # === Calculs dérivés ===
            marge_brute_facturation = round(facturation_client - facturation_fournisseur, 2)
            marge_brute_analyse_facturation = round(analyse_facturation_client - analyse_facturation_fournisseur, 2)

            ecart_facturation_client = round(facturation_client - analyse_facturation_client, 2)
            ecart_facturation_fournisseur = round(facturation_fournisseur - analyse_facturation_fournisseur, 2)
            ecart_marge_brute = round(marge_brute_facturation - marge_brute_analyse_facturation, 2)

            rec.write({
                'facturation_client': round(facturation_client, 2),
                'facturation_fournisseur': round(facturation_fournisseur, 2),
                'marge_brute_facturation': marge_brute_facturation,
                'analyse_facturation_client': round(analyse_facturation_client, 2),
                'analyse_facturation_fournisseur': round(analyse_facturation_fournisseur, 2),
                'marge_brute_analyse_facturation': marge_brute_analyse_facturation,
                'ecart_facturation_client': ecart_facturation_client,
                'ecart_facturation_fournisseur': ecart_facturation_fournisseur,
                'ecart_marge_brute': ecart_marge_brute,
            })

    def action_voir_facturation_client(self):
        """Ouvre les factures et avoirs clients de la semaine"""
        self.ensure_one()
        date_debut, date_fin = self._get_dates_from_semaine()
        champ_date = self.champ_date or 'date'
        return {
            'name': 'Facturation client - %s' % self.semaine,
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form,pivot,graph',
            'domain': [
                ('state', '=', 'posted'),
                (champ_date, '>=', str(date_debut)),
                (champ_date, '<=', str(date_fin)),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
            ],
        }

    def action_voir_facturation_fournisseur(self):
        """Ouvre les factures et avoirs fournisseurs de la semaine"""
        self.ensure_one()
        date_debut, date_fin = self._get_dates_from_semaine()
        champ_date = self.champ_date or 'date'
        return {
            'name': 'Facturation fournisseur - %s' % self.semaine,
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form,pivot,graph',
            'domain': [
                ('state', '=', 'posted'),
                (champ_date, '>=', str(date_debut)),
                (champ_date, '<=', str(date_fin)),
                ('move_type', 'in', ['in_invoice', 'in_refund']),
            ],
        }

    def action_voir_analyse_facturation_client(self):
        """Ouvre les lignes d'analyse facturation client de la semaine"""
        self.ensure_one()
        date_debut, date_fin = self._get_dates_from_semaine()
        champ_date = self.champ_date or 'date'
        if champ_date == 'invoice_date':
            domain = [
                ('invoice_date', '>=', str(date_debut)),
                ('invoice_date', '<=', str(date_fin)),
                ('move_type', 'in', ['Facture client', 'Avoir client']),
            ]
        else:
            domain = [
                ('invoice_id.date', '>=', str(date_debut)),
                ('invoice_id.date', '<=', str(date_fin)),
                ('move_type', 'in', ['Facture client', 'Avoir client']),
            ]
        return {
            'name': 'Analyse facturation client - %s' % self.semaine,
            'type': 'ir.actions.act_window',
            'res_model': 'is.analyse.facturation',
            'view_mode': 'tree,form,pivot,graph',
            'domain': domain,
        }

    @api.model
    def _cron_audit_marge_brute(self):
        """Tâche planifiée : crée et actualise toutes les semaines depuis le début de la facturation"""
        # Changer ici la date utilisée pour toutes les fiches : 
        # 'date' (Date comptable) ou 'invoice_date' (Date de facturation)
        champ_date = 'invoice_date'
        cr = self.env.cr
        # Trouver la date la plus ancienne de facturation
        cr.execute("SELECT MIN(date) FROM account_move WHERE state = 'posted' AND date IS NOT NULL")
        row = cr.fetchone()
        if not row or not row[0]:
            return True
        date_min = row[0]
        # Déterminer la semaine ISO de début et la semaine courante
        today = date.today()
        iso_min = date_min.isocalendar()
        iso_now = today.isocalendar()
        # Générer toutes les semaines de iso_min à iso_now
        current = date_min - timedelta(days=date_min.weekday())  # Lundi de la semaine de début
        end = today
        semaines = []
        while current <= end:
            iso = current.isocalendar()
            semaine = '%s-S%02d' % (iso[0], iso[1])
            semaines.append(semaine)
            current += timedelta(days=7)
        # Créer les semaines manquantes et actualiser toutes
        existing = self.search([('semaine', 'in', semaines)])
        existing_map = {r.semaine: r for r in existing}
        for sem in semaines:
            if sem not in existing_map:
                existing_map[sem] = self.create({'semaine': sem, 'champ_date': champ_date})
        # Mettre à jour le champ_date de toutes les fiches
        all_records = self.search([('semaine', 'in', semaines)])
        all_records.write({'champ_date': champ_date})
        # Actualiser toutes les fiches
        all_records.action_calculer()
        _logger.info("Cron audit marge brute : %s semaines traitées (champ_date=%s)", len(semaines), champ_date)
        return True
