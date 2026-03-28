# -*- coding: utf-8 -*-
from odoo import models, fields, api


class IsPromptIa(models.Model):
    _name = "is.prompt.ia"
    _description = "Prompt IA"
    _order = "modele_id, id"

    modele_id = fields.Many2one("ir.model", string="Modèle", required=True, ondelete="cascade")
    field_id  = fields.Many2one("ir.model.fields", string="Champ")
    prompt    = fields.Text(string="Prompt")
    active    = fields.Boolean(string="Actif", default=True)

    @api.onchange("modele_id")
    def _onchange_modele_id(self):
        self.field_id = False
        if self.modele_id:
            return {
                "domain": {
                    "field_id": [
                        ("model_id", "=", self.modele_id.id),
                        ("ttype", "not in", ["one2many", "reference", "binary", "serialized"]),
                        ("store", "=", True),
                    ]
                }
            }
        return {
            "domain": {
                "field_id": []
            }
        }
