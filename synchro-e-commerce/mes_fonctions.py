#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fonctions communes pour la synchronisation entre Odoo principal et e-commerce
"""

import xmlrpc.client
import os
import random
from datetime import datetime, timedelta


# =============================================================================
# CONFIGURATION
# =============================================================================

def read_config():
    """Lire la configuration depuis config.py"""
    from config import get_config
    return get_config()


# =============================================================================
# CONNEXION ODOO
# =============================================================================

def connect_odoo(server_config):
    """Connexion à un serveur Odoo"""
    common = xmlrpc.client.ServerProxy(f'{server_config["url"]}/xmlrpc/2/common')
    models = xmlrpc.client.ServerProxy(f'{server_config["url"]}/xmlrpc/2/object')
    
    # Authentification
    uid = common.authenticate(
        server_config['database'], 
        server_config['username'], 
        server_config['password'], 
        {}
    )
    
    if not uid:
        raise Exception(f"Échec de l'authentification sur {server_config['url']}")
    
    return models, server_config['database'], uid, server_config['password']


# =============================================================================
# UTILITAIRES DE DATE
# =============================================================================

def parse_odoo_date(date_string):
    """Convertir une date Odoo en datetime Python"""
    if not date_string:
        return None
    
    try:
        return datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            return datetime.strptime(date_string, '%Y-%m-%d')
        except ValueError:
            print(f"Erreur lors de la conversion de la date : {date_string}")
            return None


def should_force_update(odoo_date_str, force_days):
    """Vérifier si un article doit être mis à jour de force selon sa date de modification"""
    if force_days == 0:
        return False
    
    odoo_date = parse_odoo_date(odoo_date_str)
    if not odoo_date:
        return False
    
    # Calculer la date limite (maintenant - X jours)
    cutoff_date = datetime.now() - timedelta(days=force_days)
    
    # Retourner True si la date Odoo est plus récente que la date limite
    return odoo_date > cutoff_date


# =============================================================================
# UTILITAIRES D'IMAGE
# =============================================================================

def get_image_size(image_data):
    """Calculer la taille d'une image en base64"""
    if not image_data:
        return 0
    # Taille en base64 * 0.75 pour avoir la taille réelle en bytes
    return len(image_data) * 3 // 4


def format_size(size_bytes):
    """Formater la taille en KB ou MB"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


# =============================================================================
# RECHERCHE DE PRODUITS
# =============================================================================

def find_product_by_code(models, database, uid, password, default_code):
    """Rechercher un produit par sa référence (default_code)"""
    if not default_code:
        return None
    
    products = models.execute_kw(
        database, uid, password,
        'product.product', 'search_read',
        [[['default_code', '=', default_code]]],
        {'fields': ['id', 'product_tmpl_id', 'write_date'], 'limit': 1}
    )
    
    return products[0] if products else None


def find_product_template_by_code(models, database, uid, password, default_code):
    """Rechercher un produit template par sa référence"""
    if not default_code:
        return None
    
    # Chercher d'abord dans product.product
    products = models.execute_kw(
        database, uid, password,
        'product.product', 'search_read',
        [[['default_code', '=', default_code]]],
        {'fields': ['id', 'product_tmpl_id'], 'limit': 1}
    )
    
    if products and products[0].get('product_tmpl_id'):
        return products[0]['product_tmpl_id'][0]
    
    return None


def get_product_code(models, database, uid, password, product_id, is_template=False):
    """Récupérer la référence d'un produit"""
    if not product_id:
        return None
    
    model = 'product.template' if is_template else 'product.product'
    
    products = models.execute_kw(
        database, uid, password,
        model, 'read',
        [[product_id]],
        {'fields': ['default_code']}
    )
    
    return products[0].get('default_code') if products else None


def get_product_by_id(models, database, uid, password, product_id, is_template=True):
    """Récupérer un produit par son ID avec tous les champs de base"""
    if not product_id:
        return None
    
    model = 'product.template' if is_template else 'product.product'
    
    fields = ['id', 'name', 'default_code', 'list_price', 'categ_id', 'type', 
              'active', 'write_date', 'description']
    
    if is_template:
        # Ajouter les champs spécifiques aux templates
        fields.extend(['milk_type_ids', 'is_region_id', 'traitement_thermique'])
    
    try:
        products = models.execute_kw(
            database, uid, password,
            model, 'read',
            [[product_id]],
            {'fields': fields, 'context': {'lang': 'fr_FR'}}
        )
        
        return products[0] if products else None
    except Exception as e:
        print(f"Erreur lors de la récupération du produit {product_id}: {e}")
        return None


