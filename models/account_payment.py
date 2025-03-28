# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from datetime import date,timedelta
from calendar import monthrange
 

class AccountPaymentOrder(models.Model):
    _inherit = 'account.payment.order'

    #Champ créé uniquement pour pouvoir faire un PDF
    partner_id          = fields.Many2one('res.partner','Partenaire', related='generated_user_id.partner_id')
    is_export_compta_id = fields.Many2one('is.export.compta', 'Folio', copy=False)


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    def compute(self, value, date_ref=False, currency=None):
        self.ensure_one()
        date_ref = date_ref or fields.Date.context_today(self)
        amount = value
        sign = value < 0 and -1 or 1
        result = []
        if not currency and self.env.context.get('currency_id'):
            currency = self.env['res.currency'].browse(self.env.context['currency_id'])
        elif not currency:
            currency = self.env.company.currency_id
        for line in self.line_ids:
            if line.value == 'fixed':
                amt = sign * currency.round(line.value_amount)
            elif line.value == 'percent':
                amt = currency.round(value * (line.value_amount / 100.0))
            elif line.value == 'balance':
                amt = currency.round(amount)
            next_date = fields.Date.from_string(date_ref)
            if line.option == 'day_after_invoice_date':
                next_date += relativedelta(days=line.days)
                if line.day_of_the_month > 0:
                    months_delta = (line.day_of_the_month < next_date.day) and 1 or 0
                    next_date += relativedelta(day=line.day_of_the_month, months=months_delta)
            elif line.option == 'after_invoice_month':
                next_first_date = next_date + relativedelta(day=1, months=1)  # Getting 1st of next month
                next_date = next_first_date + relativedelta(days=line.days - 1)
            elif line.option == 'day_following_month':
                next_date += relativedelta(day=line.days, months=1)
            elif line.option == 'day_current_month':
                next_date += relativedelta(day=line.days, months=0)

            #** Ajout option 'fin_de_decade' le 22:03/2024 ********************
            elif line.option == 'fin_de_decade':
                next_date += timedelta(days=line.days)
                if next_date.day>=1 and next_date.day<=10:
                    delta = 10 - next_date.day
                    next_date += timedelta(days=delta)

                if next_date.day>=11 and next_date.day<=20:
                    delta = 20 - next_date.day
                    next_date += timedelta(days=delta)

                if next_date.day>=21 and next_date.day<=31:
                    nb_jours_dans_mois = monthrange(next_date.year, next_date.month)[1]
                    delta = nb_jours_dans_mois - next_date.day
                    next_date += timedelta(days=delta)
            #******************************************************************

            result.append((fields.Date.to_string(next_date), amt))
            amount -= amt
        amount = sum(amt for _, amt in result)
        dist = currency.round(value - amount)
        if dist:
            last_date = result and result[-1][0] or fields.Date.context_today(self)
            result.append((last_date, dist))
        res = sorted(result, key=lambda k: k[0])
        return res


class AccountPaymentTermLine(models.Model):
    _inherit = "account.payment.term.line"

    option = fields.Selection(selection_add=[
        ("fin_de_decade", "Fin de décade"),
    ], ondelete={'fin_de_decade': 'set default'})


    # option = fields.Selection([
    #         ('day_after_invoice_date', "days after the invoice date"),
    #         ('after_invoice_month', "days after the end of the invoice month"),
    #         ('day_following_month', "of the following month"),
    #         ('day_current_month', "of the current month"),
    #     ],
    #     default='day_after_invoice_date', required=True, string='Options'
    #     )


