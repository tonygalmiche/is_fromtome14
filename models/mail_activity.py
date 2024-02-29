# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _


class MailActivity(models.Model):
    _inherit = 'mail.activity'
 

    active      = fields.Boolean("Actif", default=True)
    partner_id  = fields.Many2one('res.partner','Partenaire', compute='_compute_partner_id', readonly=True, store=True)
    is_customer = fields.Boolean("Est un Client"            , compute='_compute', readonly=True, store=True)
    is_supplier = fields.Boolean("Est un Fournisseur"       , compute='_compute', readonly=True, store=True)
    is_attachment_ids = fields.Many2many('ir.attachment', 'mail_activity_is_attachment_ids_rel', 'activity_id', 'file_id', 'Pièce jointe')


    @api.depends('partner_id','partner_id.is_customer','partner_id.is_supplier')
    def _compute(self):
        for obj in self:
            is_customer = obj.is_customer
            is_supplier = obj.is_supplier
            if obj.partner_id:
                is_customer = obj.partner_id.is_customer
                is_supplier = obj.partner_id.is_supplier
            obj.is_customer = is_customer
            obj.is_supplier = is_supplier


    @api.depends('res_model','res_id')
    def _compute_partner_id(self):
        for obj in self:

            partner_id= False

            # try:
            #     print(obj) #,obj.res_model,obj.res_id)
            #     partner_id=False
            # except ValueError:
            #     partner_id=False



            p=False
            if obj.res_model=='res.partner':
                partners=self.env['res.partner'].search([('id','=',obj.res_id)])
                for partner in partners:
                    p = partner
            if obj.res_model=='stock.picking':
                pickings=self.env['stock.picking'].search([('id','=',obj.res_id)])
                for picking in pickings:
                    p = picking.partner_id
            if obj.res_model=='sale.order':
                orders=self.env['sale.order'].search([('id','=',obj.res_id)])
                for order in orders:
                    p = order.partner_id
            if obj.res_model=='account.move':
                orders=self.env['account.move'].search([('id','=',obj.res_id)])
                for order in orders:
                    p = order.partner_id
            if p:
                partner_id=p.id

            print(obj,obj.res_model,obj.res_id,partner_id)



            obj.partner_id = partner_id
            


    # def write(self, vals):
    #     print(self,vals)
    #     return super(MailActivity, self).write(vals)



    def unlink(self):
        self.active=False
        return True


