
# -*- coding: utf-8 -*-
from odoo import api, fields, tools, models,_
from odoo.tools import float_is_zero, pycompat
from odoo.tools.float_utils import float_round
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError


_TRAITEMENT_THERMIQUE = [('laitcru', 'Lait Cru'), ('laitthermise', 'Lait Thermise'), ('laitpasteurisé', 'Lait Pasteurise')]


class MilkType(models.Model):
    _name="milk.type"
    _description = "Type de lait"
    name=fields.Char('Nom')
    logo=fields.Binary('Logo')
    description=fields.Text('Desciption')


class ProductLabelCategory(models.Model):
    _name="product.label.category"
    _description = "ProductLabelCategory"
    name=fields.Char('Categorie')
    note = fields.Text('Note')


class ProductLabel(models.Model):
    _name="product.label"
    _description = "ProductLabel"
    name=fields.Char('Nom du Label')
    libelle=fields.Char('Libelle Label')
    logo_label = fields.Binary('Logo')
    category_id = fields.Many2one('product.label.category','Categorie')


class MoisFromage(models.Model):
    _name = "mois.fromage"
    _description = "MoisFromage"
    name = fields.Char('Mois')


class ContratDateClient(models.Model):
    _name = 'contrat.date.client'
    _description = "ContratDateClient"
    name = fields.Integer('Contrat Date')
    partner_id = fields.Many2one('res.partner','Client')  #,domain="[('customer','=',True)]")
    product_id = fields.Many2one('product.template','Produit')


class IsRegionOrigine(models.Model):
    _name = "is.region.origine"
    _description = "Région d'origine"
    _order = "name"
    name = fields.Char("Région d'origine")


class IsFamilleFromage(models.Model):
    _name = "is.famille.fromage"
    _description = "Famille de fromage"
    _order = "name"
    name = fields.Char("Région d'origine")


class IsIngredient(models.Model):
    _name = "is.ingredient"
    _description = "Ingrédients"
    _order = "name"
    name = fields.Char("Ingrédient", required=True)
    active = fields.Boolean("Actif", default=True)


class IsIngredientLine(models.Model):
    _name = "is.ingredient.line"
    _description = "Ingrédients des articles"
    _order = "ordre"

    product_id     = fields.Many2one('product.template', "Article", required=True, ondelete='cascade', readonly=True)
    ingredient_id  = fields.Many2one('is.ingredient', 'Ingrédient', required=True)
    allergene      = fields.Boolean('Allergène')
    ordre          = fields.Integer('Ordre')


class IsGerme(models.Model):
    _name = "is.germe"
    _description = "Germe"
    _order = "ordre"

    name   = fields.Char("Germe", required=True)
    active = fields.Boolean("Actif", default=True)
    ordre  = fields.Integer('Ordre')


class IsGermeLine(models.Model):
    _name = "is.germe.line"
    _description = "Germes des articles"
    _order = "ordre"

    product_id     = fields.Many2one('product.template', "Article", required=True, ondelete='cascade', readonly=True)
    germe_id       = fields.Many2one('is.germe', 'Germe', required=True)
    critere         = fields.Char('Critère REG EU 2073')
    ordre          = fields.Integer('Ordre')


class IsValeurNutritionnelle(models.Model):
    _name = "is.valeur.nutritionnelle"
    _description = "Valeur Nutritionnelle"
    _order = "ordre"

    name   = fields.Char("Valeur Nutritionnelle", required=True)
    active = fields.Boolean("Active", default=True)
    ordre  = fields.Integer('Ordre')


class IsValeurNutritionnelleLine(models.Model):
    _name = "is.valeur.nutritionnelle.line"
    _description = "Valeur Nutritionnelle des articles"
    _order = "ordre"

    product_id     = fields.Many2one('product.template', "Article", required=True, ondelete='cascade', readonly=True)
    valeur_id      = fields.Many2one('is.valeur.nutritionnelle', 'Valeur Nutritionnelle ', required=True)
    valeur         = fields.Char('Valeur')
    ordre          = fields.Integer('Ordre')