def get_product_image(models, database, uid, password, product_id):
    """Récupérer l'image d'un produit spécifique"""
    try:
        product_data = models.execute_kw(
            database, uid, password,
            'product.template', 'read',
            [[product_id]],
            {
                'fields': ['image_1920'],
                'context': {'lang': 'fr_FR'}
            }
        )
        
        if product_data and product_data[0].get('image_1920'):
            return product_data[0]['image_1920']
        
    except Exception as e:
        print(f"Erreur lors de la récupération de l'image pour le produit {product_id}: {e}")
    
    return None


# =============================================================================
# RECHERCHE DE CATÉGORIES
# =============================================================================

def find_category_by_name(models, database, uid, password, category_name):
    """Rechercher une catégorie de produits par son nom"""
    if not category_name:
        return None
    
    categories = models.execute_kw(
        database, uid, password,
        'product.category', 'search_read',
        [[['name', '=', category_name]]],
        {'fields': ['id', 'name'], 'limit': 1}
    )
    
    return categories[0]['id'] if categories else None


def find_category_by_complete_name(models, database, uid, password, complete_name):
    """Rechercher une catégorie de produits par son nom complet (hiérarchie)"""
    if not complete_name:
        return None
    
    categories = models.execute_kw(
        database, uid, password,
        'product.category', 'search_read',
        [[['complete_name', '=', complete_name]]],
        {'fields': ['id', 'name', 'complete_name'], 'limit': 1}
    )
    
    return categories[0]['id'] if categories else None


def get_category_complete_name(models, database, uid, password, category_id):
    """Récupérer le nom complet d'une catégorie"""
    if not category_id:
        return None
    
    categories = models.execute_kw(
        database, uid, password,
        'product.category', 'read',
        [[category_id]],
        {'fields': ['complete_name']}
    )
    
    return categories[0].get('complete_name') if categories else None


def find_public_category_by_name(models, database, uid, password, name):
    """Rechercher une catégorie publique par son nom"""
    if not name:
        return None
    
    categories = models.execute_kw(
        database, uid, password,
        'product.public.category', 'search_read',
        [[['name', '=', name]]],
        {'fields': ['id', 'name', 'write_date'], 'limit': 1}
    )
    
    return categories[0] if categories else None


def get_public_category_ids_by_names(models, database, uid, password, category_names):
    """Récupérer les IDs des catégories publiques à partir de leurs noms"""
    if not category_names:
        return []
    
    categories = models.execute_kw(
        database, uid, password,
        'product.public.category', 'search_read',
        [[['name', 'in', category_names]]],
        {
            'fields': ['id', 'name'],
            'context': {'lang': 'fr_FR'}
        }
    )
    
    return [cat['id'] for cat in categories]


# =============================================================================
# RECHERCHE DE DEVISES
# =============================================================================

def find_currency_by_name(models, database, uid, password, currency_name):
    """Rechercher une devise par son nom"""
    if not currency_name:
        return None
    
    currencies = models.execute_kw(
        database, uid, password,
        'res.currency', 'search_read',
        [[['name', '=', currency_name]]],
        {'fields': ['id', 'name'], 'limit': 1}
    )
    
    return currencies[0]['id'] if currencies else None


# =============================================================================
# RECHERCHE DE LISTES DE PRIX
# =============================================================================

def find_pricelist_by_name(models, database, uid, password, name):
    """Rechercher une liste de prix par son nom"""
    if not name:
        return None
    
    pricelists = models.execute_kw(
        database, uid, password,
        'product.pricelist', 'search_read',
        [[['name', '=', name]]],
        {'fields': ['id', 'name', 'write_date', 'currency_id'], 'limit': 1}
    )
    
    return pricelists[0] if pricelists else None


def get_pricelist_name(models, database, uid, password, pricelist_id):
    """Récupérer le nom d'une liste de prix"""
    if not pricelist_id:
        return None
    
    pricelists = models.execute_kw(
        database, uid, password,
        'product.pricelist', 'read',
        [[pricelist_id]],
        {'fields': ['name']}
    )
    
    return pricelists[0].get('name') if pricelists else None


