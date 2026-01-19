#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de synchronisation des articles entre Odoo principal et e-commerce via XML-RPC
"""

import sys
import os
import random
import re
from datetime import datetime, timedelta

# Import des fonctions communes
from mes_fonctions import (
    read_config,
    connect_odoo,
    parse_odoo_date,
    should_force_update,
    get_image_size,
    format_size,
    find_product_by_code,
    get_product_image,
    get_milk_type_names_by_ids,
    get_region_name_by_id,
    get_public_category_ids_by_names,
    find_or_create_product_tag,
    find_public_category_by_name,
    prepare_product_data,
)


def get_products(models, database, uid, password, limit=None):
    """Récupérer la liste des articles depuis Odoo"""
    print("Récupération des articles depuis Odoo...")
    
    # Utiliser search_read pour une requête plus efficace
    domain = []
    # Exclure image_1920 de la récupération initiale pour éviter les erreurs de parsing XML
    fields = ['id', 'name', 'default_code', 'list_price', 'categ_id', 'type', 'active', 'write_date', 'milk_type_ids', 'is_region_id', 'traitement_thermique']
    
    search_params = {
        'fields': fields,
        'context': {'lang': 'fr_FR'}  # Récupérer les noms en français
    }
    
    if limit:
        search_params['limit'] = limit
    
    try:
        products = models.execute_kw(
            database, uid, password,
            'product.template', 'search_read',
            [domain],
            search_params
        )
        
        print(f"Nombre d'articles récupérés: {len(products)}")
        return products
        
    except Exception as e:
        print(f"Erreur lors de la récupération des articles: {e}")
        print("Tentative avec une limite réduite...")
        
        # Réessayer avec une limite plus petite si pas de limite définie
        if not limit:
            search_params['limit'] = 100
        elif limit > 100:
            search_params['limit'] = min(100, limit // 2)
        else:
            search_params['limit'] = 50
            
        try:
            products = models.execute_kw(
                database, uid, password,
                'product.template', 'search_read',
                [domain],
                search_params
            )
            
            print(f"Nombre d'articles récupérés (limite réduite): {len(products)}")
            return products
            
        except Exception as e2:
            print(f"Erreur persistante lors de la récupération: {e2}")
            return []


def get_milk_types(models, database, uid, password):
    """Récupérer la liste des types de lait depuis Odoo"""
    print("Récupération des types de lait depuis Odoo...")
    
    # Utiliser search_read pour récupérer les milk.type
    fields = ['id', 'name', 'logo', 'description', 'write_date']
    
    milk_types = models.execute_kw(
        database, uid, password,
        'milk.type', 'search_read',
        [[]],
        {
            'fields': fields,
            'context': {'lang': 'fr_FR'}
        }
    )
    
    print(f"Nombre de types de lait récupérés: {len(milk_types)}")
    return milk_types


def get_regions_origine(models, database, uid, password):
    """Récupérer la liste des régions d'origine depuis Odoo"""
    print("Récupération des régions d'origine depuis Odoo...")
    
    # Utiliser search_read pour récupérer les is.region.origine
    fields = ['id', 'name', 'write_date']
    
    regions = models.execute_kw(
        database, uid, password,
        'is.region.origine', 'search_read',
        [[]],
        {
            'fields': fields,
            'context': {'lang': 'fr_FR'}
        }
    )
    
    print(f"Nombre de régions d'origine récupérées: {len(regions)}")
    return regions