class IsBio(models.Model):
    _name = "is.bio"
    _description = "BIO"
    _order = "name"
    name = fields.Char("Bio", required=True)


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'barcodes.barcode_events_mixin']



    # def name_get(self):
    #     self.browse(self.ids).read(['name', 'default_code'])
    #     return [(template.id, '%s%s' % (template.default_code and '[%s] ' % template.default_code or '', template.name))
    #             for template in self]




    def on_barcode_scanned(self, barcode):
        for obj in self:
            code   = str(barcode)[2:]
            prefix = str(barcode)[:2]
            if prefix in ("01","02"):
                obj.barcode = code


    @api.onchange('default_code')
    def default_code_uniq(self):
        list = []
        if self.default_code or self._origin.default_code:
            default_code_list = self.env['product.template'].search([('default_code', '=', self.default_code)])
            if default_code_list:
                for l in default_code_list:
                    list.append(l.id)
            if len(list)>=1:
                    raise UserError(_('La reference interne de doit etre unique !'))


    @api.depends('milk_type_ids')
    def _compute_milk_type(self):
        for obj in self:
            res=[]
            for line in obj.milk_type_ids:
                res.append(line.name)
            obj.milk_type = ', '.join(res)


    @api.depends('is_ingredient_ids')
    def _compute_is_ingredient(self):
        for obj in self:
            res=[]
            for line in obj.is_ingredient_ids:
                x=line.ingredient_id.name
                if line.allergene:
                    x="<b>"+x+"</b>"
                res.append(x)
            obj.is_ingredient = ', '.join(res)


    @api.onchange('is_nb_pieces_par_colis','is_poids_net_colis')
    def onchange_is_poids_net_colis(self):
        for obj in self:
            obj.weight = obj.is_poids_net_colis / (obj.is_nb_pieces_par_colis or 1)
 

    @api.depends('seller_ids')
    def _compute_is_ref_fournisseur(self):
        for obj in self:
            filtre=[
                ('product_tmpl_id', '=', obj.id),
            ]
            ref=False
            suppliers=self.env['product.supplierinfo'].search(filtre,limit=1)
            for s in suppliers:
                ref=s.product_code
            obj.is_ref_fournisseur = ref


    is_ref_fournisseur = fields.Char(string='Réf fournisseur', compute='_compute_is_ref_fournisseur', readonly=True, store=True)

    contrat_date_id = fields.One2many('contrat.date.client','product_id','Contrat Date')

    # Présentation / Conseils
    is_enseigne_id   = fields.Many2one('is.enseigne.commerciale', 'Enseigne', help="Enseigne commerciale")
    is_creation_le   = fields.Date(string='Création le', default=lambda *a: fields.Date.today())
    is_mis_a_jour_le = fields.Date(string='Mise à jour le')
    is_mise_en_avant = fields.Boolean(string='Mise en avant', help="Mise en avant de cet article dans le listing client", default=False)
    is_bio_id   = fields.Many2one('is.bio', 'BIO')
    #is_bio           = fields.Boolean(string='BIO', help="Article issue de l'agriculture biologique", default=False)
    is_preco         = fields.Boolean(string='Préco.', default=False)
    is_presentation = fields.Text(string='Présentation')
    is_conseils     = fields.Text(string='Conseils')


    # CARACTÉRISTIQUES GÉNÉRALES DU PRODUIT:
    is_region_id          = fields.Many2one('is.region.origine', string="Region d'origine")
    milk_type_ids         = fields.Many2many('milk.type','product_milk_type_rel','product_id','milk_type_id', string='Type de Lait')
    milk_type             = fields.Char(string='Types de Lait', compute='_compute_milk_type')
    traitement_thermique  = fields.Selection(string='Traitement Thermique', selection=_TRAITEMENT_THERMIQUE)
    is_famille_fromage_id = fields.Many2one('is.famille.fromage', string="Famille de fromage")
    duree_affinage        = fields.Char(string="Durée d'affinage")
    is_croute_comestible  = fields.Char(string="Croûte comestible")

    is_type_tracabilite       = fields.Selection(string='Traçabilité', selection=[('ddm', 'DDM'), ('dlc', 'DLC')], default='dlc')
    is_dluo                   = fields.Char(string='DDM/DLC')
    is_type_conditionnement   = fields.Char(string='Type de conditionnement')
    is_atelier_transformation = fields.Char(string='Atelier de transformation')
    no_agrement_sanitaire     = fields.Char(string="N° d'agrément fabriquant")
    temperature_stock         = fields.Char(string='T° de conservation')


    # CARACTÉRISTIQUES ORGANOLEPTIQUES:
    is_forme   = fields.Char(string='Forme')
    is_couleur = fields.Char(string='Couleur')
    texture    = fields.Char(string='Texture')

    degustation = fields.Char(string='Goût / Dégustation')
    odeur       = fields.Char(string='Odeur')

    is_ingredient_ids = fields.One2many('is.ingredient.line', 'product_id', "Lignes", copy=True)
    is_ingredient     = fields.Char(string='Ingrédients', compute='_compute_is_ingredient')

    is_germe_ids                 = fields.One2many('is.germe.line'                , 'product_id', "Germes" , copy=True)
    is_valeur_nutritionnelle_ids = fields.One2many('is.valeur.nutritionnelle.line', 'product_id', "Valeurs", copy=True)

    product_label_ids = fields.Many2many('product.label','product_label_rel','product_id','label_id', string='Labels')
    mode_vente        = fields.Selection(selection=[('colis', 'Colis'),('piece', 'Pièce'),('decoupe', 'Découpe')], string="Mode Vente")
    douane            = fields.Char(string='Nomenclature Douane')

    is_stock_mini         = fields.Float("Stock mini", digits=(14,4))
    is_pricelist_item_ids = fields.One2many('product.pricelist.item', 'product_tmpl_id', 'Liste de prix')

    is_nb_pieces_par_colis = fields.Integer(string='Nb Pièces / colis')
    is_poids_net_colis     = fields.Float(string='Poids net colis (Kg)', digits='Stock Weight')
    is_forcer_poids_colis  = fields.Boolean(string='Forcer le scan au poids du colis', default=False, help="Cocher cette case si l'article est configuré par erreur au poids alors qu'il fallait le configuer à la pièce")

    is_note_importation = fields.Text(string='Note importation Fusion Fromtome / Le Cellier')


    def init_emplacement_inventaire_action(self):
        for obj in self:
            if not obj.property_stock_inventory:
                obj.property_stock_inventory = 14





