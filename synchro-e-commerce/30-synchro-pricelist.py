#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de synchronisation des listes de prix entre Odoo principal et e-commerce via XML-RPC
"""

import sys
import os
from datetime import datetime

# Import des fonctions communes
from mes_fonctions import (
    read_config,
    connect_odoo,
    parse_odoo_date,
    find_pricelist_by_name,
    find_currency_by_name,
    find_product_template_by_code,
    find_product_by_code,
    find_category_by_complete_name,
    get_product_code,
    get_category_complete_name,
    get_pricelist_name,
    create_product_on_ecommerce,
)


def get_archived_product_ids(models, database, uid, password):
    """
    Récupère les IDs de tous les produits archivés (product.product et product.template).
    Retourne deux sets: (archived_product_ids, archived_template_ids)
    """
    print("Récupération des produits archivés...")
    
    # Récupérer les IDs des product.product archivés
    archived_products = models.execute_kw(
        database, uid, password,
        'product.product', 'search',
        [[['active', '=', False]]],
        {'context': {'active_test': False}}
    )
    
    # Récupérer les IDs des product.template archivés
    archived_templates = models.execute_kw(
        database, uid, password,
        'product.template', 'search',
        [[['active', '=', False]]],
        {'context': {'active_test': False}}
    )
    
    archived_product_set = set(archived_products)
    archived_template_set = set(archived_templates)
    
    print(f"  → {len(archived_product_set)} variantes archivées, {len(archived_template_set)} templates archivés")
    
    return archived_product_set, archived_template_set


def get_pricelists(models, database, uid, password, limit=0, pricelist_names=None):
    """Récupérer les listes de prix depuis Odoo"""
    print("Récupération des listes de prix depuis Odoo...")
    
    fields = [
        'id', 'name', 'active', 'sequence', 'currency_id', 
        'company_id', 'discount_policy', 'write_date'
    ]
    
    # Construire le domaine de recherche
    domain = []
    if pricelist_names:
        domain = [['name', 'in', pricelist_names]]
        print(f"Filtrage par noms: {pricelist_names}")
    
    search_params = {
        'fields': fields,
        'context': {'lang': 'fr_FR'}
    }
    
    if limit > 0:
        search_params['limit'] = limit
    
    try:
        pricelists = models.execute_kw(
            database, uid, password,
            'product.pricelist', 'search_read',
            [domain],
            search_params
        )
        
        print(f"Nombre de listes de prix récupérées: {len(pricelists)}")
        return pricelists
        
    except Exception as e:
        print(f"Erreur lors de la récupération des listes de prix: {e}")
        return []


def get_pricelist_items(models, database, uid, password, pricelist_id, limit=0):
    """Récupérer les règles d'une liste de prix"""
    fields = [
        'id', 'pricelist_id', 'applied_on', 'product_tmpl_id', 'product_id',
        'categ_id', 'min_quantity', 'date_start', 'date_end',
        'compute_price', 'fixed_price', 'percent_price', 'base',
        'base_pricelist_id', 'price_discount', 'price_surcharge',
        'price_round', 'price_min_margin', 'price_max_margin', 'write_date'
    ]
    
    search_params = {
        'fields': fields,
        'context': {'lang': 'fr_FR'}
    }
    
    if limit > 0:
        search_params['limit'] = limit
    
    try:
        items = models.execute_kw(
            database, uid, password,
            'product.pricelist.item', 'search_read',
            [[['pricelist_id', '=', pricelist_id]]],
            search_params
        )
        
        return items
        
    except Exception as e:
        print(f"Erreur lors de la récupération des règles pour la liste {pricelist_id}: {e}")
        return []


def prepare_pricelist_data(pricelist, target_currency_id):
    """Préparer les données de la liste de prix pour création/mise à jour"""
    # Note: discount_policy n'existe plus dans Odoo 18, donc on ne l'inclut pas
    data = {
        'name': pricelist['name'],
        'active': pricelist.get('active', True),
        'sequence': pricelist.get('sequence', 16),
        'currency_id': target_currency_id,
    }
    
    return data