def sync_milk_type_to_public_category(milk_type, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password):
    """Synchroniser un type de lait vers une catégorie publique"""
    if not milk_type.get('name'):
        return False
    
    # Chercher si la catégorie publique existe déjà
    existing_category = find_public_category_by_name(
        ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
        milk_type['name']
    )
    
    # Préparer les données de la catégorie
    category_data = {
        'name': milk_type['name'],
        'website_description': milk_type.get('description', '')
    }
    
    # Ajouter l'image si elle existe
    if milk_type.get('logo'):
        category_data['image'] = milk_type['logo']
    
    if existing_category:
        # Mettre à jour la catégorie existante
        try:
            result = ecommerce_models.execute_kw(
                ecommerce_database, ecommerce_uid, ecommerce_password,
                'product.public.category', 'write', 
                [[existing_category['id']], category_data],
                {'context': {'lang': 'fr_FR'}}
            )
            
            if result:
                status = "✓ Mise à jour"
                image_info = " (avec image)" if milk_type.get('logo') else ""
                print(f"Type lait: {milk_type['name']:<30} {status}{image_info}")
                return True
            else:
                print(f"Type lait: {milk_type['name']:<30} ✗ Échec mise à jour")
                return False
                
        except Exception as e:
            print(f"Type lait: {milk_type['name']:<30} ✗ Erreur mise à jour: {e}")
            return False
    else:
        # Créer une nouvelle catégorie
        try:
            new_category_id = ecommerce_models.execute_kw(
                ecommerce_database, ecommerce_uid, ecommerce_password,
                'product.public.category', 'create', [category_data],
                {'context': {'lang': 'fr_FR'}}
            )
            
            status = f"✓ Création (ID: {new_category_id})"
            image_info = " (avec image)" if milk_type.get('logo') else ""
            print(f"Type lait: {milk_type['name']:<30} {status}{image_info}")
            return True
            
        except Exception as e:
            print(f"Type lait: {milk_type['name']:<30} ✗ Erreur création: {e}")
            return False


def sync_region_to_public_category(region, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password):
    """Synchroniser une région d'origine vers une catégorie publique"""
    if not region.get('name'):
        return False
    
    # Chercher si la catégorie publique existe déjà
    existing_category = find_public_category_by_name(
        ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
        region['name']
    )
    
    # Préparer les données de la catégorie
    category_data = {
        'name': region['name'],
        'website_description': f"Produits de la région: {region['name']}"
    }
    
    if existing_category:
        # Mettre à jour la catégorie existante
        try:
            result = ecommerce_models.execute_kw(
                ecommerce_database, ecommerce_uid, ecommerce_password,
                'product.public.category', 'write', 
                [[existing_category['id']], category_data],
                {'context': {'lang': 'fr_FR'}}
            )
            
            if result:
                print(f"Région: {region['name']:<30} ✓ Mise à jour")
                return True
            else:
                print(f"Région: {region['name']:<30} ✗ Échec mise à jour")
                return False
                
        except Exception as e:
            print(f"Région: {region['name']:<30} ✗ Erreur mise à jour: {e}")
            return False
    else:
        # Créer une nouvelle catégorie
        try:
            new_category_id = ecommerce_models.execute_kw(
                ecommerce_database, ecommerce_uid, ecommerce_password,
                'product.public.category', 'create', [category_data],
                {'context': {'lang': 'fr_FR'}}
            )
            
            print(f"Région: {region['name']:<30} ✓ Création (ID: {new_category_id})")
            return True
            
        except Exception as e:
            print(f"Région: {region['name']:<30} ✗ Erreur création: {e}")
            return False


def create_product(models, database, uid, password, product_data):
    """Créer un nouveau produit"""
    return models.execute_kw(
        database, uid, password,
        'product.product', 'create', [product_data]
    )


def update_product(models, database, uid, password, product_id, product_data):
    """Mettre à jour un produit existant"""
    try:
        return models.execute_kw(
            database, uid, password,
            'product.product', 'write', [[product_id], product_data]
        )
    except Exception as e:
        print(f"    Erreur lors de la mise à jour: {e}")
        return False


def format_product_log(product, status, current_index=1, total_count=1, extra_info=""):
    """Formater l'affichage d'un produit avec compteur et alignement amélioré pour toutes les colonnes"""
    counter = f"[{current_index:3d}/{total_count:3d}]"
    code = product.get('default_code', 'N/A')
    name = product.get('name', 'N/A')[:30]
    
    # Analyser extra_info pour extraire et aligner les colonnes
    if extra_info:
        # Extraire les informations structurées
        
        # Extraire image info
        image_match = re.search(r'\(image: ([^)]+)\)', extra_info)
        image_info = image_match.group(1) if image_match else "N/A"
        
        # Extraire catég info
        categ_match = re.search(r'\(catég: (\d+)\)', extra_info)
        categ_info = categ_match.group(1) if categ_match else "0"
        
        # Extraire tags info
        tags_match = re.search(r'\(tags: (\d+)\)', extra_info)
        tags_info = tags_match.group(1) if tags_match else "0"
        
        # Extraire Odoo date
        odoo_match = re.search(r'\(Odoo: ([^)]+)\)', extra_info)
        odoo_info = odoo_match.group(1) if odoo_match else "N/A"
        
        # Formater avec alignement fixe
        formatted_extra = f" (image: {image_info:<8}) (catég: {categ_info:<2}) (tags: {tags_info:<2}) (Odoo: {odoo_info})"
        
        return f"{counter} {code:<15} {name:<30} {status}{formatted_extra}"
    else:
        return f"{counter} {code:<15} {name:<30} {status}"