#TODO : Toute la partie ci-dessous sera a revoir dans un deuxième temps

#     default_code = fields.Char(
#         'Internal Reference', compute='_compute_default_code',
#         inverse='_set_default_code', store=True, required=False)


    def recharger_germes_action(self):
        for obj in self:
            res = []
            self.is_germe_ids = False
            lines = self.env['is.germe'].search([('active', '=', True)])
            ordre=0
            for line in lines:
                ordre+=10
                res.append((0, 0, {
                    'germe_id': line.id,
                    'ordre': ordre,
                }))
            self.is_germe_ids = res


    def recharger_valeurs_action(self):
        for obj in self:
            res = []
            self.is_valeur_nutritionnelle_ids = False
            lines = self.env['is.valeur.nutritionnelle'].search([('active', '=', True)])
            ordre=0
            for line in lines:
                ordre+=10
                res.append((0, 0, {
                    'valeur_id': line.id,
                    'ordre': ordre,
                }))
            self.is_valeur_nutritionnelle_ids = res


#     def _get_makebuy_route(self):
#         buy_route = self.env.ref('purchase_stock.route_warehouse0_buy', raise_if_not_found=False)
#         if buy_route:
#             buy_route+=(self.env.ref('stock.route_warehouse0_mto'))
#             products = self.env['product.template'].browse(self.env.context.get('active_ids'))
#             for s in products:
#                 s.route_ids = buy_route.ids

#     @api.model
#     def _get_buy_route(self):
#         buy_route = self.env.ref('purchase_stock.route_warehouse0_buy', raise_if_not_found=False)
#         if buy_route:
#             buy_route += (self.env.ref('stock.route_warehouse0_mto'))
#             return buy_route.ids
#         return []

#     route_ids = fields.Many2many(default=lambda self: self._get_buy_route())


#     def ts_mois_fromage(self):
#         for s in self:
#             print('ok')
#             fromage_all = self.env['mois.fromage'].search([]).ids
#             print('allll---',fromage_all)
#             s.mois_fromage_all = fromage_all
#             print('sssss--',s.mois_fromage_all)

#     mois_fromage_all = fields.Many2many('mois.fromage','all_product_mois_fromage_rel','product_id','mois_fromage_id', string='Tous les Mois du fromage', compute=ts_mois_fromage)


#     @api.onchange('uom_po_id', 'uom_id')
#     @api.depends('uom_po_id', 'uom_id')
#     def onchange_poids_net(self):
#         for obj in self:
#             obj.weight = obj.uom_id.factor_inv
#             obj.weight_uom_id = obj.env['uom.uom'].search(
#                 [('category_id', '=', obj.uom_id.category_id.id), ('uom_type', '=', 'reference')], limit=1).id