def prepare_pricelist_item_data(item, target_pricelist_id, 
                                 target_models, target_database, target_uid, target_password,
                                 source_models, source_database, source_uid, source_password,
                                 archived_product_ids=None, archived_template_ids=None,
                                 auto_create_products=True, update_images=False):
    """
    Préparer les données d'une règle de prix pour création/mise à jour.
    Si auto_create_products=True, crée automatiquement les produits manquants sur la cible.
    Les produits archivés (IDs dans archived_product_ids/archived_template_ids) sont ignorés.
    """
    data = {
        'pricelist_id': target_pricelist_id,
        'applied_on': item.get('applied_on', '3_global'),
        'min_quantity': item.get('min_quantity', 0),
        'compute_price': item.get('compute_price', 'fixed'),
    }
    
    # Dates de validité
    if item.get('date_start'):
        data['date_start'] = item['date_start']
    if item.get('date_end'):
        data['date_end'] = item['date_end']
    
    # Selon le mode de calcul du prix
    compute_price = item.get('compute_price', 'fixed')
    
    if compute_price == 'fixed':
        data['fixed_price'] = item.get('fixed_price', 0.0)
    elif compute_price == 'percentage':
        data['percent_price'] = item.get('percent_price', 0.0)
    elif compute_price == 'formula':
        data['base'] = item.get('base', 'list_price')
        data['price_discount'] = item.get('price_discount', 0.0)
        data['price_surcharge'] = item.get('price_surcharge', 0.0)
        data['price_round'] = item.get('price_round', 0.0)
        data['price_min_margin'] = item.get('price_min_margin', 0.0)
        data['price_max_margin'] = item.get('price_max_margin', 0.0)
        
        # Liste de prix de base (si formule basée sur une autre liste)
        if item.get('base') == 'pricelist' and item.get('base_pricelist_id'):
            base_pricelist_name = get_pricelist_name(
                source_models, source_database, source_uid, source_password,
                item['base_pricelist_id'][0] if isinstance(item['base_pricelist_id'], list) else item['base_pricelist_id']
            )
            if base_pricelist_name:
                target_base_pricelist = find_pricelist_by_name(
                    target_models, target_database, target_uid, target_password,
                    base_pricelist_name
                )
                if target_base_pricelist:
                    data['base_pricelist_id'] = target_base_pricelist['id']
    
    # Selon le type d'application
    applied_on = item.get('applied_on', '3_global')
    
    if applied_on == '0_product_variant':
        # Variante de produit spécifique
        if item.get('product_id'):
            product_id = item['product_id'][0] if isinstance(item['product_id'], list) else item['product_id']
            
            # Vérifier si le produit est archivé dans la source
            if archived_product_ids and product_id in archived_product_ids:
                return 'SKIP'
            
            product_code = get_product_code(source_models, source_database, source_uid, source_password, product_id, is_template=False)
            if product_code:
                target_product_id = find_product_by_code(
                    target_models, target_database, target_uid, target_password, product_code
                )
                if target_product_id:
                    data['product_id'] = target_product_id['id']
                else:
                    # Produit non trouvé sur la cible - tenter de le créer
                    if auto_create_products:
                        print(f"    ⚠ Produit variant '{product_code}' non trouvé sur la cible - création...")
                        new_template_id = create_product_on_ecommerce(
                            {'default_code': product_code},
                            target_models, target_database, target_uid, target_password,
                            source_models, source_database, source_uid, source_password,
                            update_images=update_images, verbose=True
                        )
                        if new_template_id:
                            # Rechercher le product.product créé
                            target_product = find_product_by_code(
                                target_models, target_database, target_uid, target_password, product_code
                            )
                            if target_product:
                                data['product_id'] = target_product['id']
                            else:
                                print(f"    ⚠ Produit variant '{product_code}' créé mais ID non récupéré")
                                return None
                        else:
                            print(f"    ⚠ Échec création produit variant '{product_code}'")
                            return None
                    else:
                        print(f"    ⚠ Produit variant '{product_code}' non trouvé sur la cible")
                        return None
            else:
                print(f"    ⚠ Référence produit variant non trouvée pour ID {product_id}")
                return None
                
    elif applied_on == '1_product':
        # Modèle de produit spécifique
        if item.get('product_tmpl_id'):
            tmpl_id = item['product_tmpl_id'][0] if isinstance(item['product_tmpl_id'], list) else item['product_tmpl_id']
            
            # Vérifier si le template est archivé dans la source
            if archived_template_ids and tmpl_id in archived_template_ids:
                return 'SKIP'
            
            product_code = get_product_code(source_models, source_database, source_uid, source_password, tmpl_id, is_template=True)
            if product_code:
                target_tmpl_id = find_product_template_by_code(
                    target_models, target_database, target_uid, target_password, product_code
                )
                if target_tmpl_id:
                    data['product_tmpl_id'] = target_tmpl_id
                else:
                    # Produit non trouvé sur la cible - tenter de le créer
                    if auto_create_products:
                        print(f"    ⚠ Produit template '{product_code}' non trouvé sur la cible - création...")
                        new_template_id = create_product_on_ecommerce(
                            {'default_code': product_code},
                            target_models, target_database, target_uid, target_password,
                            source_models, source_database, source_uid, source_password,
                            update_images=update_images, verbose=True
                        )
                        if new_template_id:
                            data['product_tmpl_id'] = new_template_id
                        else:
                            print(f"    ⚠ Échec création produit template '{product_code}'")
                            return None
                    else:
                        print(f"    ⚠ Produit template '{product_code}' non trouvé sur la cible")
                        return None
            else:
                print(f"    ⚠ Référence produit template non trouvée pour ID {tmpl_id}")
                return None
                
    elif applied_on == '2_product_category':
        # Catégorie de produits
        if item.get('categ_id'):
            categ_id = item['categ_id'][0] if isinstance(item['categ_id'], list) else item['categ_id']
            categ_complete_name = get_category_complete_name(source_models, source_database, source_uid, source_password, categ_id)
            if categ_complete_name:
                target_categ_id = find_category_by_complete_name(
                    target_models, target_database, target_uid, target_password, categ_complete_name
                )
                if target_categ_id:
                    data['categ_id'] = target_categ_id
                else:
                    print(f"    ⚠ Catégorie '{categ_complete_name}' non trouvée sur la cible")
                    return None
            else:
                print(f"    ⚠ Nom catégorie non trouvé pour ID {categ_id}")
                return None
    
    # applied_on == '3_global' : pas de référence produit/catégorie nécessaire
    
    return data