def sync_product_to_ecommerce(product, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password, main_models, main_database, main_uid, main_password, force_days=0, update_images=True, current_index=1, total_count=1):
    """Synchroniser un produit vers l'e-commerce avec vérification de date et synchronisation des catégories publiques"""
    if not product.get('default_code'):
        return False
    
    # Chercher si le produit existe déjà
    existing_product = find_product_by_code(
        ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
        product['default_code']
    )
    
    # Si le produit existe, comparer les dates de modification
    if existing_product:
        odoo_date = parse_odoo_date(product.get('write_date'))
        ecommerce_date = parse_odoo_date(existing_product.get('write_date'))
        
        odoo_date_str = product.get('write_date', 'N/A')
        ecommerce_date_str = existing_product.get('write_date', 'N/A')
        
        # Vérifier si on doit forcer la mise à jour
        force_update = should_force_update(odoo_date_str, force_days)
        
        if not force_update and odoo_date and ecommerce_date and odoo_date <= ecommerce_date:
            # Pas de mise à jour forcée ET l'e-commerce est plus récent ou égal
            status = f"✓ Déjà à jour (Odoo: {odoo_date_str}, E-com: {ecommerce_date_str})"
            print(format_product_log(product, status, current_index, total_count))
            return True
        
        # Préparer le message de raison pour la mise à jour
        if force_update:
            reason = f"Forcé (récent: {force_days}j)"
        else:
            reason = "Mise à jour"
    else:
        # Nouveau produit à créer
        reason = "Création"
        odoo_date_str = product.get('write_date', 'N/A')
    
    # Récupérer les catégories publiques correspondantes aux milk_type_ids
    public_categ_ids = []
    category_names = []
    
    # Ajouter les types de lait aux catégories publiques
    if product.get('milk_type_ids'):
        # Récupérer les noms des types de lait
        milk_type_names = get_milk_type_names_by_ids(
            main_models, main_database, main_uid, main_password, 
            product['milk_type_ids']
        )
        category_names.extend(milk_type_names)
    
    # Récupérer les IDs des catégories publiques correspondantes
    if category_names:
        public_categ_ids = get_public_category_ids_by_names(
            ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
            category_names
        )
    
    # Récupérer les tags produits correspondants à traitement_thermique, is_region_id et milk_type_ids
    product_tag_ids = []
    tag_names = []
    
    # Ajouter les types de lait aux tags avec préfixe
    if product.get('milk_type_ids'):
        # Récupérer les noms des types de lait
        milk_type_names = get_milk_type_names_by_ids(
            main_models, main_database, main_uid, main_password, 
            product['milk_type_ids']
        )
        for milk_type_name in milk_type_names:
            type_with_prefix = f"Type {milk_type_name}"
            tag_names.append(type_with_prefix)
    
    # Ajouter traitement_thermique aux tags avec préfixe
    if product.get('traitement_thermique'):
        # Convertir la valeur de sélection en nom lisible
        traitement_mapping = {
            'laitcru': 'Lait Cru',
            'laitthermise': 'Lait Thermisé',
            'laitpasteurisé': 'Lait Pasteurisé'
        }
        traitement_name = traitement_mapping.get(product['traitement_thermique'], product['traitement_thermique'])
        traitement_with_prefix = f"Traitement Thermique {traitement_name}"
        tag_names.append(traitement_with_prefix)
    
    # Ajouter la région d'origine aux tags avec préfixe  
    if product.get('is_region_id'):
        # is_region_id est un Many2one, donc c'est [id, nom] ou juste id
        region_id = product['is_region_id'][0] if isinstance(product['is_region_id'], list) else product['is_region_id']
        region_name = get_region_name_by_id(
            main_models, main_database, main_uid, main_password, 
            region_id
        )
        if region_name:
            region_with_prefix = f"Région {region_name}"
            tag_names.append(region_with_prefix)
    
    # Créer/récupérer les tags
    if tag_names:
        for tag_name in tag_names:
            tag_id = find_or_create_product_tag(
                ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password, 
                tag_name
            )
            if tag_id:
                product_tag_ids.append(tag_id)
    
    if existing_product:
        # Récupérer l'ID du template
        template_id = existing_product.get('product_tmpl_id', [None])[0] if existing_product.get('product_tmpl_id') else None
        
        if template_id:
            # Préparer les données
            product_data = prepare_product_data(product, update_images)
            
            try:
                # Mettre à jour le template en français
                update_data = {
                    'name': product_data['name'],
                    'list_price': 0,
                    'public_categ_ids': [(6, 0, public_categ_ids)],
                    'is_published': True,
                    'product_tag_ids': [(6, 0, product_tag_ids)],
                    'website_ribbon_id': random.randint(1, 4)
                }
                
                # Ajouter l'image si elle existe et si l'option est activée
                image_info = ""
                if update_images:
                    # Récupérer l'image séparément pour éviter les erreurs de parsing XML
                    product_image = get_product_image(main_models, main_database, main_uid, main_password, product['id'])
                    if product_image:
                        update_data['image_1920'] = product_image
                        image_size = get_image_size(product_image)
                        image_info = f" (image: {format_size(image_size)})"
                    else:
                        image_info = " (image: non trouvée)"
                else:
                    image_info = " (image: ignorée)"
                
                # Info sur les catégories et tags
                categ_info = f" (catég: {len(public_categ_ids)})" if public_categ_ids else ""
                tag_info = f" (tags: {len(product_tag_ids)})" if product_tag_ids else ""
                
                template_result = ecommerce_models.execute_kw(
                    ecommerce_database, ecommerce_uid, ecommerce_password,
                    'product.template', 'write', [[template_id], update_data],
                    {'context': {'lang': 'fr_FR'}}
                )
                
                if template_result:
                    status = f"✓ {reason}"
                    extra_info = f"{image_info}{categ_info}{tag_info} (Odoo: {odoo_date_str})"
                    print(format_product_log(product, status, current_index, total_count, extra_info))
                    return True
                else:
                    status = f"✗ Échec {reason.lower()}"
                    extra_info = f"{image_info}{categ_info}{tag_info} (Odoo: {odoo_date_str})"
                    print(format_product_log(product, status, current_index, total_count, extra_info))
                    return False
                    
            except Exception as e:
                # Afficher la taille de l'image en cas d'erreur
                error_msg = str(e)
                if update_images and product_data.get('image_1920'):
                    image_size = get_image_size(product_data['image_1920'])
                    error_msg += f" (image: {format_size(image_size)})"
                categ_info = f" (catég: {len(public_categ_ids)})" if public_categ_ids else ""
                tag_info = f" (tags: {len(product_tag_ids)})" if product_tag_ids else ""
                status = f"✗ Erreur {reason.lower()}: {error_msg}"
                extra_info = f"{categ_info}{tag_info} (Odoo: {odoo_date_str})"
                print(format_product_log(product, status, current_index, total_count, extra_info))
                return False
        else:
            categ_info = f" (catég: {len(public_categ_ids)})" if public_categ_ids else ""
            tag_info = f" (tags: {len(product_tag_ids)})" if product_tag_ids else ""
            status = f"✗ Template non trouvé pour {reason.lower()}"
            extra_info = f"{categ_info}{tag_info} (Odoo: {odoo_date_str})"
            print(format_product_log(product, status, current_index, total_count, extra_info))
            return False
    else:
        # Créer un nouveau template
        product_data = prepare_product_data(product, update_images)
        
        # Ajouter les catégories publiques
        product_data['public_categ_ids'] = [(6, 0, public_categ_ids)]
        
        # Ajouter les tags produits
        product_data['product_tag_ids'] = [(6, 0, product_tag_ids)]
        
        # Ajouter l'image si nécessaire
        image_info = ""
        if update_images:
            # Récupérer l'image séparément pour éviter les erreurs de parsing XML
            product_image = get_product_image(main_models, main_database, main_uid, main_password, product['id'])
            if product_image:
                product_data['image_1920'] = product_image
                image_size = get_image_size(product_image)
                image_info = f" (image: {format_size(image_size)})"
            else:
                image_info = " (image: non trouvée)"
        else:
            image_info = " (image: ignorée)"
        
        try:
            new_template_id = ecommerce_models.execute_kw(
                ecommerce_database, ecommerce_uid, ecommerce_password,
                'product.template', 'create', [product_data],
                {'context': {'lang': 'fr_FR'}}
            )
            
            # Info sur les catégories et tags
            categ_info = f" (catég: {len(public_categ_ids)})" if public_categ_ids else ""
            tag_info = f" (tags: {len(product_tag_ids)})" if product_tag_ids else ""
            
            status = f"✓ {reason} (ID: {new_template_id})"
            extra_info = f"{image_info}{categ_info}{tag_info} (Odoo: {odoo_date_str})"
            print(format_product_log(product, status, current_index, total_count, extra_info))
            return True
        except Exception as e:
            error_msg = str(e)
            if update_images and product_data.get('image_1920'):
                image_size = get_image_size(product_data['image_1920'])
                error_msg += f" (image: {format_size(image_size)})"
            categ_info = f" (catég: {len(public_categ_ids)})" if public_categ_ids else ""
            tag_info = f" (tags: {len(product_tag_ids)})" if product_tag_ids else ""
            status = f"✗ Erreur {reason.lower()}: {error_msg}"
            extra_info = f"{categ_info}{tag_info} (Odoo: {odoo_date_str})"
            print(format_product_log(product, status, current_index, total_count, extra_info))
            return False


