#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'archivage des articles sur le site e-commerce
qui n'existent pas (ou plus) dans la base Odoo principale.

Logique :
  1. Récupérer tous les default_code actifs de la base principale.
  2. Récupérer tous les product.template actifs sur le site e-commerce
     (is_published=True ou simplement active=True selon le besoin).
  3. Tout article e-commerce dont le default_code ne correspond à aucun
     article de la base principale est archivé (active=False).

Usage :
  python3 archive-ecommerce-articles.py [--dry-run]

  --dry-run  : liste les articles qui seraient archivés sans les modifier.
"""

import sys

# Import des fonctions communes
from mes_fonctions import read_config, connect_odoo


# ---------------------------------------------------------------------------
# Récupération des données
# ---------------------------------------------------------------------------

def get_main_default_codes(models, database, uid, password):
    """Retourner un set des default_code actifs dans la base principale."""
    products = models.execute_kw(
        database, uid, password,
        'product.template', 'search_read',
        [[['active', '=', True]]],
        {'fields': ['id', 'name', 'default_code'], 'context': {'active_test': False}}
    )
    codes = {p['default_code'] for p in products if p.get('default_code')}
    return codes, products


def get_ecommerce_active_products(models, database, uid, password):
    """Retourner tous les product.template actifs sur l'e-commerce."""
    products = models.execute_kw(
        database, uid, password,
        'product.template', 'search_read',
        [[['active', '=', True]]],
        {
            'fields': ['id', 'name', 'default_code', 'is_published'],
            'context': {'active_test': False, 'lang': 'fr_FR'}
        }
    )
    return products


# ---------------------------------------------------------------------------
# Analyse comparative
# ---------------------------------------------------------------------------

def analyse_differences(main_products, main_codes, ecommerce_products):
    """
    Compare le nombre d'articles avec default_code dans les deux bases.
    Affiche OK si identique, sinon liste les différences.
    """
    ec_with_code  = [p for p in ecommerce_products if p.get('default_code')]
    ec_codes      = {p['default_code'] for p in ec_with_code}
    ec_by_code    = {p['default_code']: p for p in ec_with_code}
    main_by_code  = {p['default_code']: p for p in main_products if p.get('default_code')}

    # Articles présents dans l'origine mais absents de l'e-commerce
    absents_ec     = sorted(
        [p for p in main_products if p.get('default_code') and p['default_code'] not in ec_codes],
        key=lambda x: x['default_code']
    )
    # Articles présents sur l'e-commerce mais absents de l'origine
    absents_origin = sorted(
        [p for p in ec_with_code if p['default_code'] not in main_codes],
        key=lambda x: x['default_code']
    )

    nb_main = len(main_codes)
    nb_ec   = len(ec_codes)

    if nb_main == nb_ec and not absents_ec and not absents_origin:
        print(f"✓ Comparaison articles OK — {nb_main} articles avec default_code dans les deux bases.")
    else:
        all_codes = sorted(
            {p['default_code'] for p in absents_ec} | {p['default_code'] for p in absents_origin}
        )
        col = max((len(c) for c in all_codes), default=10)
        name_col = max(
            (len((main_by_code.get(c) or ec_by_code.get(c, {})).get('name', '')) for c in all_codes),
            default=20
        )
        header = f"  {'Référence':<{col}}  {'Nom':<{name_col}}  Origine  E-commerce"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for code in all_codes:
            p = main_by_code.get(code) or ec_by_code.get(code, {})
            name = p.get('name', '')
            in_main = "✓" if code in main_codes else " "
            in_ec   = "✓" if code in ec_codes   else " "
            print(f"  {code:<{col}}  {name:<{name_col}}    {in_main}          {in_ec}")

    return absents_ec, absents_origin


# ---------------------------------------------------------------------------
# Archivage
# ---------------------------------------------------------------------------

