# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _


class StockInventory(models.Model):
    _inherit = "stock.inventory"


    # def valorisation_stock_action(self):
    #     for obj in self:
    #         dummy, tree_view_id = self.env['ir.model.data'].get_object_reference('is_fromtome14', 'is_stock_inventory_line_tree')
    #         dummy, form_view_id = self.env['ir.model.data'].get_object_reference('is_fromtome14', 'is_stock_inventory_line_form')
#             res = {
#                 'name': 'Stock valorisé '+obj.name,
#                 'view_mode': 'tree,form',
#                 'view_type': 'form',
# #                'views': [[tree_view_id, "tree"], [form_view_id, "form"]],
#                 'res_model': 'stock.inventory.line',
#                 # 'domain': [
#                 #      ('inventory_id','=',obj.id)
#                 # ],
#                 'type': 'ir.actions.act_window',
#                 #'limit':1000,
#             }
#             print(res)
#             return res


    def valorisation_stock_action(self):
        dummy, tree_view_id = self.env['ir.model.data'].get_object_reference('is_fromtome14', 'is_stock_inventory_line_tree')
        dummy, form_view_id = self.env['ir.model.data'].get_object_reference('is_fromtome14', 'is_stock_inventory_line_form')
        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'name': _('Inventory Lines'),
            'res_model': 'stock.inventory.line',
            #'views': [[tree_view_id, "tree"], [form_view_id, "form"]],
            #'view_id' : self.env.ref('stock.stock_inventory_line_tree').id,
            'view_id' : self.env.ref('is_fromtome14.is_stock_inventory_line_tree').id,
        }
        context = {
            'default_is_editable': True,
            'default_inventory_id': self.id,
            'default_company_id': self.company_id.id,
        }
        domain = [
            ('inventory_id', '=', self.id),
            ('location_id.usage', 'in', ['internal', 'transit'])
        ]
        if self.location_ids:
            context['default_location_id'] = self.location_ids[0].id
            if len(self.location_ids) == 1:
                if not self.location_ids[0].child_ids:
                    context['readonly_location_id'] = True
        action['context'] = context
        action['domain'] = domain
        return action








class StockInventoryLine(models.Model):
    _inherit = "stock.inventory.line"


    @api.depends('product_id')
    def compute_is_dernier_prix(self):
        cr,uid,context,su = self.env.args
        sale_qty = 0
        for obj in self:
            SQL="""
                SELECT ail.price_unit,ail.product_uom_id
                FROM account_move_line ail inner join account_move ai on ail.move_id=ai.id
                WHERE ail.product_id=%s  and ai.state='posted' and ai.move_type='in_invoice'
                ORDER BY ail.id desc
                limit 1
            """
            cr.execute(SQL,[obj.product_id.id])
            prix=0
            uom_id = obj.product_uom_id.id
            for row in cr.fetchall():
                print(row)
                prix = row[0]
                uom_id=row[1]
            obj.is_dernier_prix   = prix
            obj.is_stock_valorise = prix*obj.product_qty
            obj.is_uom_facture_id = uom_id


    is_default_code    = fields.Char('Référence interne'           , related='product_id.default_code')
    is_product_name    = fields.Char('Désignation article'         , related='product_id.name')
    is_dernier_prix    = fields.Float("Dernier prix facturé"       , compute=compute_is_dernier_prix, store=False)
    is_stock_valorise  = fields.Float("Stock valorisé"             , compute=compute_is_dernier_prix, store=False)
    is_uom_facture_id  = fields.Many2one('uom.uom', 'Unité facture', compute=compute_is_dernier_prix, store=False)




#TODO : A revoir


# class InventoryLine(models.Model):
#     _inherit = "stock.inventory.line"
#     _order = ""

#     life_use_date = fields.Datetime('DLC / DDM')


#     @api.onchange('prod_lot_id')
#     def onchage_life_use_date_lot(self):
#         if self.prod_lot_id and not self.life_use_date:
#             if self.prod_lot_id.use_date:
#                 self.life_use_date = self.prod_lot_id.use_date
#             elif self.prod_lot_id.life_date:
#                 self.life_use_date = self.prod_lot_id.life_date
