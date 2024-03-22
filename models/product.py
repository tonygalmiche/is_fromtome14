
# -*- coding: utf-8 -*-
from odoo import api, fields, tools, models,_
from odoo.tools import float_is_zero, pycompat
from odoo.tools.float_utils import float_round
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import pytz
import math
import logging
_logger = logging.getLogger(__name__)


_TRAITEMENT_THERMIQUE = [('laitcru', 'Lait Cru'), ('laitthermise', 'Lait Thermise'), ('laitpasteurisé', 'Lait Pasteurise')]
_PRICELISTS = {
    'cdf_quai'  : 'Cdf quai',
    'cdf_franco': 'Cdf franco',
    'lf'        : 'LF',
    'lf_coll'   : 'LF coll.',
    'ft'        : 'FT',
}

class MilkType(models.Model):
    _name="milk.type"
    _description = "Type d'article"
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
            fournisseur_id = False
            suppliers=self.env['product.supplierinfo'].search(filtre,limit=1)
            for s in suppliers:
                ref=s.product_code
                fournisseur_id = s.name.id
            obj.is_ref_fournisseur = ref
            obj.is_fournisseur_id  = fournisseur_id


    is_ref_fournisseur = fields.Char(string='Réf fournisseur'        , compute='_compute_is_ref_fournisseur', readonly=True, store=True)
    is_fournisseur_id  = fields.Many2one('res.partner', 'Fournisseur', compute='_compute_is_ref_fournisseur', readonly=True, store=True)


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
    milk_type_ids         = fields.Many2many('milk.type','product_milk_type_rel','product_id','milk_type_id', string='Types articles')

    is_type_article = fields.Char(string='Type article', compute='_compute_is_type_article', readonly=True, store=True)

    milk_type             = fields.Char(string='Types article', compute='_compute_milk_type')
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

    is_stock_mini         = fields.Float("Stock mini FT", digits=(14,4))
    is_stock_mini_lc      = fields.Float("Stock mini LC", digits=(14,4))
    is_pricelist_item_ids = fields.One2many('product.pricelist.item', 'product_tmpl_id', 'Liste de prix')

    is_nb_pieces_par_colis = fields.Integer(string='Nb Pièces / colis')
    is_poids_net_colis     = fields.Float(string='Poids net colis (Kg)', digits='Stock Weight')
    is_forcer_poids_colis  = fields.Boolean(string='Forcer le scan au poids du colis', default=False, help="Cocher cette case si l'article est configuré par erreur au poids alors qu'il fallait le configuer à la pièce")

    is_note_importation = fields.Text(string='Note importation Fusion Fromtome / Le Cellier')

    is_date_bascule_tarif = fields.Date(string="Date bascule", help='Date bascule tarif client'                   , compute='_compute_tarifs', readonly=True, store=True)
    is_prix_achat_actuel  = fields.Float(string="PA actuel", digits='Product Price', compute='_compute_tarifs', readonly=True, store=True)
    is_prix_achat_futur   = fields.Float(string="PA futur" , digits='Product Price', compute='_compute_tarifs', readonly=True, store=True)

    is_prix_vente_actuel_cdf_quai   = fields.Float(string='PV actuel Cdf quai'  , digits='Product Price', readonly=True, store=True)
    is_prix_vente_actuel_cdf_franco = fields.Float(string='PV actuel Cdf franco', digits='Product Price', readonly=True, store=True)
    is_prix_vente_actuel_lf         = fields.Float(string='PV actuel LF'        , digits='Product Price', readonly=True, store=True)
    is_prix_vente_actuel_lf_coll    = fields.Float(string='PV actuel LF coll.'  , digits='Product Price', readonly=True, store=True)
    is_prix_vente_actuel_ft         = fields.Float(string='PV actuel FT'        , digits='Product Price', readonly=True, store=True)

    is_prix_vente_actuel_marge_cdf_quai   = fields.Float(string='TM actuel forcé Cdf quai'  , digits='Product Price')
    is_prix_vente_actuel_marge_cdf_franco = fields.Float(string='TM actuel forcé Cdf franco', digits='Product Price')
    is_prix_vente_actuel_marge_lf         = fields.Float(string='TM actuel forcé LF'        , digits='Product Price')
    is_prix_vente_actuel_marge_lf_coll    = fields.Float(string='TM actuel forcé LF coll.'  , digits='Product Price')
    is_prix_vente_actuel_marge_ft         = fields.Float(string='TM actuel forcé FT'        , digits='Product Price')

    is_prix_vente_futur_cdf_quai   = fields.Float(string='PV futur Cdf quai'  , digits='Product Price', compute='_compute_tarifs', readonly=True, store=True)
    is_prix_vente_futur_cdf_franco = fields.Float(string='PV futur Cdf franco', digits='Product Price', compute='_compute_tarifs', readonly=True, store=True)
    is_prix_vente_futur_lf         = fields.Float(string='PV futur LF'        , digits='Product Price', compute='_compute_tarifs', readonly=True, store=True)
    is_prix_vente_futur_lf_coll    = fields.Float(string='PV futur LF coll.'  , digits='Product Price', compute='_compute_tarifs', readonly=True, store=True)
    is_prix_vente_futur_ft         = fields.Float(string='PV futur FT'        , digits='Product Price', compute='_compute_tarifs', readonly=True, store=True)

    is_prix_vente_futur_marge_cdf_quai   = fields.Float(string='TM futur forcé Cdf quai'  , digits='Product Price')
    is_prix_vente_futur_marge_cdf_franco = fields.Float(string='TM futur forcé Cdf franco', digits='Product Price')
    is_prix_vente_futur_marge_lf         = fields.Float(string='TM futur forcé LF'        , digits='Product Price')
    is_prix_vente_futur_marge_lf_coll    = fields.Float(string='TM futur forcé LF coll.'  , digits='Product Price')
    is_prix_vente_futur_marge_ft         = fields.Float(string='TM futur forcé FT'        , digits='Product Price')

    is_discount = fields.Float(string="Remise (%)", compute='_compute_is_discount', readonly=True, store=True, digits="Discount", help="Remise du fournisseur par défaut (actualisé la nuit par la gestion des promos)")


    @api.depends('seller_ids','seller_ids.discount')
    def _compute_is_discount(self):
        for obj in self:
            discount=0
            if obj.product_variant_id:
                seller = obj.product_variant_id._select_seller(
                    partner_id=obj.is_fournisseur_id,
                )
                if seller:
                    discount = seller.discount
            obj.is_discount = discount


    @api.depends('milk_type_ids','milk_type_ids.name')
    def _compute_is_type_article(self):
        for obj in self:
            l=[]
            for line in obj.milk_type_ids:
                if line.name:
                    l.append(line.name)
            val=""
            if len(l)>0:
                val = ",".join(l)
            obj.is_type_article = val


    def update_prix_actuel_action(self):
        self._compute_tarifs(update_prix_actuel=True)


    # Prix FRANCO = Prix A QUAI + montant en € => 12€ + 0,8 = 12,80 pour les produit facturé au Kg
    # Prix FRANCO = Prix A QUAI + (montant en € x poids du produit) =>  fromage de 300g => 2,5€ + (0,8x0,3) = 2,74€/pièce pour les produits facturés à la pièce
    def get_frais_port(self,port=0):
        for obj in self:
            res = 0
            unite = obj.uom_id.category_id.name
            if unite=="Poids":
                res=port
            else:
                nb = obj.is_nb_pieces_par_colis or 1
                res= port*obj.is_poids_net_colis/nb
            return res

    @api.depends('seller_ids','seller_ids.price',
                 'seller_ids.date_start',
                 'is_prix_vente_actuel_marge_cdf_quai',
                 'is_prix_vente_actuel_marge_cdf_franco',
                 'is_prix_vente_actuel_marge_lf',
                 'is_prix_vente_actuel_marge_lf_coll',
                 'is_prix_vente_actuel_marge_ft',
                 'is_prix_vente_futur_marge_cdf_quai',
                 'is_prix_vente_futur_marge_cdf_franco',
                 'is_prix_vente_futur_marge_lf',
                 'is_prix_vente_futur_marge_lf_coll',
                 'is_prix_vente_futur_marge_ft',
                 'active'
    )
    def _compute_tarifs(self, update_prix_actuel=False):
        company = self.env.user.company_id

        #** Coefficients à appliquer ******************************************
        coefs={}
        for price in _PRICELISTS:
            name = "is_coef_%s"%price
            coef = getattr(company, name)
            coefs[price] = coef
        #**********************************************************************

        #** Frais de port à appliquer *****************************************
        ports={}
        for price in _PRICELISTS:
            name = "is_port_%s"%price
            port = getattr(company, name)
            ports[price] = port
        #**********************************************************************

        nb=len(self)
        ct=1
        for obj in self:
            #** Recherche du prix d'achat actuel ******************************
            now = datetime.now().date()
            prix_actuel = 0
            for line in obj.seller_ids:
                if now>=line.date_start and now<=line.date_end:
                    prix_actuel = line.price
                    #obj._compute_is_discount()
            obj.is_prix_achat_actuel  = prix_actuel
            #******************************************************************

            #** Recherche du prix d'achat futur *******************************
            prix_futur  = 0
            mem_date=False
            for line in obj.seller_ids:
                if mem_date==False:
                    mem_date = line.date_start
                    prix_futur = line.price
                if line.date_start>mem_date:
                    mem_date = line.date_start
                    prix_futur = line.price
            obj.is_prix_achat_futur   = prix_futur
            #******************************************************************

            #** Prix de vente actuel ******************************************
            if update_prix_actuel:
                for price in _PRICELISTS:
                    taux_marge = coefs[price]
                    name = "is_prix_vente_actuel_marge_%s"%price
                    force = getattr(obj, name)
                    if force!=0:
                        taux_marge = force
                    val=0
                    #if taux_marge<100 and taux_marge>0:
                    if taux_marge<100:
                        val = round(100 * prix_actuel / (100 - taux_marge),4) # PrixVente = 100 x PrixAchat / (100 - TauxMarge)
                    val+=obj.get_frais_port(ports[price])
                    name = "is_prix_vente_actuel_%s"%price
                    setattr(obj, name, val)
            #******************************************************************

            #** Mise à jour des liste de prix *********************************
            if update_prix_actuel:
                for product in obj.product_variant_ids:
                    if type(product.id)==int:
                        product.update_pricelist(product_tmpl_id=obj.id)
            #******************************************************************

            #** Prix de vente futur *******************************************
            for price in _PRICELISTS:
                taux_marge = coefs[price]
                name = "is_prix_vente_futur_marge_%s"%price
                force = getattr(obj, name)
                if force!=0:
                    taux_marge = force
                val=0
                #if taux_marge<100 and taux_marge>0:
                if taux_marge<100:
                    val = round(100 * prix_futur / (100 - taux_marge),4) # PrixVente = 100 x PrixAchat / (100 - TauxMarge)
                val+=obj.get_frais_port(ports[price])
                name = "is_prix_vente_futur_%s"%price
                setattr(obj, name, val)
            #******************************************************************
            _logger.info("_compute_tarifs : %s/%s : %s"%(ct,nb,obj.name))
            ct+=1


    def appliquer_nouveaux_tarifs_action(self):
        tz = pytz.timezone('Europe/Paris')
        now = datetime.now(tz).strftime("%Y-%m-%d à %H:%M:%S")
        for key in _PRICELISTS:
            name = _PRICELISTS[key]
            pricelists = self.env['product.pricelist'].search([('name', '=', name)])
            if pricelists:
                pricelist = pricelists[0]
                name = "%s archivée le %s"%(name,now)
                default={
                    "name"  : name,
                    "active": False,
                }
                copy = pricelist.copy(default=default)
                _logger.info("appliquer_nouveaux_tarifs_action : Archivage liste de prix '%s'"%name)
        filtre=[
            #("default_code","=","0111001")
        ]
        products = self.env['product.template'].search(filtre)
        nb=len(products)
        ct=1
        for product in products:
            _logger.info("appliquer_nouveaux_tarifs_action : %s/%s : %s"%(ct,nb,product.default_code))
            vals={}
            for price in _PRICELISTS:
                name = "is_prix_vente_futur%s"%price
                is_prix_vente_futur       = getattr(product, "is_prix_vente_futur_%s"%price)
                is_prix_vente_futur_marge = getattr(product, "is_prix_vente_futur_marge_%s"%price)
                vals.update({
                    "is_prix_vente_actuel_%s"%price     : is_prix_vente_futur,
                    "is_prix_vente_actuel_marge_%s"%price: is_prix_vente_futur_marge,
                })
            product.write(vals)
            for variante in product.product_variant_ids:
                variante.update_pricelist(product_tmpl_id=product.id)
            ct+=1


    def init_emplacement_inventaire_action(self):
        for obj in self:
            if not obj.property_stock_inventory:
                obj.property_stock_inventory = 14


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


    def voir_article_action(self):
        for obj in self:
            res= {
                'name': 'Article',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_model': 'product.template',
                'type': 'ir.actions.act_window',
                'res_id':obj.id,
            }
            return res


    def uom2colis(self,qty,arrondir="round"):
        nb        = self.is_nb_pieces_par_colis
        poids_net = self.is_poids_net_colis
        unite     = self.uom_id.category_id.name
        nb_colis  = 0
        if unite=="Poids":
            if poids_net>0:
                nb_colis = qty / poids_net
        else:
            if nb>0:
                nb_colis = qty / nb
        nb_colis = round(nb_colis,2)       # Arrondir à 2 decimales pour éviter les problèmes de virgules flotante
        if arrondir=="round":             
            nb_colis = round(nb_colis)     # Arrondir à l'entier le plus proche
        if arrondir=="ceil":
            nb_colis = math.ceil(nb_colis) # Arrondir à l'entier supérieur
        return nb_colis


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


    def update_pricelist_ir_cron(self):
        cr, user, context, su = self.env.args
        products = self.env['product.template'].search([])
        ids=[]
        for product in products:
            ids.append(str(product.id))
        nb_products = len(products)

        for key in _PRICELISTS:
            name = _PRICELISTS[key]
            pricelists = self.env['product.pricelist'].search([('name', '=', name)], limit=1)
            for pricelist in pricelists:
                #** Supprimer les lignes sans article correspondand ***********
                items = self.env['product.pricelist.item'].search([('pricelist_id'   ,'=',pricelist.id)])
                nb1=len(items)
                SQL="delete from product_pricelist_item where pricelist_id=%s and product_tmpl_id not in(%s)"%(pricelist.id,",".join(ids))
                cr.execute(SQL)
                items = self.env['product.pricelist.item'].search([('pricelist_id'   ,'=',pricelist.id)])
                nb2=len(items)
                #**************************************************************

                #** Mettre à jour les articles manquant ***********************
                item_ids=[]
                for item in items:
                    item_ids.append(str(item.product_tmpl_id.id))
                for id in ids:
                    if id not in item_ids:
                        product = self.env['product.template'].browse(int(id))
                        if product:
                            field_name = "is_prix_vente_actuel_%s"%key
                            price = round(getattr(product, field_name),6)
                            if price>0:
                                print("Ajouter article %s"%product.name,product.product_variant_ids)
                                product.product_variant_ids.update_pricelist(product_tmpl_id=product.id)
                #**************************************************************

                items = self.env['product.pricelist.item'].search([('pricelist_id'   ,'=',pricelist.id)])
                nb3=len(items)
                print(pricelist, pricelist.name, nb_products, nb1,nb2,nb3)
                #**************************************************************


    def update_pricelist(self, product_tmpl_id=False):
        for key in _PRICELISTS:
            name = _PRICELISTS[key]
            pricelists = self.env['product.pricelist'].search([('name', '=', name)])
            if pricelists:
                pricelist = pricelists[0]
            else:
                vals={
                    'name': name
                }
                pricelist = self.env['product.pricelist'].create(vals)
            if pricelist:
                field_name = "is_prix_vente_actuel_%s"%key
                filtre=[
                    (field_name, '>', 0)
                ]
                if product_tmpl_id:
                    filtre.append(('product_tmpl_id','=', product_tmpl_id))
                products = self.env['product.product'].search(filtre, order='default_code') #, limit=10)
                nb=len(products)
                ct=1
                for product in products:
                    price = round(getattr(product, field_name),6)
                    item=False
                    filtre=[
                        ('pricelist_id'   ,'=',pricelist.id),
                        ('product_tmpl_id','=', product.product_tmpl_id.id),
                    ]
                    items = self.env['product.pricelist.item'].search(filtre)
                    if items:
                        item=items[0]
                        if product.product_tmpl_id.active==False:
                            item.unlink()
                            item=False
                    if not item and product.product_tmpl_id.active:
                        vals={
                            'pricelist_id'   : pricelist.id,
                            'product_tmpl_id': product.product_tmpl_id.id,
                            'applied_on'     : '1_product',
                            'fixed_price'    : price,
                        }
                        item = self.env['product.pricelist.item'].create(vals)
                    if item:
                        item.fixed_price = price
                        _logger.info("update_pricelist : %s : %s/%s : %s : %s"%(key,ct,nb,product.default_code,price))
                    ct+=1



    def get_product_pricelist(self,pricelist):
        price=0
        items = self.env['product.pricelist.item'].search([
                ('pricelist_id','=',pricelist.id),('product_tmpl_id','=',self.product_tmpl_id.id)
            ], order="date_start desc", limit=1)
        for item in items:
            price=item.fixed_price
        return price


    def get_prix_futur(self,prix_futur=False):
        price=0
        if prix_futur:
            name = "is_prix_vente_futur_%s"%prix_futur
            price = getattr(self, name)
        return price



    def voir_product_template_action(self):
        for obj in self:
            return obj.product_tmpl_id.voir_article_action()
