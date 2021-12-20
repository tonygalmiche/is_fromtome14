# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, tools
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from dateutil import relativedelta
from itertools import groupby
from operator import itemgetter
from datetime import datetime
from datetime import timedelta
from dateutil.parser import parse
import dateparser
import dateutil
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, pycompat


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def get_nb_colis(self):
        nb        = self.product_id.is_nb_pieces_par_colis
        poids_net = self.product_id.is_poids_net_colis
        unite     = self.product_uom_id.category_id.name
        nb_colis  = 0
        if unite=="Poids":
            if poids_net>0:
                nb_colis = self.qty_done/poids_net
        else:
            if nb>0:
                nb_colis = self.qty_done / nb
        return round(nb_colis)


    @api.onchange('product_id','qty_done')
    def _onchange_product_id_qty_done(self):
        for obj in self:
            nb_colis = obj.get_nb_colis()
            obj.is_nb_colis = nb_colis
            unite = self.product_uom_id.category_id.name
            if unite=="Poids":
                poids = obj.qty_done
            else:
                poids = nb_colis*obj.product_id.is_poids_net_colis
            obj.is_poids_net_reel = poids


    @api.depends('product_id','qty_done')
    def _compute_is_poids_net_estime(self):
        for obj in self:
            nb_colis = obj.get_nb_colis()
            obj.is_poids_net_estime = nb_colis * obj.product_id.is_poids_net_colis


    is_type_tracabilite    = fields.Selection(string='Traçabilité', related="product_id.is_type_tracabilite")
    is_dlc_ddm             = fields.Date('DLC / DDM', related="lot_id.is_dlc_ddm")
    status_move            = fields.Selection(string='Statut', selection=[('receptionne', 'Réceptionné'), ('manquant', 'Manquant'), ('abime', 'Abimé'), ('autre', 'Autre')], default='receptionne')
    is_nb_pieces_par_colis = fields.Integer(string='PCB', related="product_id.is_nb_pieces_par_colis")
    is_nb_colis            = fields.Float(string='Nb Colis', digits=(14,2))
    is_poids_net_estime    = fields.Float(string='Poids net estimé', digits='Stock Weight', compute='_compute_is_poids_net_estime', readonly=True, store=True, help="Poids net total (Kg)")
    is_poids_net_reel      = fields.Float(string='Poids net réel'  , digits='Stock Weight', help="Poids net réel total (Kg)")


    def stock_move_line_edit_action(self):
        for obj in self:
            dummy, view_id = self.env['ir.model.data'].get_object_reference('is_fromtome14', 'is_stock_move_line_edit')
            res= {
                'name'     : 'Modification du poids réél',
                'view_mode': 'form',
                'target'    : 'new',
                'res_id'   : obj.id,
                'res_model': 'stock.move.line',
                'type'     : 'ir.actions.act_window',
                'views'    : [[view_id, "form"]],
            }
            return res