def delete_pricelist_items(models, database, uid, password, pricelist_id):
    """Supprimer toutes les règles d'une liste de prix"""
    try:
        item_ids = models.execute_kw(
            database, uid, password,
            'product.pricelist.item', 'search',
            [[['pricelist_id', '=', pricelist_id]]]
        )
        
        if item_ids:
            models.execute_kw(
                database, uid, password,
                'product.pricelist.item', 'unlink',
                [item_ids]
            )
            return len(item_ids)
        return 0
        
    except Exception as e:
        print(f"Erreur lors de la suppression des règles: {e}")
        return 0


def sync_pricelist(pricelist, 
                   target_models, target_database, target_uid, target_password,
                   source_models, source_database, source_uid, source_password,
                   archived_product_ids=None, archived_template_ids=None,
                   current_index=1, total_count=1, limit_items=0, 
                   auto_create_products=True, update_images=False):
    """Synchroniser une liste de prix vers la cible"""
    pricelist_name = pricelist.get('name', 'N/A')
    counter = f"[{current_index:2d}/{total_count:2d}]"
    
    # Chercher si la liste de prix existe déjà
    existing_pricelist = find_pricelist_by_name(
        target_models, target_database, target_uid, target_password,
        pricelist_name
    )
    
    # Récupérer la devise
    currency_name = pricelist.get('currency_id', [None, 'EUR'])[1] if pricelist.get('currency_id') else 'EUR'
    target_currency_id = find_currency_by_name(
        target_models, target_database, target_uid, target_password,
        currency_name
    )
    
    if not target_currency_id:
        print(f"{counter} Liste: {pricelist_name:<30} ✗ Devise '{currency_name}' non trouvée")
        return False, 0, 0, 0
    
    # Préparer les données de la liste de prix
    pricelist_data = prepare_pricelist_data(pricelist, target_currency_id)
    
    target_pricelist_id = None
    
    if existing_pricelist:
        target_pricelist_id = existing_pricelist['id']
        
        # Mettre à jour la liste existante
        try:
            result = target_models.execute_kw(
                target_database, target_uid, target_password,
                'product.pricelist', 'write',
                [[target_pricelist_id], pricelist_data],
                {'context': {'lang': 'fr_FR'}}
            )
            
            if result:
                action = "Mise à jour"
            else:
                print(f"{counter} Liste: {pricelist_name:<30} ✗ Échec mise à jour")
                return False, 0, 0, 0
                
        except Exception as e:
            print(f"{counter} Liste: {pricelist_name:<30} ✗ Erreur mise à jour: {e}")
            return False, 0, 0, 0
    else:
        # Créer une nouvelle liste
        try:
            target_pricelist_id = target_models.execute_kw(
                target_database, target_uid, target_password,
                'product.pricelist', 'create',
                [pricelist_data],
                {'context': {'lang': 'fr_FR'}}
            )
            
            action = f"Création (ID: {target_pricelist_id})"
            
        except Exception as e:
            print(f"{counter} Liste: {pricelist_name:<30} ✗ Erreur création: {e}")
            return False, 0, 0, 0
    
    # Supprimer les anciennes règles et synchroniser les nouvelles
    deleted_count = delete_pricelist_items(target_models, target_database, target_uid, target_password, target_pricelist_id)
    
    # Récupérer les règles depuis la source
    source_items = get_pricelist_items(source_models, source_database, source_uid, source_password, pricelist['id'], limit_items)
    
    items_success = 0
    items_error = 0
    items_skipped = 0
    products_created = 0
    
    for item in source_items:
        item_data = prepare_pricelist_item_data(
            item, target_pricelist_id,
            target_models, target_database, target_uid, target_password,
            source_models, source_database, source_uid, source_password,
            archived_product_ids=archived_product_ids, archived_template_ids=archived_template_ids,
            auto_create_products=auto_create_products, update_images=update_images
        )
        
        if item_data == 'SKIP':
            # Produit ignoré (non trouvé/archivé dans la source)
            items_skipped += 1
        elif item_data:
            try:
                target_models.execute_kw(
                    target_database, target_uid, target_password,
                    'product.pricelist.item', 'create',
                    [item_data],
                    {'context': {'lang': 'fr_FR'}}
                )
                items_success += 1
            except Exception as e:
                print(f"    ✗ Erreur création règle: {e}")
                items_error += 1
        else:
            items_error += 1
    
    # Construire le message de résumé
    summary_parts = [f"{items_success} règles"]
    if items_skipped > 0:
        summary_parts.append(f"{items_skipped} ignorés")
    if items_error > 0:
        summary_parts.append(f"{items_error} erreurs")
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{timestamp} {counter} Liste: {pricelist_name:<30} ✓ {action} ({', '.join(summary_parts)})")
    
    return True, items_success, items_error, products_created


