# Modules OCA utilisés par `is_fromtome14`

Ce document liste les modules OCA (dépôts clonés dans `/home/tony/Documents/Développement/dev_odoo/14.0/fromtome/`) dont dépend le module `is_fromtome14`, ainsi que leurs modules techniques sous-jacents, avec une explication de leur rôle.

Colonnes ajoutées :
- **v18** : `OK` si le module (ou son équivalent) existe en version 18.0 (vérifié sur la branche `18.0` du dépôt OCA correspondant sur GitHub, ou dans les sources locales), vide sinon.
- **FE** : `OK` si le module est nécessaire à la mise en place de la facturation électronique (dépendance directe ou transitive des modules `account_invoice_en16931` / `l10n_fr_einvoicing` étudiés pour le projet `facturation-electronique`), vide sinon.

## Dépôt `bank-payment`

Gère les ordres de paiement et les moyens de paiement bancaires (SEPA, mandats...).

| Module | v18 | FE | Rôle |
|---|---|---|---|
| **account_payment_mode** | OK ⚠️ | | Module de base : définit le concept de "mode de paiement" (ex: virement SEPA, prélèvement, LCR...) associé à un journal comptable et une méthode de paiement. Sert de fondation aux autres modules de paiement. |
| **account_payment_partner** | OK | | Ajoute le mode de paiement sur les partenaires (clients/fournisseurs) et sur les factures, permettant de définir un mode de paiement par défaut par partenaire. |
| **account_payment_order** | OK | | Cœur du dépôt : permet de regrouper plusieurs factures/paiements dans un "ordre de paiement" (fichier à remettre à la banque) au lieu de les payer un par un. |
| **account_payment_purchase** | OK | | Ajoute le compte bancaire et le mode de paiement sur les bons de commande d'achat, repris ensuite sur la facture fournisseur. |
| **account_payment_sale** | OK | | Ajoute le mode de paiement sur les commandes de vente, repris ensuite sur la facture client. |
| **account_banking_pain_base** | OK | | Module technique de base pour générer les fichiers XML au format PAIN (Payment Initiation - norme ISO 20022) utilisés par les virements/prélèvements SEPA. |
| **account_banking_mandate** | OK | | Gère les mandats de prélèvement SEPA (autorisations données par le client au fournisseur pour prélever son compte). |
| **account_banking_sepa_credit_transfer** | OK | | Génère les fichiers XML SEPA de virement (Credit Transfer) à partir des ordres de paiement, pour paiement des fournisseurs. **Aucun équivalent en Odoo 18 Community** : le générateur natif (`account_iso20022`, activable via le paramètre "SEPA Credit Transfer / ISO20022") fait partie du périmètre **Enterprise**. Module donc bien à installer pour conserver cette fonction en Community. |
| **account_banking_sepa_direct_debit** | OK | | Génère les fichiers XML SEPA de prélèvement (Direct Debit) à partir des ordres de paiement, pour encaissement client. **Aucun équivalent en Odoo 18 Community** : le générateur natif (`account_sepa_direct_debit`, activable via le paramètre "Use SEPA Direct Debit") fait partie du périmètre **Enterprise**. Module donc bien à installer pour conserver cette fonction en Community. |

Aucun de ces modules n'est requis pour la facturation électronique : c'est un sujet indépendant (moyens de paiement bancaires vs format/transmission de la facture).

**Chaîne de dépendances pour utiliser le SEPA** : `account_banking_sepa_credit_transfer` → `account_banking_pain_base` → `account_payment_order` → `account_payment_partner` (+ `base_iban`, core Odoo) → `account_payment_mode`. `account_banking_sepa_direct_debit` suit la même chaîne via `account_banking_mandate` → `account_payment_order`. **Oui, `account_payment_partner` est donc bien indispensable** : Odoo l'installera de toute façon automatiquement en cascade (dépendance transitive obligatoire d'`account_payment_order`), mais il est plus clair de le lister explicitement dans le `depends` du manifest, comme le fait déjà `is_fromtome14`.

⚠️ **Point d'attention v18 sur `account_payment_mode`** : ce module crée son propre modèle `account.payment.mode` (distinct de `account.payment.method`/`account.payment.method.line` natifs Odoo, donc pas de conflit de modèle), mais il redéfinit aussi les vues (formulaire/liste/recherche) du modèle natif `account.payment.method`. Or, en Odoo 18, le nouveau module core-adjacent `account_payment_method_base` fournit **sa propre vue standard** pour ce même modèle `account.payment.method`, ce qui crée deux définitions de vues concurrentes. L'OCA a publié un module glue dédié, **`account_payment_method_base_mode`** (branche `18.0` du dépôt `bank-payment`), qui fait hériter les vues d'`account_payment_mode` de celles d'`account_payment_method_base` pour éviter le conflit. **À installer obligatoirement avec `account_payment_mode` lors d'une migration vers v18.** Il n'y a par ailleurs pas de redondance fonctionnelle : `account.payment.method.line` (natif) sert au paramétrage des moyens de paiement par journal/rapprochement, tandis qu'`account.payment.mode` (OCA) gère le mode de paiement par défaut du partenaire et le regroupement en ordres de paiement — ce sont deux couches complémentaires, pas concurrentes.

## Dépôt `l10n-france`

Localisation française : gère les spécificités administratives, fiscales et bancaires françaises.

