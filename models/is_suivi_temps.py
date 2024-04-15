# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import date


class IsMotifAbsence(models.Model):
    _name = 'is.motif.absence'
    _description = "Motif d'absence"
    _order = 'name'

    name   = fields.Char("Motif d'absence", required=True)
    active = fields.Boolean("Actif", default=True)


class IsSuiviTemps(models.Model):
    _name = 'is.suivi.temps'
    _description = "Suivi du temps par employé"
    _order = 'date desc'
    _rec_name = 'date'


    date             = fields.Date("Date", required=True, default=lambda *a: fields.Date.today())
    employe_id       = fields.Many2one('hr.employee', 'Employé', required=True, default=lambda self: self.get_employe())
    nb_heures        = fields.Float("Heures effectuées")
    motif_absence_id = fields.Many2one('is.motif.absence', "Motif d'absence")
    commentaire      = fields.Text('Commentaire')


    def get_employe(self):
        employe_id=False
        user_id = self.env.user.id
        employes = self.env['hr.employee'].search([('user_id','=',user_id)])
        for employe in employes:
            employe_id = employe.id
        return employe_id