def display_pricelists(pricelists):
    """Afficher les listes de prix"""
    print(f"\n{'='*80}")
    print(f"{'LISTES DE PRIX':^80}")
    print(f"{'='*80}")
    print(f"{'ID':<6} {'Nom':<40} {'Devise':<10} {'Politique':<15} {'Actif'}")
    print(f"{'-'*80}")
    
    for pl in pricelists:
        currency = pl.get('currency_id', [None, 'N/A'])
        currency_name = currency[1] if isinstance(currency, list) else 'N/A'
        
        print(f"{pl['id']:<6} {pl['name'][:39]:<40} "
              f"{currency_name:<10} {pl.get('discount_policy', 'N/A'):<15} "
              f"{'Oui' if pl.get('active', True) else 'Non'}")
    
    print(f"{'-'*80}")
    print(f"Total: {len(pricelists)} listes de prix")


def synchronize_pricelists(pricelists,
                            target_models, target_database, target_uid, target_password,
                            source_models, source_database, source_uid, source_password,
                            archived_product_ids=None, archived_template_ids=None,
                            limit_items=0, auto_create_products=True, update_images=False):
    """Synchroniser toutes les listes de prix"""
    success_count = 0
    error_count = 0
    total_items_success = 0
    total_items_error = 0
    total_products_created = 0
    total_pricelists = len(pricelists)
    
    for index, pricelist in enumerate(pricelists, 1):
        success, items_ok, items_err, products_created = sync_pricelist(
            pricelist,
            target_models, target_database, target_uid, target_password,
            source_models, source_database, source_uid, source_password,
            archived_product_ids=archived_product_ids, archived_template_ids=archived_template_ids,
            current_index=index, total_count=total_pricelists, limit_items=limit_items,
            auto_create_products=auto_create_products, update_images=update_images
        )
        
        if success:
            success_count += 1
        else:
            error_count += 1
        
        total_items_success += items_ok
        total_items_error += items_err
        total_products_created += products_created
    
    return success_count, error_count, total_items_success, total_items_error, total_products_created