| Module | v18 | FE | Rôle |
|---|---|---|---|
| **l10n_fr_state** | OK | | Peuple la base de données avec les régions françaises. |
| **l10n_fr_department** | OK | | Peuple la base de données avec les départements français (champ département sur les adresses). |
| **l10n_fr_siret** | OK | OK | Ajoute les numéros d'identité d'entreprise français SIRET/SIREN/NIC sur les partenaires. En v18, requis par `l10n_fr_account_invoice_en16931` et par `l10n_fr_einvoicing` (via `l10n_fr_siret_account`). |
| **l10n_fr_intrastat_product** | OK | | Génère la DEB (Déclaration d'Échange de Biens), déclaration douanière obligatoire pour les échanges de biens (achats/ventes) avec les autres pays de l'UE. Non requis pour la FE, mais son socle `intrastat_base` l'est (voir ci-dessous). |
| **account_banking_fr_lcr** | OK (renommé) | | Génère les fichiers CFONB pour la LCR (Lettre de Change Relevé), moyen de paiement français, à partir des ordres de paiement (dépôt `bank-payment`). **Attention** : renommé `account_payment_fr_lcr` dans la branche 18.0 du dépôt. |

`is_fromtome14` dépend aussi de `l10n_fr_fec`, module **core Odoo** (non OCA). En v18, `l10n_fr_fec` n'existe plus en tant que module séparé : son contenu a été fusionné dans `l10n_fr_account`.

## Dépôt `intrastat-extrastat`

Base pour les déclarations douanières Intrastat (échanges intracommunautaires), utilisé en dépendance par `l10n_fr_intrastat_product`.

| Module | v18 | FE | Rôle |
|---|---|---|---|
| **intrastat_base** | OK | OK | Module technique de base pour la génération des déclarations Intrastat (structure commune, quelle que soit la localisation). Déjà présent transitivement dans `is_fromtome14` (via `l10n_fr_intrastat_product`), et c'est aussi une dépendance directe du module `account_invoice_en16931` utilisé pour la facturation électronique : ce module est donc réutilisé pour les deux besoins. |
| **intrastat_product** | OK | | Spécialise le module de base pour la déclaration Intrastat sur les mouvements de **biens/produits** (achats et ventes), en s'appuyant sur les commandes et les livraisons/réceptions de stock. |

## Dépôt `purchase-workflow`

Non utilisé en dépendance du module `is_fromtome14` (installé indépendamment dans la base), mais présent dans le dossier `fromtome`.

| Module | v18 | FE | Rôle |
|---|---|---|---|
| **purchase_discount** | ⚠️ absorbé par le core | | Ajoute un champ **remise (%)** sur les lignes de commande d'achat (négatif = majoration), une remise par défaut sur la fiche fournisseur et sur chaque ligne "Fournisseurs" du produit, et répercute la remise sur la facture et le coût de revient du mouvement de stock. Dépend uniquement de `purchase_stock`. |

**Résumé `purchase_discount`** :
- C'est un module **OCA** (dépôt `OCA/purchase-workflow`, copyright Tiny/Tecnativa/ACSONE/GRAP/OCA), pas un module custom InfoSaône, malgré son emplacement dans le dossier `fromtome`.
- Rôle : afficher une remise séparée du prix catalogue sur les commandes d'achat, avec une remise par défaut paramétrable par fournisseur/produit, répercutée automatiquement sur les lignes de commande, la facture et le rapport PDF.
- **Absent de la branche `18.0`** du dépôt OCA (vérifié sur GitHub) : remplacé par `purchase_order_general_discount` et `purchase_triple_discount`, car **le champ `discount` est désormais natif** sur `purchase.order.line` dans Odoo 18 Community (confirmé dans les sources locales `18.0/0-odoo18/addons/purchase`). **Plus besoin de ce module lors d'une migration vers v18** : la fonctionnalité de base est native ; n'installer un module OCA que si un besoin avancé (double/triple remise en cascade) est nécessaire.

## Dépôt `reporting-engine`

Non utilisé directement en dépendance du module `is_fromtome14`, mais présent dans le dossier `fromtome`. Fournit des outils génériques de reporting pour Odoo (export Excel, éditeur SQL/BI, tableaux de bord KPI, personnalisation des rapports PDF/QWeb...). À documenter si un de ces modules devient une dépendance directe.

## Modules core Odoo (non OCA) utilisés par `is_fromtome14`

| Module | v18 | FE |
|---|---|---|
| base, mail, sale, product, sale_management, account, stock, purchase, purchase_stock, mrp, board, hr, account_edi | OK | |
| l10n_fr_fec | OK (fusionné dans `l10n_fr_account`) | |

## Modules du dossier `fromtome` non OCA

| Module | v18 | FE | Rôle |
|---|---|---|---|
| **is_fromtome14** | | | Module métier principal du projet (le présent module). |
| **is_scan** | | | Module métier personnalisé (scan de documents). |
| **list_export_excel_app** | | | Module personnalisé d'export Excel des vues liste. Aucune version v18 trouvée dans les sources locales — à migrer si besoin. |
| **is_llm2odoo** | OK | | Module générique personnalisé, une version v18 existe déjà dans `dev_odoo/18.0/modules-generiques/is_llm2odoo`. |
| **smtp_by_user** | | | Module personnalisé de configuration SMTP par utilisateur. |
| **web_environment_ribbon**, **web_listview_sticky_header**, **web_m2x_options** | | | Modules techniques/UI personnalisés ou communautaires (à vérifier au cas par cas, non issus des dépôts OCA officiels ci-dessus). |
