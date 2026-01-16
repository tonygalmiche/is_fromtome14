# -*- coding: utf-8 -*-
from odoo import api, fields, tools, models,_           # type: ignore
from odoo.tools import float_is_zero, pycompat          # type: ignore
from odoo.tools.float_utils import float_round          # type: ignore
from odoo.addons import decimal_precision as dp         # type: ignore
from odoo.exceptions import UserError, ValidationError  # type: ignore
from datetime import datetime
import pytz
import math
import base64
from subprocess import PIPE, Popen
import re
import logging
_logger = logging.getLogger(__name__)


_TRAITEMENT_THERMIQUE = [('laitcru', 'Lait Cru'), ('laitthermise', 'Lait Thermise'), ('laitpasteurisé', 'Lait Pasteurise')]
_PRICELISTS = {
    'cdf_quai'  : 'Cdf quai',
    'cdf_franco': 'Cdf franco',
    #'lf'        : 'LF',
    #'lf_coll'   : 'LF coll.',
    #'lf_franco' : 'LF franco',
    'ft'        : 'FT',
}
_COLISAGE = [
    ('1', 'Colis'),
    ('2', '1/2 colis'),
    ('4', '1/4 colis'),
]


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


    is_ref_fournisseur = fields.Char(string='Réf fournisseur'        , compute='_compute_is_ref_fournisseur', readonly=True, store=True, tracking=True)
    is_fournisseur_id  = fields.Many2one('res.partner', 'Fournisseur', compute='_compute_is_ref_fournisseur', readonly=True, store=True, tracking=True)


    contrat_date_id = fields.One2many('contrat.date.client','product_id','Contrat Date')

    # Présentation / Conseils
    is_enseigne_id   = fields.Many2one('is.enseigne.commerciale', 'Enseigne', help="Enseigne commerciale", tracking=True)
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
    is_poids_brut             = fields.Char(string='Poids brut')
    is_atelier_transformation = fields.Char(string='Atelier de transformation')
    no_agrement_sanitaire     = fields.Char(string="N° d'agrément fabricant")
    temperature_stock         = fields.Char(string='T° de conservation')
    is_ogm_ionisation         = fields.Char(string='OGM / Ionisation')


    # CARACTÉRISTIQUES ORGANOLEPTIQUES:
    is_forme   = fields.Char(string='Forme')
    is_couleur = fields.Char(string='Couleur')
    texture    = fields.Char(string='Texture')

    degustation = fields.Char(string='Goût / Dégustation')
    odeur       = fields.Char(string='Odeur')

    is_ingredient_ids    = fields.One2many('is.ingredient.line', 'product_id', "Lignes", copy=True)
    is_ingredient        = fields.Html(string='Ingrédients (dont allergènes en gras)', compute='_compute_is_ingredient')
    is_ingredient_import = fields.Text(string='Ingrédients importés')
    is_allergene_import  = fields.Text(string='Allergènes importés')

    is_germe_ids                 = fields.One2many('is.germe.line'                , 'product_id', "Germes" , copy=True)
    is_valeur_nutritionnelle_ids = fields.One2many('is.valeur.nutritionnelle.line', 'product_id', "Valeurs", copy=True)

    product_label_ids = fields.Many2many('product.label','product_label_rel','product_id','label_id', string='Labels')
    mode_vente        = fields.Selection(selection=[('colis', 'Colis'),('piece', 'Pièce'),('decoupe', 'Découpe')], string="Mode Vente", tracking=True)
    douane            = fields.Char(string='Nomenclature Douane')

    is_stock_mini         = fields.Float("Stock mini FT", digits=(14,4), tracking=True)
    is_stock_mini_lc      = fields.Float("Stock mini LC", digits=(14,4), tracking=True)
    is_pricelist_item_ids = fields.One2many('product.pricelist.item', 'product_tmpl_id', 'Liste de prix') #, domain=[('pricelist_id.active','in',[0,1]),('active','in',[0,1])])

    is_note_importation = fields.Text(string='Note importation Fusion Fromtome / Le Cellier')

    is_date_bascule_tarif = fields.Date(string="Date bascule", help='Date bascule tarif client'                   , compute='_compute_tarifs', readonly=True, store=True)
    is_prix_achat_actuel  = fields.Float(string="PA actuel", digits='Product Price', compute='_compute_tarifs', readonly=True, store=True, tracking=True)
    is_prix_achat_futur   = fields.Float(string="PA futur" , digits='Product Price', compute='_compute_tarifs', readonly=True, store=True, tracking=True)

    is_prix_vente_actuel_cdf_quai   = fields.Float(string='PV actuel A QUAI'  , digits='Product Price', readonly=True, store=True, tracking=True)
    is_prix_vente_actuel_cdf_franco = fields.Float(string='PV actuel FRANCO'  , digits='Product Price', readonly=True, store=True, tracking=True)
    is_prix_vente_actuel_ft         = fields.Float(string='PV actuel FROMTOME', digits='Product Price', readonly=True, store=True, tracking=True)
    is_prix_vente_actuel_lf         = fields.Float(string='PV actuel LF        (Ne plus utiliser)', digits='Product Price', readonly=True, store=True, tracking=True)
    is_prix_vente_actuel_lf_coll    = fields.Float(string='PV actuel LF coll.  (Ne plus utiliser)', digits='Product Price', readonly=True, store=True, tracking=True)
    is_prix_vente_actuel_lf_franco  = fields.Float(string='PV actuel LF franco (Ne plus utiliser)', digits='Product Price', readonly=True, store=True, tracking=True)

    is_prix_vente_actuel_marge_cdf_quai   = fields.Float(string='TM actuel forcé A QUAI'  , digits='Product Price', tracking=True)
    is_prix_vente_actuel_marge_cdf_franco = fields.Float(string='TM actuel forcé FRANCO'  , digits='Product Price', tracking=True)
    is_prix_vente_actuel_marge_ft         = fields.Float(string='TM actuel forcé FROMTOME', digits='Product Price', tracking=True)
    is_prix_vente_actuel_marge_lf         = fields.Float(string='TM actuel forcé LF        (Ne plus utiliser)', digits='Product Price', tracking=True)
    is_prix_vente_actuel_marge_lf_coll    = fields.Float(string='TM actuel forcé LF coll.  (Ne plus utiliser)', digits='Product Price', tracking=True)
    is_prix_vente_actuel_marge_lf_franco  = fields.Float(string='TM actuel forcé LF franco (Ne plus utiliser)', digits='Product Price', tracking=True)

    is_prix_vente_futur_cdf_quai   = fields.Float(string='PV futur A QUAI'  , digits='Product Price', compute='_compute_tarifs', readonly=True, store=True, tracking=True)
    is_prix_vente_futur_cdf_franco = fields.Float(string='PV futur FRANCO'  , digits='Product Price', compute='_compute_tarifs', readonly=True, store=True, tracking=True)
    is_prix_vente_futur_ft         = fields.Float(string='PV futur FROMTOME', digits='Product Price', compute='_compute_tarifs', readonly=True, store=True, tracking=True)
    is_prix_vente_futur_lf         = fields.Float(string='PV futur LF        (Ne plus utiliser)', digits='Product Price', compute='_compute_tarifs', readonly=True, store=True, tracking=True)
    is_prix_vente_futur_lf_coll    = fields.Float(string='PV futur LF coll.  (Ne plus utiliser)', digits='Product Price', compute='_compute_tarifs', readonly=True, store=True, tracking=True)
    is_prix_vente_futur_lf_franco  = fields.Float(string='PV futur LF franco (Ne plus utiliser)', digits='Product Price', compute='_compute_tarifs', readonly=True, store=True, tracking=True)

    is_prix_vente_futur_marge_cdf_quai   = fields.Float(string='TM futur forcé A QUAI'  , digits='Product Price', tracking=True)
    is_prix_vente_futur_marge_cdf_franco = fields.Float(string='TM futur forcé FRANCO'  , digits='Product Price', tracking=True)
    is_prix_vente_futur_marge_ft         = fields.Float(string='TM futur forcé FROMTOME', digits='Product Price', tracking=True)
    is_prix_vente_futur_marge_lf         = fields.Float(string='TM futur forcé LF        (Ne plus utiliser)', digits='Product Price', tracking=True)
    is_prix_vente_futur_marge_lf_coll    = fields.Float(string='TM futur forcé LF coll.  (Ne plus utiliser)', digits='Product Price', tracking=True)
    is_prix_vente_futur_marge_lf_franco  = fields.Float(string='TM futur forcé LF franco (Ne plus utiliser)', digits='Product Price', tracking=True)
    is_discount                          = fields.Float(string="Remise (%)", compute='_compute_is_discount', readonly=True, store=True, digits="Discount", tracking=True, help="Remise du fournisseur par défaut (actualisé la nuit par la gestion des promos)")
    is_fiche_technique_ids               = fields.Many2many('ir.attachment', 'product_is_fiche_technique_rel', 'product_id', 'file_id', 'Fiche techinque')
    is_fiche_technique_import            =  fields.Text('Résultat importation fiche techinque')


    is_colisage            = fields.Selection(string='Colisage', selection=_COLISAGE, required=True, tracking=True, default='1', help="Utilisé dans 'Préparation transfert entrepôt'")
    is_nb_pieces_par_colis = fields.Integer(string='Nb Pièces / colis', tracking=True)
    is_poids_net_colis     = fields.Float(string='Poids net colis (Kg)', digits='Stock Weight', tracking=True)
    is_forcer_poids_colis  = fields.Boolean(string='Forcer le scan au poids du colis', tracking=True, default=False, help="Cocher cette case si l'article est configuré par erreur au poids alors qu'il fallait le configuer à la pièce")
    is_colis_en_stock      = fields.Float(string='Nb colis théorique', digits=(14,1), compute='_compute_is_colis_en_stock',)
    is_colis_en_stock_scan = fields.Float(string='Nb colis scan'     , digits=(14,1), help="Nombre de colis en stock calculé d'après les scan")
    is_colis_ecart         = fields.Float(string='Ecart nb colis'    , digits=(14,1), help="Ecart entre le nombre de colis théorique et d'après les scans")


    def _compute_is_colis_en_stock(self):
        for obj in self:
            stock     = obj.qty_available
            nb        = obj.is_nb_pieces_par_colis
            poids_net = obj.is_poids_net_colis
            unite     = obj.uom_id.category_id.name
            nb_colis  = 0
            if unite=="Poids":
                if poids_net>0:
                    nb_colis = stock/poids_net
            else:
                if nb>0:
                    nb_colis = stock / nb
            nb_colis = math.floor(nb_colis * 2) / 2  # Arrondir au 1/2 colis inférieur
            obj.is_colis_en_stock = round(nb_colis,1)



    def recalcule_colis_stock_scans_action(self):
        """
        Recalcule le champ is_colis_en_stock_scan en remontant dans le passé
        à partir du stock actuel et en analysant les mouvements de stock.
        """
        for obj in self:
            # Récupérer tous les product.product liés à ce template
            product_ids = obj.product_variant_ids.ids
            if not product_ids:
                obj.is_colis_en_stock_scan = 0
                continue

            # Stock actuel
            stock_actuel = obj.qty_available
            stock_calcule = stock_actuel
            total_colis = 0.0

            # Recherche des mouvements de stock terminés, triés par date décroissante
            # On prend les mouvements qui affectent le stock (entrant ou sortant de l'emplacement interne)
            moves = self.env['stock.move'].search([
                ('product_id', 'in', product_ids),
                ('state', '=', 'done'),
            ], order='date desc')

            _logger.info("=" * 100)
            _logger.info("Recalcul colis stock scan pour: %s (Réf: %s)", obj.name, obj.default_code)
            _logger.info("Stock actuel: %.4f", stock_actuel)
            _logger.info("-" * 100)
            _logger.info("%-20s | %-15s | %-20s | %-12s | %12s | %10s | %12s", 
                        "Date", "Picking", "Référence", "Type", "Qté", "Nb Colis", "Stock calculé")
            _logger.info("-" * 100)

            for move in moves:
                picking = move.picking_id
                picking_name = picking.name if picking else "N/A"
                reference = move.reference or "N/A"
                date_move = move.date.strftime('%Y-%m-%d %H:%M') if move.date else "N/A"
                
                # Déterminer le type de mouvement (réception ou livraison)
                # Réception: location_dest_id est un emplacement interne (usage='internal')
                # Livraison: location_id est un emplacement interne
                # Inventaire: utilise un emplacement virtuel d'inventaire (usage='inventory')
                location_src = move.location_id
                location_dest = move.location_dest_id
                
                qty = move.quantity_done
                nb_colis = move.is_nb_colis
                
                # Si la destination est interne et source n'est pas interne => Réception
                # Si la destination est interne et source est inventaire => Inventaire positif (ajout)
                # Si la source est interne et destination n'est pas interne => Livraison
                # Si la source est interne et destination est inventaire => Inventaire négatif (retrait)
                if location_dest.usage == 'internal' and location_src.usage not in ('internal',):
                    if location_src.usage == 'inventory':
                        type_mouvement = "Inv. +"
                    else:
                        type_mouvement = "Réception"
                    # Pour remonter dans le passé, on soustrait les réceptions/ajouts
                    stock_calcule -= qty
                    # Les colis comptent positivement
                    total_colis += nb_colis
                elif location_src.usage == 'internal' and location_dest.usage not in ('internal',):
                    if location_dest.usage == 'inventory':
                        type_mouvement = "Inv. -"
                    else:
                        type_mouvement = "Livraison"
                    # Pour remonter dans le passé, on ajoute les livraisons/retraits
                    stock_calcule += qty
                    # Les colis comptent négativement (ils sont sortis)
                    total_colis -= nb_colis
                elif location_src.usage == 'internal' and location_dest.usage == 'internal':
                    type_mouvement = "Transfert"
                    # Les transferts internes ne changent pas le stock global
                    continue
                else:
                    type_mouvement = "Autre"
                    continue

                _logger.info("%-20s | %-20s | %-12s | %12.4f | %10.2f | %12.4f",
                            date_move, reference, type_mouvement, qty, nb_colis, stock_calcule)

                # Arrêter uniquement si le stock calculé atteint exactement 0 (avec tolérance pour les erreurs de virgule flottante)
                # Le stock peut être négatif, dans ce cas on continue
                if abs(stock_calcule) <= 0.0001:
                    break

            _logger.info("-" * 100)
            _logger.info("Total colis calculé: %.2f", total_colis)
            _logger.info("=" * 100)

            # Mise à jour du champ
            obj.is_colis_en_stock_scan = total_colis
            obj.is_colis_ecart = abs(total_colis - obj.is_colis_en_stock)


    def recalcule_colis_stock_scans_ir_cron(self):
        """
        Tâche cron pour recalculer is_colis_en_stock_scan pour tous les articles
        ayant un stock disponible > 0.
        """
        # Recherche des articles avec du stock disponible
        products = self.env['product.template'].search([
            ('qty_available', '>', 0),
            ('active', '=', True),
        ])
        nb = len(products)
        _logger.info("recalcule_colis_stock_scans_ir_cron : Début du traitement de %s articles", nb)
        ct = 1
        for product in products:
            _logger.info("recalcule_colis_stock_scans_ir_cron : %s/%s : %s (%s)", ct, nb, product.default_code, product.name)
            product.recalcule_colis_stock_scans_action()
            ct += 1
        _logger.info("recalcule_colis_stock_scans_ir_cron : Fin du traitement")


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
                 'is_prix_vente_actuel_marge_ft',
                 'is_prix_vente_futur_marge_cdf_quai',
                 'is_prix_vente_futur_marge_cdf_franco',
                 'is_prix_vente_futur_marge_ft',
                 'active'
    )
    def _compute_tarifs(self, update_prix_actuel=False,pricelist=False):
        company = self.env.user.company_id
        prices = _PRICELISTS
        if pricelist:
            prices={pricelist: _PRICELISTS[pricelist]}

        #** Coefficients à appliquer ******************************************
        coefs={}
        for price in prices:
            name = "is_coef_%s"%price
            coef = getattr(company, name)
            coefs[price] = coef
        #**********************************************************************

        #** Frais de port à appliquer *****************************************
        ports={}
        for price in prices:
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
                for price in prices:
                    taux_marge = coefs[price]
                    name = "is_prix_vente_actuel_marge_%s"%price
                    force = getattr(obj, name)
                    if force!=0:
                        taux_marge = force
                    val=0
                    #if taux_marge<100 and taux_marge>0:
                    if taux_marge<100:
                        val = round(100 * prix_actuel / (100 - taux_marge),4) # PrixVente = 100 x PrixAchat / (100 - TauxMarge)
                    if val>0:
                        val+=obj.get_frais_port(ports[price])
                    name = "is_prix_vente_actuel_%s"%price
                    setattr(obj, name, val)
            #******************************************************************

            #** Mise à jour des liste de prix *********************************
            if update_prix_actuel:
                for product in obj.product_variant_ids:
                    if type(product.id)==int:
                        product.update_pricelist(product_tmpl_id=obj.id,pricelist=pricelist)
            #******************************************************************

            #** Prix de vente futur *******************************************
            for price in prices:
                taux_marge = coefs[price]
                name = "is_prix_vente_futur_marge_%s"%price
                force = getattr(obj, name)
                if force!=0:
                    taux_marge = force
                val=0
                #if taux_marge<100 and taux_marge>0:
                if taux_marge<100:
                    val = round(100 * prix_futur / (100 - taux_marge),4) # PrixVente = 100 x PrixAchat / (100 - TauxMarge)
                if val>0:
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
        colisage  = int(self.is_colisage or 1)
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
        nb_colis = round(nb_colis,2)                     # Arrondir à 2 decimales pour éviter les problèmes de virgules flotante
        if arrondir=="round":   
            nb_colis = round(colisage*nb_colis)/colisage # Arrondir à l'entier le plus proche en tenant compte du colisage
        if arrondir=="ceil":
            nb_colis = math.ceil(nb_colis)               # Arrondir à l'entier supérieur
        nb_colis = round(nb_colis,2)                     # Arrondir à 2 decimales pour éviter les problèmes de virgules flotante
        return nb_colis



    def colis2uom(self,colis):
        nb        = self.is_nb_pieces_par_colis
        poids_net = self.is_poids_net_colis
        unite     = self.uom_id.category_id.name
        if unite=="Poids":
            uom = colis * poids_net
        else:
            uom = colis * nb
        return round(uom,4)


    def voir_prix_archives(self):
        for obj in self:
            ids=[]
            filtre=[
                ('pricelist_id.active','in',[0,1]),
                ('active','in',[0,1]),
                ('product_tmpl_id','=',obj.id),
            ]
            items = self.env['product.pricelist.item'].search(filtre,order="pricelist_id")
            for item in items:
                ids.append(item.pricelist_id.id)
            dummy, view_id = self.env['ir.model.data'].get_object_reference('is_fromtome14', 'is_product_pricelist_item_tree')
            res= {
                'name': 'Lignes',
                'view_mode': 'tree',
                'view_type': 'form',
                'views': [[view_id, "tree"], [False, "form"]],
                'res_model': 'product.pricelist.item',
                'type': 'ir.actions.act_window',
                'domain': [
                    ('active','in',[0,1]),
                    ('pricelist_id','in',ids),
                    ('product_tmpl_id','=',obj.id),
                ],
                'limit': 1000,
            }
            return res


    def importer_fiche_technique_action(self):
        for obj in self:
            for attachment in obj.is_fiche_technique_ids:
                pdf=base64.b64decode(attachment.datas)
                name = 'fiche-technique-%s'%obj.id
                path = "/tmp/%s.pdf"%name
                f = open(path,'wb')
                f.write(pdf)
                f.close()
                cde = "cd /tmp && pdftotext -layout %s.pdf"%name
                p = Popen(cde, shell=True, stdout=PIPE, stderr=PIPE)
                stdout, stderr = p.communicate()
                path = "/tmp/%s.txt"%name
                r = open(path,'rb').read().decode('utf-8')
                lines = r.split('\n')
                ledict={}
                for line in lines:
                    ledict = obj.regex_extract(ledict,'01-Conditionnement'          , line, 'Conditionnement :'                 , False)
                    ledict = obj.regex_extract(ledict,'01-Poids brut'               , line, 'Poids brut :'                      , False)
                    ledict = obj.regex_extract(ledict,"02-N° d'agrément"            , line, "N° d'agrément sanitaire européen :", False)
                    ledict = obj.regex_extract(ledict,'03-Energie'                  , line, 'Energie :'                   , '    ')
                    ledict = obj.regex_extract(ledict,'04-Matières Grasses'         , line, 'Matières Grasses :'          , '    ')
                    ledict = obj.regex_extract(ledict,'05-Dont Acides gras saturés' , line, '► dont acides gras saturés :', '    ')
                    ledict = obj.regex_extract(ledict,'06-Glucides'                 , line, 'Glucides :'                  , '    ')
                    ledict = obj.regex_extract(ledict,'07-Dont Sucres'              , line, '► dont sucres :'             , False)
                    ledict = obj.regex_extract(ledict,'08-Protéines'                , line, 'Protéines :'                 , False)
                    ledict = obj.regex_extract(ledict,'09-Sel'                      , line, 'Sel :'                       , False)
                    ledict = obj.regex_extract(ledict,'10-Listeria'                 , line, 'Listeria :'                  , False)
                    ledict = obj.regex_extract(ledict,'11-Salmonelle'               , line, 'Salmonelle :'                , False)
                    ledict = obj.regex_extract(ledict,'12-Escherichia coli'         , line, 'Escherichia coli :'          , False)
                    ledict = obj.regex_extract(ledict,'13-Staphylocoques'           , line, 'Staphylocoques :'            , False)

                #** Recherche des ingredients sur plusieurs lignes ************
                search_start = search_end = False
                ingredients=[]
                for line in lines:
                    if search_start:
                        x = re.findall("Matière grasse :", line)
                        if x:
                            search_end=True
                    if search_start and not search_end:
                        ingredient = line.replace('Ingrédients :','').strip()
                        if ingredient!='':
                            ingredients.append(ingredient)
                    if not search_end:
                        x = re.findall("       PRODUIT", line)
                        if x:
                            search_start=True
                ledict['14-Ingrédients']='\n'.join(ingredients)
                #**************************************************************

                #** Recherche Allergènes **************************************
                search_start = False
                for line in lines:
                    if search_start:
                        x = re.findall("(.*)Froid positif :", line)
                        if x:
                            ledict['15-Allergènes']=x[0].strip()
                        break
                    x = re.findall("Conditions de conservation", line)
                    if x:
                        search_start=True
                #**************************************************************

                #** Conditions de conservation ********************************
                search_start = False
                for line in lines:
                    if search_start:
                        x = re.findall(".*    (.*)", line)
                        if x:
                            ledict['16-Conditions de conservation']=x[0].strip()
                        break
                    x = re.findall("Conditions de conservation", line)
                    if x:
                        search_start=True
                #**************************************************************

                #** OGM / Ionisation ********************************
                search_start = False
                for line in lines:
                    if search_start:
                        ledict['17-OGM / Ionisation']=line.strip()
                        break
                    x = re.findall("OGM / Ionisation", line)
                    if x:
                        search_start=True
                #**************************************************************
                
                #** Recherche Description  ************************************
                search_start = search_end = False
                descriptions=[]
                for line in lines:
                    if search_start:
                        x = re.findall("Caractéristiques nutritionnelles", line)
                        if x:
                            search_end=True
                    if search_start and not search_end:
                        description = line.strip()
                        if description!='':
                            descriptions.append(description)
                    if not search_end:
                        x = re.findall("Description & caractéristiques organoleptiques", line)
                        if x:
                            search_start=True
                ledict['18-Description']='\n'.join(descriptions)
                #**************************************************************

                #** Résultat final ********************************************
                resultat=[]
                sorted_dict = dict(sorted(ledict.items())) 
                if sorted_dict:
                    for key in sorted_dict:
                        x = "%s : %s"%(key.ljust(30), sorted_dict[key])
                        resultat.append(x)
                obj.is_fiche_technique_import = '\n'.join(resultat)
                #**************************************************************

                #** Enregistrement des données ********************************
                obj.is_mis_a_jour_le = datetime.today()
                obj.is_type_conditionnement = sorted_dict.get("01-Conditionnement")
                obj.is_poids_brut           = sorted_dict.get("01-Poids brut")
                obj.no_agrement_sanitaire   = sorted_dict.get("02-N° d'agrément")
                obj.is_ingredient_import    = sorted_dict.get("14-Ingrédients")
                obj.is_allergene_import     = sorted_dict.get("15-Allergènes")
                obj.temperature_stock       = sorted_dict.get("16-Conditions de conservation")
                obj.is_ogm_ionisation       = sorted_dict.get("17-OGM / Ionisation")
                obj.degustation             = sorted_dict.get("18-Description")
                #**************************************************************

                #** Caractéristiques nutritionnelles **************************
                obj.is_valeur_nutritionnelle_ids.unlink()
                obj.add_valeur_nutritionnelle('Valeur Énergétique'      , sorted_dict.get("03-Energie"))
                obj.add_valeur_nutritionnelle('Matières Grasses'        , sorted_dict.get("04-Matières Grasses"))
                obj.add_valeur_nutritionnelle('Dont Acides gras saturés', sorted_dict.get("05-Dont Acides gras saturés"))
                obj.add_valeur_nutritionnelle('Glucides'                , sorted_dict.get("06-Glucides"))
                obj.add_valeur_nutritionnelle('Dont Sucres'             , sorted_dict.get("07-Dont Sucres"))
                obj.add_valeur_nutritionnelle('Protéines'               , sorted_dict.get("08-Protéines"))
                obj.add_valeur_nutritionnelle('Sel'                     , sorted_dict.get("09-Sel"))
                #**************************************************************

                #** Germes ****************************************************
                obj.is_germe_ids.unlink()
                obj.add_germe('Listeria monocytogenes', sorted_dict.get("10-Listeria"))
                obj.add_germe('Salmonella'            , sorted_dict.get("11-Salmonelle"))
                obj.add_germe('Escherichia coli'      , sorted_dict.get("12-Escherichia coli"))
                obj.add_germe('Staphylocoques'        , sorted_dict.get("13-Staphylocoques"))
                #**************************************************************



    def add_valeur_nutritionnelle(self,name,valeur):
        for obj in self:
            lines = self.env['is.valeur.nutritionnelle'].search([('name', '=' , name)], limit=1)
            for line in lines:
                vals={
                    'product_id': obj.id,
                    'valeur_id' : line.id,
                    'valeur'    : valeur
                }
                self.env['is.valeur.nutritionnelle.line'].create(vals)


    def add_germe(self,name,critere):
        for obj in self:
            lines = self.env['is.germe'].search([('name', '=' , name)], limit=1)
            for line in lines:
                vals={
                    'product_id': obj.id,
                    'germe_id'  : line.id,
                    'critere'   : critere
                }
                self.env['is.germe.line'].create(vals)


    def regex_extract(self,ledict,key,txt,regex_start,regex_end):
        "retourne dans dict la chaine trouvée entre 2 expressions régulières"
        v = re.search(regex_start, txt)  # Recherche la première occurence de regex_start
        res=False
        if v:
            txt2 = txt[v.end():].strip()
            if regex_end:
                v = re.search(regex_end, txt2)      # Recherche la première occurence de '    '
                if v:
                    res= txt2[0:v.start()].strip()
            else:
                res = txt2
        if res:
            ledict[key]=res
        return ledict


    def _get_rows_sql(self):
        cr = self._cr
        for obj in self:
            sql="""
                SELECT  
                    sm.id,
                    sm.sale_line_id,
                    sm.purchase_line_id
                FROM stock_move sm join product_product pp on sm.product_id=pp.id
                WHERE sm.state not in ('done','cancel') 
                    and pp.product_tmpl_id=%s
            """
            cr.execute(sql,[obj.id])
            rows = cr.dictfetchall()
            return rows


    def lignes_commandes_action(self):
        for obj in self:
            ids=[]
            rows = obj._get_rows_sql()
            for row in rows:
                ids.append(row['sale_line_id'])
            res= {
                'name': 'Lignes cde',
                'view_mode': 'tree,form',
                'view_type': 'form',
                'res_model': 'is.sale.order.line',
                'type': 'ir.actions.act_window',
                'domain': [
                    ('id','in',ids),
                ],
            }
            return res
           

    def mouvements_stock_action(self):
        cr = self._cr
        for obj in self:
            ids=[]
            rows = obj._get_rows_sql()
            for row in rows:
                ids.append(row['id'])
            dummy, view_id = self.env['ir.model.data'].get_object_reference('stock', 'view_move_tree')
            res= {
                'name': 'Mouvements',
                'view_mode': 'tree,form',
                'view_type': 'form',
                'views': [[view_id, "tree"], [False, "form"]],
                'res_model': 'stock.move',
                'type': 'ir.actions.act_window',
                'domain': [
                    ('id','in',ids),
                ],
            }
            return res




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
        # Log de la langue par défaut avant modification
        lang_before = self.env.context.get('lang', 'Non définie')
        _logger.info("update_pricelist_ir_cron : Langue du contexte par défaut : %s", lang_before)
        
        # Forcer le contexte fr_FR pour que le search utilise les noms traduits
        self = self.with_context(lang='fr_FR')
        
        # Log de la langue après modification
        lang_after = self.env.context.get('lang', 'Non définie')
        _logger.info("update_pricelist_ir_cron : Langue du contexte après with_context : %s", lang_after)
        
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
                                product.product_variant_ids.update_pricelist(product_tmpl_id=product.id)

                #**************************************************************

                items = self.env['product.pricelist.item'].search([('pricelist_id'   ,'=',pricelist.id)])
                nb3=len(items)
                #**************************************************************


    def update_pricelist(self, product_tmpl_id=False, pricelist=False):
        # Forcer le contexte fr_FR pour que le search utilise les noms traduits
        self = self.with_context(lang='fr_FR')
        prices = _PRICELISTS
        if pricelist:
            prices={pricelist: _PRICELISTS[pricelist]}

        for key in prices:
            name = prices[key]
            pricelists = self.env['product.pricelist'].search([('name', '=', name)], limit=1)
            if pricelists:
                pricelist = pricelists[0]




            else:
                vals={
                    'name': name
                }
                pricelist = self.env['product.pricelist'].create(vals)
            if pricelist:
                field_name = "is_prix_vente_actuel_%s"%key
                # filtre=[
                #     (field_name, '>', 0)
                # ]
                filtre=[]
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
                        if product.product_tmpl_id.active==False or price==0:
                            item.unlink()
                            item=False
                    if not item and product.product_tmpl_id.active and price>0:
                        vals={
                            'pricelist_id'   : pricelist.id,
                            'product_tmpl_id': product.product_tmpl_id.id,
                            'applied_on'     : '1_product',
                            'fixed_price'    : price,
                        }
                        item = self.env['product.pricelist.item'].create(vals)

                        _logger.info("update_pricelist:create : %s (id=%s) : %s/%s : %s : %s"%(key, pricelist.id,ct,nb,product.default_code,price))



                    if item:
                        item.fixed_price = price
                        _logger.info("update_pricelist : %s (id=%s) : %s/%s : %s : %s"%(key, pricelist.id,ct,nb,product.default_code,price))
                    ct+=1



    def get_product_pricelist(self,pricelist):
        """
        Récupère le prix d'un produit pour une liste de prix donnée.
        Gère correctement les listes de prix basées sur des remises globales ou d'autres listes de prix.
        """
        price=0
        if pricelist:
            # Utilise la méthode standard d'Odoo pour calculer le prix
            # Cela gère automatiquement les listes de prix basées sur d'autres listes de prix
            price = pricelist.get_product_price(
                product=self,
                quantity=1.0,
                partner=None,
                date=False,
                uom_id=False
            )
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