# =============================================================================
# TYPES DE LAIT ET RÉGIONS
# =============================================================================

def get_milk_type_names_by_ids(models, database, uid, password, milk_type_ids):
    """Récupérer les noms des types de lait à partir de leurs IDs"""
    if not milk_type_ids:
        return []
    
    milk_types = models.execute_kw(
        database, uid, password,
        'milk.type', 'search_read',
        [[['id', 'in', milk_type_ids]]],
        {
            'fields': ['name'],
            'context': {'lang': 'fr_FR'}
        }
    )
    
    return [mt['name'] for mt in milk_types]


def get_region_name_by_id(models, database, uid, password, region_id):
    """Récupérer le nom de la région d'origine à partir de son ID"""
    if not region_id:
        return None
    
    regions = models.execute_kw(
        database, uid, password,
        'is.region.origine', 'search_read',
        [[['id', '=', region_id]]],
        {
            'fields': ['name'],
            'context': {'lang': 'fr_FR'}
        }
    )
    
    return regions[0]['name'] if regions else None


# =============================================================================
# TAGS PRODUITS
# =============================================================================

def find_or_create_product_tag(models, database, uid, password, tag_name):
    """Trouver ou créer un tag produit par son nom"""
    if not tag_name:
        return None
    
    # Chercher si le tag existe déjà
    existing_tags = models.execute_kw(
        database, uid, password,
        'product.tag', 'search_read',
        [[['name', '=', tag_name]]],
        {'fields': ['id', 'name'], 'limit': 1}
    )
    
    if existing_tags:
        return existing_tags[0]['id']
    
    # Créer le tag s'il n'existe pas
    try:
        new_tag_id = models.execute_kw(
            database, uid, password,
            'product.tag', 'create',
            [{'name': tag_name}],
            {'context': {'lang': 'fr_FR'}}
        )
        return new_tag_id
    except Exception as e:
        print(f"Erreur lors de la création du tag '{tag_name}': {e}")
        return None


# =============================================================================
# CRÉATION DE PRODUIT E-COMMERCE
# =============================================================================

def prepare_product_data(product, update_images=True):
    """Préparer les données du produit pour création/mise à jour"""
    # Mapper les types de produits entre les versions d'Odoo
    type_mapping = {
        'product': 'consu',  # Produit stockable -> Consommable
        'consu': 'consu',    # Consommable -> Consommable
        'service': 'service' # Service -> Service
    }
    
    product_type = product.get('type', 'consu')
    mapped_type = type_mapping.get(product_type, 'consu')
    
    data = {
        'name': product['name'],
        'default_code': product.get('default_code'),
        'list_price': 0,
        'type': mapped_type,
        'active': product.get('active', True),
        'description': product.get('description', ''),
        'is_published': True,
        'website_ribbon_id': random.randint(1, 4)
    }
    
    return data


