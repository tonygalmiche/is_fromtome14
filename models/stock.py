# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class StockProductionLot(models.Model):
    _inherit = "stock.production.lot"

    is_article_actif = fields.Boolean('Article actif', related='product_id.active')
    is_dlc_ddm       = fields.Date('DLC / DDM', required=True)

    # @api.constrains('name','product_id','is_dlc_ddm')
    # def _check_lot_unique(self):
    #     for obj in self:
    #         filtre=[
    #             ('name'      , '=' , obj.name),
    #             ('id'        , '!=', obj.id),
    #             ('product_id', '=' , obj.product_id.id),
    #             ('is_dlc_ddm', '=' , obj.is_dlc_ddm),
    #         ]
    #         lots = self.env['stock.production.lot'].search(filtre, limit=1)
    #         for lot in lots:
    #             print(lot.name)
    #         if lots:
    #             raise Warning("Ce lot existe déjà !") 



    @api.constrains('name', 'product_id', 'company_id', 'is_dlc_ddm')
    def _check_unique_lot(self):
        domain = [
            ('product_id', 'in', self.product_id.ids),
            ('company_id', 'in', self.company_id.ids),
            ('name', 'in', self.mapped('name')),
            ('is_dlc_ddm', 'in', self.mapped('is_dlc_ddm')),
        ]
        fields = ['company_id' , 'product_id', 'name', 'is_dlc_ddm']
        groupby = ['company_id', 'product_id', 'name', 'is_dlc_ddm']
        records = self.read_group(domain, fields, groupby, lazy=False)
        error_message_lines = []
        for rec in records:
            if rec['__count'] != 1:
                product_name = self.env['product.product'].browse(rec['product_id'][0]).display_name
                error_message_lines.append(_(" - Product: %s, Serial Number: %s", product_name, rec['name']))
        if error_message_lines:
            raise ValidationError(_('The combination of serial number and product must be unique across a company.\nFollowing combination contains duplicates:\n') + '\n'.join(error_message_lines))



    # @api.depends('product_id')
    # def compute_is_company_id(self):
    #     for obj in self:
    #         obj.is_company_id=obj.product_id.company_id.id


    # is_company_id = fields.Many2one('res.company', 'Société', compute=compute_is_company_id, store=True)
    active        = fields.Boolean("Actif", default=True)


    def archiver_lot_action_server(self):
        for obj in self:
            if obj.product_qty==0:
                obj.active=False

 

class StockMove(models.Model):
    _inherit = "stock.move"

    @api.onchange('move_line_ids')
    def _compute_is_alerte(self):
        for obj in self:
            if obj.picking_id:
                alerte=False
                state=obj.picking_id.state
                if state in ['draft', 'cancel', 'waiting', 'confirmed']:
                    alerte=False
                else:
                    if obj.picking_id.scheduled_date:
                        date=obj.picking_id.scheduled_date.date()
                        if state=='assigned' and date<datetime.now().date():
                            date=datetime.now().date()
                        alerte=[]
                        # for line in obj.move_line_ids:
                        #     date_due = line.life_use_date
                        #     if date_due and date_due.date() < date:
                        #         alerte.append("Le lot "+str(line.lot_id.name)+" de l'article "+str(obj.product_id.display_name)+" est expiré !")
                        #     if date_due and date_due.date() ==date:
                        #         alerte.append("Le lot "+str(line.lot_id.name)+" de l'article "+str(obj.product_id.display_name)+" expire aujourd'hui !")
                        if len(alerte)>0:
                            alerte='\n'.join(alerte)
                        else:
                            alerte=False
                obj.is_alerte=alerte


    @api.onchange('move_line_ids')
    def _compute_is_lots(self):
        for obj in self:
            lots={}
            for line in obj.move_line_ids:
                cle="%s-%s-%s"%(obj.product_id.id,line.lot_id.name,line.is_dlc_ddm)
                if cle not in lots:
                    dlc = (line.is_dlc_ddm and line.is_dlc_ddm.strftime('%d/%m/%Y')) or ''
                    lots[cle]=[(line.lot_id.name or ''),(line.is_type_tracabilite or '').upper(),dlc,0,0]
                lots[cle][3]+=line.qty_done
                lots[cle][4]+=line.is_nb_colis
            t=[]
            for lot in lots:
                l=lots[lot]
                #x="Lot:%s %s:%s Quant:%.2f Colis:%.1f"%(l[0],l[1],l[2],l[3],l[4])
                x="Lot:%s - %s:%s - Colis:%.1f"%(l[0],l[1],l[2],l[4])
                t.append(x)
            obj.is_lots = "\n".join(t)


    @api.onchange('move_line_ids')
    def _compute_is_nb_colis_poids(self):
        for obj in self:
            nb=0
            poids=0
            for line in obj.move_line_ids:
                nb+=line.is_nb_colis
                poids+=line.is_poids_net_reel
            obj.is_nb_colis       = nb
            obj.is_poids_net_reel = poids
 

    is_alerte         = fields.Text('Alerte', copy=False, compute=_compute_is_alerte)
    is_lots           = fields.Text('Lots'  , copy=False, compute=_compute_is_lots)
    is_nb_colis       = fields.Float('Nb Colis'      , digits=(14,2), compute=_compute_is_nb_colis_poids)
    is_poids_net_reel = fields.Float('Poids net réel', digits=(14,4), compute=_compute_is_nb_colis_poids)


    def get_nb_colis(self):
        nb        = self.product_id.is_nb_pieces_par_colis
        poids_net = self.product_id.is_poids_net_colis
        unite     = self.product_uom.category_id.name
        nb_colis  = 0
        if unite=="Poids":
            if poids_net>0:
                nb_colis = self.product_uom_qty/poids_net
        else:
            if nb>0:
                nb_colis = self.product_uom_qty / nb
        return round(nb_colis)