def display_products(products):
    """Afficher les articles"""
    print(f"\n{'='*100}")
    print(f"{'LISTE DES ARTICLES':^100}")
    print(f"{'='*100}")
    print(f"{'ID':<6} {'Référence':<15} {'Nom':<30} {'Prix':<10} {'Catégorie':<20} {'Type':<10} {'Actif'}")
    print(f"{'-'*100}")
    
    for product in products:
        categorie = 'N/A'
        if product.get('categ_id') and isinstance(product['categ_id'], list):
            categorie = product['categ_id'][1]
        
        print(f"{product['id']:<6} {product.get('default_code', 'N/A'):<15} "
              f"{product['name'][:29]:<30} {product.get('list_price', 0.0):<10.2f} "
              f"{categorie[:19]:<20} {product.get('type', 'N/A'):<10} "
              f"{'Oui' if product.get('active', True) else 'Non'}")
    
    print(f"{'-'*100}")
    print(f"Total: {len(products)} articles")


def sort_product_tags_alphabetically(ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password):
    """Trier tous les tags produits par ordre alphabétique en mettant à jour leur séquence"""
    print(f"\n{'='*80}")
    print(f"{'TRI ALPHABÉTIQUE DES TAGS PRODUITS':^80}")
    print(f"{'='*80}")
    
    try:
        # Récupérer tous les tags produits triés par nom
        tags = ecommerce_models.execute_kw(
            ecommerce_database, ecommerce_uid, ecommerce_password,
            'product.tag', 'search_read',
            [[]],  # Domaine vide pour récupérer tous les tags
            {
                'fields': ['id', 'name', 'sequence'],
                'order': 'name asc',  # Tri alphabétique par nom
                'context': {'lang': 'fr_FR'}
            }
        )
        
        if not tags:
            print("Aucun tag produit trouvé.")
            return 0, 0
        
        print(f"Mise à jour de la séquence pour {len(tags)} tags...")
        
        success_count = 0
        error_count = 0
        
        # Mettre à jour la séquence de chaque tag
        for index, tag in enumerate(tags):
            new_sequence = (index + 1) * 10  # Séquence par pas de 10 pour permettre des insertions futures
            
            # Mettre à jour seulement si la séquence a changé
            if tag.get('sequence', 0) != new_sequence:
                try:
                    result = ecommerce_models.execute_kw(
                        ecommerce_database, ecommerce_uid, ecommerce_password,
                        'product.tag', 'write',
                        [[tag['id']], {'sequence': new_sequence}],
                        {'context': {'lang': 'fr_FR'}}
                    )
                    
                    if result:
                        print(f"Tag: {tag['name']:<40} ✓ Séquence: {new_sequence}")
                        success_count += 1
                    else:
                        print(f"Tag: {tag['name']:<40} ✗ Échec mise à jour séquence")
                        error_count += 1
                        
                except Exception as e:
                    print(f"Tag: {tag['name']:<40} ✗ Erreur: {e}")
                    error_count += 1
            else:
                # Séquence déjà correcte, pas de mise à jour nécessaire
                success_count += 1
        
        print(f"{'-'*80}")
        print(f"Résultat tri des tags: {success_count} succès, {error_count} erreurs")
        return success_count, error_count
        
    except Exception as e:
        print(f"Erreur lors du tri des tags: {e}")
        return 0, 1