def create_product_on_ecommerce(product, 
                                 ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
                                 main_models, main_database, main_uid, main_password,
                                 update_images=True, verbose=True):
    """
    Créer un produit sur l'e-commerce à partir des données du produit source.
    
    Args:
        product: dict avec les données du produit source (ou au minimum 'default_code')
        ecommerce_*: connexion e-commerce
        main_*: connexion Odoo principal
        update_images: bool pour inclure les images
        verbose: bool pour afficher les messages
    
    Returns:
        int: ID du template créé, ou None en cas d'erreur
    """
    if not product.get('default_code'):
        if verbose:
            print(f"    ⚠ Pas de référence produit fournie")
        return None
    
    # Si on n'a qu'un default_code, récupérer les infos complètes
    if 'name' not in product:
        default_code = product['default_code']
        
        # D'abord chercher dans product.product (car default_code est sur les variantes)
        source_variants = main_models.execute_kw(
            main_database, main_uid, main_password,
            'product.product', 'search_read',
            [[['default_code', '=', default_code]]],
            {
                'fields': ['id', 'product_tmpl_id', 'default_code'],
                'context': {'lang': 'fr_FR'},
                'limit': 1
            }
        )
        
        if source_variants and source_variants[0].get('product_tmpl_id'):
            # Récupérer le template complet
            tmpl_id = source_variants[0]['product_tmpl_id'][0]
            source_products = main_models.execute_kw(
                main_database, main_uid, main_password,
                'product.template', 'search_read',
                [[['id', '=', tmpl_id]]],
                {
                    'fields': ['id', 'name', 'default_code', 'list_price', 'categ_id', 'type', 
                              'active', 'write_date', 'description', 'milk_type_ids', 
                              'is_region_id', 'traitement_thermique'],
                    'context': {'lang': 'fr_FR'},
                    'limit': 1
                }
            )
            if source_products:
                product = source_products[0]
                # S'assurer que le default_code est bien défini
                if not product.get('default_code'):
                    product['default_code'] = default_code
            else:
                if verbose:
                    print(f"    ⚠ Template ID {tmpl_id} non trouvé pour '{default_code}'")
                return None
        else:
            # Fallback: essayer directement sur product.template (au cas où)
            source_products = main_models.execute_kw(
                main_database, main_uid, main_password,
                'product.template', 'search_read',
                [[['default_code', '=', default_code]]],
                {
                    'fields': ['id', 'name', 'default_code', 'list_price', 'categ_id', 'type', 
                              'active', 'write_date', 'description', 'milk_type_ids', 
                              'is_region_id', 'traitement_thermique'],
                    'context': {'lang': 'fr_FR'},
                    'limit': 1
                }
            )
            
            if not source_products:
                if verbose:
                    print(f"    ℹ Produit '{default_code}' ignoré (non trouvé ou archivé dans la source)")
                return None
            
            product = source_products[0]
    
    # Récupérer les catégories publiques correspondantes aux milk_type_ids
    public_categ_ids = []
    category_names = []
    
    if product.get('milk_type_ids'):
        milk_type_names = get_milk_type_names_by_ids(
            main_models, main_database, main_uid, main_password, 
            product['milk_type_ids']
        )
        category_names.extend(milk_type_names)
    
    if category_names:
        public_categ_ids = get_public_category_ids_by_names(
            ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
            category_names
        )
    
    # Récupérer les tags produits
    product_tag_ids = []
    tag_names = []
    
    # Types de lait
    if product.get('milk_type_ids'):
        milk_type_names = get_milk_type_names_by_ids(
            main_models, main_database, main_uid, main_password, 
            product['milk_type_ids']
        )
        for milk_type_name in milk_type_names:
            tag_names.append(f"Type {milk_type_name}")
    
    # Traitement thermique
    if product.get('traitement_thermique'):
        traitement_mapping = {
            'laitcru': 'Lait Cru',
            'laitthermise': 'Lait Thermisé',
            'laitpasteurisé': 'Lait Pasteurisé'
        }
        traitement_name = traitement_mapping.get(product['traitement_thermique'], product['traitement_thermique'])
        tag_names.append(f"Traitement Thermique {traitement_name}")
    
    # Région d'origine
    if product.get('is_region_id'):
        region_id = product['is_region_id'][0] if isinstance(product['is_region_id'], list) else product['is_region_id']
        region_name = get_region_name_by_id(
            main_models, main_database, main_uid, main_password, 
            region_id
        )
        if region_name:
            tag_names.append(f"Région {region_name}")
    
    # Créer/récupérer les tags
    for tag_name in tag_names:
        tag_id = find_or_create_product_tag(
            ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password, 
            tag_name
        )
        if tag_id:
            product_tag_ids.append(tag_id)
    
    # Préparer les données
    product_data = prepare_product_data(product, update_images)
    product_data['public_categ_ids'] = [(6, 0, public_categ_ids)]
    product_data['product_tag_ids'] = [(6, 0, product_tag_ids)]
    
    # Ajouter l'image si nécessaire
    if update_images:
        product_image = get_product_image(main_models, main_database, main_uid, main_password, product['id'])
        if product_image:
            product_data['image_1920'] = product_image
    
    try:
        new_template_id = ecommerce_models.execute_kw(
            ecommerce_database, ecommerce_uid, ecommerce_password,
            'product.template', 'create', [product_data],
            {'context': {'lang': 'fr_FR'}}
        )
        
        if verbose:
            print(f"    ✓ Produit '{product['default_code']}' créé sur e-commerce (ID: {new_template_id})")
        
        return new_template_id
        
    except Exception as e:
        if verbose:
            print(f"    ✗ Erreur création produit '{product['default_code']}': {e}")
        return None