def archive_products(ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
                     products_to_archive, dry_run=False):
    """Archiver la liste de produits donnée sur l'e-commerce."""
    if not products_to_archive:
        return 0, 0

    ids_to_archive = [p['id'] for p in products_to_archive]

    if dry_run:
        print("\n[DRY-RUN] Aucune modification effectuée.")
        return len(ids_to_archive), 0

    # Désactiver d'abord la publication puis archiver
    success = 0
    errors = 0
    try:
        # Dépublier
        ecommerce_models.execute_kw(
            ecommerce_database, ecommerce_uid, ecommerce_password,
            'product.template', 'write',
            [ids_to_archive, {'is_published': False}]
        )
        # Archiver
        ecommerce_models.execute_kw(
            ecommerce_database, ecommerce_uid, ecommerce_password,
            'product.template', 'write',
            [ids_to_archive, {'active': False}]
        )
        success = len(ids_to_archive)
        print(f"✓ {success} article(s) archivé(s).")
    except Exception as e:
        print(f"✗ Erreur archivage en masse : {e} — tentative article par article...")
        for p in products_to_archive:
            try:
                ecommerce_models.execute_kw(
                    ecommerce_database, ecommerce_uid, ecommerce_password,
                    'product.template', 'write',
                    [[p['id']], {'is_published': False, 'active': False}]
                )
                success += 1
            except Exception as e2:
                print(f"  ✗ Échec ID {p['id']} {p.get('default_code','?')} : {e2}")
                errors += 1
        if success:
            print(f"✓ {success} article(s) archivé(s).")

    return success, errors


def reactivate_archived_products(ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
                                  absents_ec, dry_run=False):
    """
    Pour chaque article présent en origine mais absent de l'e-commerce,
    vérifie s'il est archivé (active=False) sur l'e-commerce et le réactive.
    """
    if not absents_ec:
        return

    codes_to_check = [p['default_code'] for p in absents_ec if p.get('default_code')]

    # Rechercher les produits archivés sur l'e-commerce avec ces références
    archived = ecommerce_models.execute_kw(
        ecommerce_database, ecommerce_uid, ecommerce_password,
        'product.template', 'search_read',
        [[['default_code', 'in', codes_to_check], ['active', '=', False]]],
        {
            'fields': ['id', 'name', 'default_code'],
            'context': {'active_test': False, 'lang': 'fr_FR'}
        }
    )

    if not archived:
        return

    ids = [p['id'] for p in archived]
    col = max(len(p['default_code']) for p in archived)

    print(f"\n  Article(s) archivé(s) sur l'e-commerce à réactiver ({len(archived)}) :")
    for p in sorted(archived, key=lambda x: x['default_code']):
        print(f"    {p['default_code']:<{col}}  {p['name']}")

    if dry_run:
        print("  [DRY-RUN] Aucune réactivation effectuée.")
        return

    try:
        ecommerce_models.execute_kw(
            ecommerce_database, ecommerce_uid, ecommerce_password,
            'product.template', 'write',
            [ids, {'active': True}]
        )
        print(f"  ✓ {len(ids)} article(s) réactivé(s).")
    except Exception as e:
        print(f"  ✗ Erreur réactivation : {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print("[DRY-RUN] Aucune modification ne sera effectuée.")

    config = read_config()
    main_models, main_database, main_uid, main_password = connect_odoo(config['odoo'])
    ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password = connect_odoo(config['ecommerce'])

    main_codes, main_products = get_main_default_codes(main_models, main_database, main_uid, main_password)
    ecommerce_products = get_ecommerce_active_products(
        ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password
    )

    absents_ec, to_archive = analyse_differences(main_products, main_codes, ecommerce_products)

    # Réactiver les articles archivés sur l'e-commerce absents de l'origine
    reactivate_archived_products(
        ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
        absents_ec, dry_run=dry_run
    )

    success, errors = archive_products(
        ecommerce_models, ecommerce_database, ecommerce_uid, ecommerce_password,
        to_archive, dry_run=dry_run
    )

    if errors:
        print(f"✗ {errors} erreur(s) lors de l'archivage.")


if __name__ == "__main__":
    main()