def synchronize_products(main_products, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password, main_models, main_database, main_uid, main_password, force_days=0, update_images=True):
    """Synchroniser tous les produits vers l'e-commerce"""
    success_count = 0
    error_count = 0
    total_products = len(main_products)
    
    for index, product in enumerate(main_products, 1):
        success = sync_product_to_ecommerce(
            product, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
            main_models, main_database, main_uid, main_password, force_days, update_images,
            index, total_products
        )
        if success:
            success_count += 1
        else:
            error_count += 1
    
    return success_count, error_count


def synchronize_milk_types_to_public_categories(milk_types, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password):
    """Synchroniser tous les types de lait vers les catégories publiques"""
    print(f"\n{'='*80}")
    print(f"{'SYNCHRONISATION DES TYPES DE LAIT':^80}")
    print(f"{'='*80}")
    
    success_count = 0
    error_count = 0
    
    for milk_type in milk_types:
        success = sync_milk_type_to_public_category(
            milk_type, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password
        )
        if success:
            success_count += 1
        else:
            error_count += 1
    
    print(f"{'-'*80}")
    print(f"Résultat types de lait: {success_count} succès, {error_count} erreurs")
    
    return success_count, error_count


def synchronize_regions_to_public_categories(regions, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password):
    """Synchroniser toutes les régions d'origine vers les catégories publiques"""
    print(f"\n{'='*80}")
    title = "SYNCHRONISATION DES RÉGIONS D'ORIGINE"
    print(f"{title:^80}")
    print(f"{'='*80}")
    
    success_count = 0
    error_count = 0
    
    for region in regions:
        success = sync_region_to_public_category(
            region, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password
        )
        if success:
            success_count += 1
        else:
            error_count += 1
    
    print(f"{'-'*80}")
    print(f"Résultat régions d'origine: {success_count} succès, {error_count} erreurs")
    
    return success_count, error_count