#     weight_uom_id = fields.Many2one('uom.uom', 'UV', default=False, readonly=False, store=True, compute=onchange_poids_net)
#     weight = fields.Float('Nbr PC / Colis', digits=dp.get_precision('Stock Weight'))
#     product_weight = fields.Float('Poids Net / Colis', digits=dp.get_precision('Stock Weight'), help="Poids Fixe de l'entité avec unité de mesure de stockage Colis / Pièce / Kg", copy=True)


#     uom_id = fields.Many2one(
#         'uom.uom', 'Unité de Stockage',  required=True,
#         help="Default unit of measure used for all stock operations.")
#     uom_po_id = fields.Many2one(
#         'uom.uom', "Unité d'achat", required=True,
#         help="Default unit of measure used for purchase orders. It must be in the same category as the default unit of measure.")

#     tracking = fields.Selection([
#         ('serial', 'By Unique Serial Number'),
#         ('lot', 'By Lots'),
#         ('none', 'No Tracking')], string="Tracking",
#         help="Ensure the traceability of a storable product in your warehouse.", default='lot', required=True)


# class SupplierInfo(models.Model):
#     _inherit = "product.supplierinfo"

#     prix_brut = fields.Float('Prix Brut')


class ProductProduct(models.Model):
    _inherit = 'product.product'


    @api.constrains('barcode','active','product_tmpl_id')
    def _check_barcode_unique(self):
        for obj in self:
            if obj.barcode:
                filtre=[
                    ('barcode', '=' , obj.barcode),
                    ('id'  , '!=', obj.id),
                    ('product_tmpl_id.company_id', '=', obj.product_tmpl_id.company_id.id),
                ]
                products = self.env['product.product'].sudo().search(filtre, limit=1)
                if products:
                    raise Warning("Le code barre doit-être unique !") 

 

    def name_get(self):
        self.browse(self.ids).read(['name', 'default_code'])



        return [(template.id, (template.default_code and '%s [%s]' % (template.name, template.default_code) or '%s' % (template.name) ))
            for template in self]








#     @api.onchange('default_code')
#     @api.multi
#     def default_code_uniq(self):
#         list = []
#         if self.default_code or self._origin.default_code:
#             default_code_list = self.env['product.product'].search([('default_code', '=', self.default_code)])
#             if default_code_list:
#                 for l in default_code_list:
#                     list.append(l.id)
#             if len(list) >= 1:
#                 print('messaaaageeee')
#                 warning_mess = {
#                     'title': _('Référence interne'),
#                     'message': _(
#                         'Référence interne doit être unique !')
#                 }
#                 return {'warning': warning_mess}



#     @api.onchange('uom_po_id', 'uom_id')
#     @api.multi
#     def onchange_poids_net(self):
#         self.weight = self.uom_id.factor_inv
#         self.weight_uom_id = self.env['uom.uom'].search(
#             [('category_id', '=', self.uom_id.category_id.id), ('uom_type', '=', 'reference')], limit=1).id

#     @api.multi
#     @api.depends('stock_move_ids.product_qty', 'stock_move_ids.state', 'stock_move_ids.remaining_value',
#                  'product_tmpl_id.cost_method', 'product_tmpl_id.standard_price', 'product_tmpl_id.property_valuation',
#                  'product_tmpl_id.categ_id.property_valuation')
#     def _compute_weight_stock_value(self):
#         for product in self:
#             if product.qty_available>0:
#                 product.weight_stock_value = (product.stock_value/product.qty_available) * product.weight_qty_available


#     weight_stock_value = fields.Float(
#         'Valeur', compute='_compute_weight_stock_value')



#     @api.depends('stock_move_ids.product_qty', 'stock_move_ids.state')
#     def _compute_weight_quantities(self):
#         res = self._compute_weight_quantities_dict(self._context.get('lot_id'), self._context.get('owner_id'),
#                                             self._context.get('package_id'), self._context.get('from_date'),
#                                             self._context.get('to_date'))
#         for product in self:
#             product.weight_qty_available = res[product.id]['weight']



#     def _compute_weight_quantities_dict(self, lot_id, owner_id, package_id, from_date=False, to_date=False):
#         domain_quant_loc, domain_move_in_loc, domain_move_out_loc = self._get_domain_locations()
#         domain_quant = [('product_id', 'in', self.ids)] + domain_quant_loc
#         dates_in_the_past = False
#         # only to_date as to_date will correspond to qty_available
#         to_date = fields.Datetime.to_datetime(to_date)
#         if to_date and to_date < fields.Datetime.now():
#             dates_in_the_past = True

