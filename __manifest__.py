# -*- coding: utf-8 -*-
{
    'name'     : 'InfoSaône - Module Odoo 14 pour Fromtome',
    'version'  : '0.1',
    'author'   : 'InfoSaône',
    'category' : 'InfoSaône',
    'description': """
InfoSaône - Module Odoo 14 pour Fromtome 
===================================================
""",
    'maintainer' : 'InfoSaône',
    'website'    : 'http://www.infosaone.com',
    'depends'    : [
        'base',
        'sale',
        'product',
        'sale_management',
        'account',
        'stock',
        'purchase',
        'mrp',
        'board',
        'account_payment_order',
        'account_payment_partner',
        'account_payment_purchase',
        'account_payment_sale',
        'account_banking_fr_lcr',
        'account_banking_sepa_credit_transfer',
        'account_banking_sepa_direct_debit',
        'l10n_fr_department',
        'l10n_fr_fec',
        'l10n_fr_intrastat_product',
        'l10n_fr_siret',
        'l10n_fr_state',
        'list_export_excel_app',
    ],
    'data' : [
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/account_move_view.xml',
        'views/mail_activity_views.xml',
        'views/mail_views.xml',
        'views/product_view.xml',
        'views/product_pricelist_views.xml',
        'views/product_tech_template.xml',
        'views/purchase_view.xml',
        'views/res_company_view.xml',
        'views/res_partner_view.xml',
        'views/res_users_view.xml',
        'views/sale_view.xml',
        'views/stock_views.xml',
        'views/stock_inventory_view.xml',
        'views/stock_move_view.xml',
        'views/stock_picking_view.xml',
        'views/stock_quant_view.xml',
        'views/product_supplierinfo_view.xml',
        'views/is_account_invoice_line.xml',
        'views/is_analyse_facturation_views.xml',
        'views/is_commande_fromtome_views.xml',
        'views/is_export_compta_views.xml',
        'views/is_fnc_views.xml',
        'views/is_imprimer_etiquette_gs1_views.xml',
        'views/is_sale_order_line.xml',
        'views/is_listing_prix_client_views.xml',
        'views/is_stock_move_line_view.xml',
        'views/is_stock_production_lot_contrat_view.xml',
        'views/is_import_le_cellier_views.xml',
        'views/is_relance_facture_view.xml',
        'views/is_suivi_commande_hebdo_views.xml',
        'views/is_analyse_rupture_views.xml',
        'views/is_preparation_transfert_entrepot_views.xml',
        'views/is_promo_fournisseur_view.xml',
        "views/menu.xml",
        'views/report_invoice.xml',
        'report/delivery_template.xml',
        'report/fiche_prepa_template.xml',
        'report/sale_template.xml',
        'report/purchase_order_templates.xml',
        'report/external_layout_boxed.xml',
        'report/offre_report_template.xml',
        'report/fiche_palette.xml',
        'report/listing_prix_client_template.xml',
        'report/listing_prix_client_liste_template.xml',
        'report/report_stockinventory.xml',
        'report/report_account_payment_order.xml',
        'data/stock_picking_mail.xml',
    ],
    'installable': True,
    'application': True,
}