def main():
    # Heure de début
    start_time = datetime.now()
    print(f"{'='*80}")
    print(f"{'SYNCHRONISATION DES LISTES DE PRIX':^80}")
    print(f"{'='*80}")
    print(f"Début: {start_time.strftime('%d/%m/%Y %H:%M:%S')}")
    
    config = read_config()
    
    # Connexion au serveur source (Odoo principal)
    print("\nConnexion au serveur Odoo principal...")
    source_models, source_database, source_uid, source_password = connect_odoo(config['odoo'])
    print(f"✓ Connecté à {config['odoo']['url']} (base: {config['odoo']['database']})")
    
    # Connexion au serveur cible (e-commerce)
    print("\nConnexion au serveur e-commerce...")
    target_models, target_database, target_uid, target_password = connect_odoo(config['ecommerce'])
    print(f"✓ Connecté à {config['ecommerce']['url']} (base: {config['ecommerce']['database']})")
    
    # Récupérer les listes de prix depuis la source
    limit_pricelists = config['odoo']['limit_pricelists']
    pricelist_names = config['odoo']['pricelist_names']
    limit_items = config['odoo']['limit_items_per_pricelist']
    update_images = config['odoo'].get('update_images', False)
    
    if pricelist_names:
        print(f"Filtrage par noms: {pricelist_names}")
    if limit_pricelists > 0:
        print(f"Limite: {limit_pricelists} liste(s) de prix")
    if limit_items > 0:
        print(f"Limite: {limit_items} règle(s) par liste de prix")
    
    print(f"Création automatique des produits manquants: Activée")
    print(f"Mise à jour des images: {'Activée' if update_images else 'Désactivée'}")
    
    # Récupérer les IDs des produits archivés (pour éviter de les traiter)
    archived_product_ids, archived_template_ids = get_archived_product_ids(
        source_models, source_database, source_uid, source_password
    )
    
    pricelists = get_pricelists(source_models, source_database, source_uid, source_password, limit_pricelists, pricelist_names)
    
    if not pricelists:
        print("\nAucune liste de prix à synchroniser.")
        return
    
    # Afficher les listes de prix trouvées
    display_pricelists(pricelists)
    
    # Synchroniser les listes de prix
    print(f"\n{'='*80}")
    print(f"{'SYNCHRONISATION':^80}")
    print(f"{'='*80}")
    
    pricelist_success, pricelist_errors, items_success, items_errors, products_created = synchronize_pricelists(
        pricelists,
        target_models, target_database, target_uid, target_password,
        source_models, source_database, source_uid, source_password,
        archived_product_ids=archived_product_ids, archived_template_ids=archived_template_ids,
        limit_items=limit_items, auto_create_products=True, update_images=update_images
    )
    
    # Heure de fin et durée
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{'='*80}")
    print(f"{'RÉSUMÉ FINAL':^80}")
    print(f"{'='*80}")
    print(f"Listes de prix: {pricelist_success} succès, {pricelist_errors} erreurs")
    print(f"Règles de prix: {items_success} succès, {items_errors} erreurs")
    if products_created > 0:
        print(f"Produits créés automatiquement: {products_created}")
    print(f"Fin: {end_time.strftime('%d/%m/%Y %H:%M:%S')} - Durée: {duration.total_seconds():.2f}s")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