#         domain_move_in = [('product_id', 'in', self.ids)] + domain_move_in_loc
#         domain_move_out = [('product_id', 'in', self.ids)] + domain_move_out_loc
#         if lot_id is not None:
#             domain_quant += [('lot_id', '=', lot_id)]
#         if owner_id is not None:
#             domain_quant += [('owner_id', '=', owner_id)]
#             domain_move_in += [('restrict_partner_id', '=', owner_id)]
#             domain_move_out += [('restrict_partner_id', '=', owner_id)]
#         if package_id is not None:
#             domain_quant += [('package_id', '=', package_id)]
#         if dates_in_the_past:
#             domain_move_in_done = list(domain_move_in)
#             domain_move_out_done = list(domain_move_out)
#         if from_date:
#             domain_move_in += [('date', '>=', from_date)]
#             domain_move_out += [('date', '>=', from_date)]
#         if to_date:
#             domain_move_in += [('date', '<=', to_date)]
#             domain_move_out += [('date', '<=', to_date)]

#         Move = self.env['stock.move']
#         Quant = self.env['stock.quant']
#         domain_move_in_todo = [('state', 'in',
#                                 ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_in
#         domain_move_out_todo = [('state', 'in',
#                                  ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_out
#         moves_in_res = dict((item['product_id'][0], item['product_qty']) for item in
#                             Move.read_group(domain_move_in_todo, ['product_id', 'product_qty'], ['product_id'],
#                                             orderby='id'))
#         moves_out_res = dict((item['product_id'][0], item['product_qty']) for item in
#                              Move.read_group(domain_move_out_todo, ['product_id', 'product_qty'], ['product_id'],
#                                              orderby='id'))
#         quants_res = dict((item['product_id'][0], item['weight']) for item in
#                           Quant.read_group(domain_quant, ['product_id', 'weight'], ['product_id'], orderby='id'))
#         if dates_in_the_past:
#             # Calculate the moves that were done before now to calculate back in time (as most questions will be recent ones)
#             domain_move_in_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_in_done
#             domain_move_out_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_out_done
#             moves_in_res_past = dict((item['product_id'][0], item['weight']) for item in
#                                      Move.read_group(domain_move_in_done, ['product_id', 'weight'], ['product_id'],
#                                                      orderby='id'))
#             moves_out_res_past = dict((item['product_id'][0], item['weight']) for item in
#                                       Move.read_group(domain_move_out_done, ['product_id', 'weight'],
#                                                       ['product_id'], orderby='id'))

#         res = dict()
#         for product in self.with_context(prefetch_fields=False):
#             product_id = product.id
#             rounding = product.uom_id.rounding
#             res[product_id] = {}
#             if dates_in_the_past:
#                 qty_available = quants_res.get(product_id, 0.0) - moves_in_res_past.get(product_id,
#                                                                                         0.0) + moves_out_res_past.get(
#                     product_id, 0.0)
#             else:
#                 qty_available = quants_res.get(product_id, 0.0)
#             res[product_id]['weight'] = float_round(qty_available, precision_rounding=rounding)

#         return res

#     weight_qty_available = fields.Float(
#         'Poids', compute='_compute_weight_quantities')

# class UoM(models.Model):
#     _inherit = 'uom.uom'

#     @api.multi
#     def _compute_quantity(self, qty, to_unit, round=True, rounding_method='UP', raise_if_failure=True):
#         """ Convert the given quantity from the current UoM `self` into a given one
#             :param qty: the quantity to convert
#             :param to_unit: the destination UoM record (uom.uom)
#             :param raise_if_failure: only if the conversion is not possible
#                 - if true, raise an exception if the conversion is not possible (different UoM category),
#                 - otherwise, return the initial quantity
#         """
#         if not self:
#             return qty
#         self.ensure_one()
#         if self.category_id.id != to_unit.category_id.id:
#             if raise_if_failure:
#                 print('Error UOM')
#             else:
#                 return qty
#         amount = qty / self.factor
#         if to_unit:
#             amount = amount * to_unit.factor
#             if round:
#                 amount = tools.float_round(amount, precision_rounding=to_unit.rounding, rounding_method=rounding_method)
#         return amount