def main():
    # Heure de début
    start_time = datetime.now()
    print(f"Début: {start_time.strftime('%d/%m/%Y %H:%M:%S')}")
    
    config = read_config()
    
    # Connexion au serveur principal
    main_models, main_database, main_uid, main_password = connect_odoo(config['odoo'])
    
    # Connexion au serveur e-commerce
    ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password = connect_odoo(config['ecommerce'])
    
    # 1. Synchroniser d'abord les types de lait vers les catégories publiques
    milk_types = get_milk_types(main_models, main_database, main_uid, main_password)
    milk_success, milk_errors = synchronize_milk_types_to_public_categories(
        milk_types, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password
    )
    
    # 2. Récupérer les produits du serveur principal
    products = get_products(main_models, main_database, main_uid, main_password, config['odoo']['limit'])
    
    # Récupérer les paramètres de configuration
    force_days = config['odoo']['force_update_days']
    update_images = config['odoo']['update_images']
    
    if force_days > 0:
        print(f"Mode forcé activé: mise à jour des articles modifiés dans les {force_days} derniers jours")
    
    if update_images:
        print("Mise à jour des images activée")
    else:
        print("Mise à jour des images désactivée")
    
    # 3. Synchroniser les produits vers l'e-commerce
    print(f"\n{'='*100}")
    print(f"{'SYNCHRONISATION DES PRODUITS':^100}")
    print(f"{'='*100}")
    
    success_count, error_count = synchronize_products(
        products, ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
        main_models, main_database, main_uid, main_password, force_days, update_images
    )
    
    # 4. Trier tous les tags produits par ordre alphabétique
    tag_success, tag_errors = sort_product_tags_alphabetically(
        ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password
    )
    
    # Heure de fin et durée
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{'='*100}")
    print(f"{'RÉSUMÉ FINAL':^100}")
    print(f"{'='*100}")
    print(f"Types de lait (catégories): {milk_success} succès, {milk_errors} erreurs")
    print(f"Produits: {success_count} succès, {error_count} erreurs")
    print(f"Tags (tri alphabétique): {tag_success} succès, {tag_errors} erreurs")
    print(f"Fin: {end_time.strftime('%d/%m/%Y %H:%M:%S')} - Durée: {duration.total_seconds():.2f}s")
    print(f"{'='*100}")


if __name__ == "__main__":
    main()
