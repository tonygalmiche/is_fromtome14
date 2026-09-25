# Analyse marge brute sur les lots facturés

Mise en œuvre du CDC du 10/09/2026 (conversation avec Ulysse et Édith).

Objectif : calculer la marge brute par client, enseigne et commercial à partir des **lots facturés** (et non plus de la dernière facture fournisseur de l'article), et répartir le coût des **rebuts** sur les clients.

Le programme existant `is.analyse.facturation` n'est pas modifié.

## Fichiers

| Fichier | Contenu |
|---|---|
| `models/is_analyse_marge_lot.py` | Modèles `is.analyse.marge.lot` et `is.analyse.marge.lot.ligne` |
| `views/is_analyse_marge_lot_views.xml` | Formulaire, liste, recherche, pivot, graphique |
| `views/menu.xml` | Menu *Analyses > Analyse facturation > Analyse marge brute sur les lots facturés* (groupe `is_analyse_marge_brute_group`) |
| `models/stock_move_line.py` | Index ajouté sur `stock_move_line.lot_id` (absent dans Odoo 14 standard, indispensable pour les recherches par lot) |
| `security/ir.model.access.csv` | Droits du groupe `is_analyse_marge_brute_group` (le même que le menu) sur les 2 modèles |

## Modèles

### `is.analyse.marge.lot` (fiche d'analyse)

- `name` : numéro chrono de l'analyse sur 5 chiffres (séquence `is.analyse.marge.lot`, attribuée à la création).
- `date_debut`, `date_fin` : période analysée.
- `date_calcul`, `duree_calcul` : date et temps (en secondes) du dernier calcul.
- `client`, `enseigne_id`, `user_id`, `product_id`, `invoice_id` : filtres facultatifs (client, enseigne, commercial, produit, facture client) qui **limitent le calcul**, pour réduire le temps de traitement lors d'analyses ponctuelles. Voir « Filtres » ci-dessous.
- `ligne_ids` : lignes calculées (supprimées avec la fiche).
- `exclure_hors_lot` « Exclure les articles non gérés par lot » (coché par défaut) : les articles non gérés par lot (transport…), qui n'ont ni lot ni facture d'achat, sont exclus de l'analyse (factures, avoirs et rebuts).
- `exclure_services` « Exclure les articles de type service » (coché par défaut) : les articles de type service (vente de véhicule, commissions…) sont exclus de l'analyse, car ils ne relèvent pas de la marge sur les marchandises.
- Que ces options soient cochées ou non, les articles non gérés par lot ou de type service ne génèrent **jamais d'anomalie**.
- Totaux calculés en SQL : `nb_lignes`, `nb_anomalies`, `montant_vente`, `montant_achat`, `marge_brute`.

Les analyses sont conservées. Le bouton **Calculer** supprime puis recrée les lignes de la fiche, pour tenir compte des dernières corrections. À la fin du calcul, un message est ajouté dans le chatter : temps de calcul (total, factures, rebuts), nombre de factures et avoirs traités, de rebuts traités, de lignes créées, de lignes en anomalie, et marge brute.

### `is.analyse.marge.lot.ligne` (lignes)

| Champ | Description |
|---|---|
| `type_ligne` | Facture client / Avoir client / Rebut |
| `is_type_avoir` | Avoir sur prix / sur quantité |
| `date` | Date de la facture, de l'avoir ou du rebut |
| `invoice_id`, `invoice_line_id`, `scrap_id` | Origine de la ligne |
| `partner_id`, `enseigne_id`, `user_id` | Client, enseigne (`is.enseigne.commerciale`), commercial |
| `product_id`, `categ_id`, `lot_id` | Article, catégorie, lot |
| `quantity`, `price_unit`, `discount`, `montant_vente` | Vente (signée : négative pour les avoirs) |
| `origine_prix` | `lot` (facture d'achat du lot), `article` (dernière facture de l'article), `aucun` |
| `prix_achat`, `discount_fournisseur`, `prix_achat_net` | Prix d'achat, remise, prix net de remise |
| `fournisseur_id`, `date_facture_fournisseur`, `ligne_facture_fournisseur_id` | Facture d'achat utilisée |
| `montant_achat` | `prix_achat_net × quantité` (coût du rebut pour les rebuts) |
| `marge_brute` | `montant_vente − montant_achat` |
| `anomalie` | Texte de l'anomalie éventuelle |

## Calcul

### 1. Factures et avoirs client (CDC 2.1)

Factures `out_invoice` et `out_refund` validées dont la date de facture est dans la période. Pour chaque ligne avec un article (hors sections, et hors lignes à quantité et montant nuls) :

1. **Recherche des lots** : mouvements de stock faits des lignes de commande liées à la ligne de facture (`sale_order_line_invoice_rel → stock_move.sale_line_id → stock_move_line`), sur le même article :
   - livraisons (`outgoing`) pour une facture, retours (`incoming`) pour un avoir, ou à défaut les livraisons de la commande (avoir sans retour de marchandise, ex : avoir qualité) ;
   - si le BL de la ligne (`is_picking_id`) est renseigné, seuls ses mouvements sont retenus ;
   - quantités converties dans l'unité de l'article.
2. **Répartition** : une ligne de résultat par lot ; la quantité et le montant de la ligne de facture sont répartis au prorata des quantités de chaque lot.
3. **Prix d'achat du lot** : dernière ligne de facture fournisseur (`in_invoice` validée) liée à une ligne de commande d'achat ayant réceptionné ce lot :
   `stock.move.line (lot) → stock.move.purchase_line_id → account.move.line.purchase_line_id`.
   Le prix retenu tient compte de la remise : `price_unit × (1 − discount / 100)`.
4. **Solution de repli** : si aucun lot n'est trouvé, ou si le lot n'a pas de facture d'achat, on prend la dernière facture fournisseur de l'article à la date de la facture, comme le programme actuel. L'anomalie est indiquée sur la ligne.
5. **Avoirs sur prix** : pas de recherche de lot ni de coût d'achat, comme dans le programme actuel.

Signes : pour un avoir, la quantité, le montant de vente et le montant d'achat sont négatifs.

### 2. Rebuts (CDC 2.2)

Rebuts `stock.scrap` faits dans la période :

1. Coût : quantité rebutée × prix d'achat net du lot (même recherche et même repli que ci-dessus, à la date du rebut).
2. Répartition : quantités **facturées** sur ce lot par client (factures `out_invoice` validées, **toutes dates confondues**), calculées avec la même répartition par lot que ci-dessus. Une ligne par client au prorata de ces quantités, avec l'enseigne et le commercial du client.
3. Si le rebut n'a pas de lot, ou si aucune facture client n'existe pour ce lot : une seule ligne sans client, avec l'anomalie.

Pour un rebut, `montant_vente = 0` et `marge_brute = −montant_achat`.

### Anomalies possibles

| Anomalie | Cas |
|---|---|
| `Aucun lot sur les livraisons` | Article géré par lot, mais pas de lot trouvé sur les mouvements de la ligne |
| `Lot sans facture d'achat` | Lot trouvé mais sans facture fournisseur liée (repli sur l'article) |
| `Article sans facture d'achat` | Aucun prix d'achat trouvé, même sans le lot |
| `Rebut sans lot` | Rebut sans lot renseigné |
| `Lot sans facture client` | Coût du rebut non réparti |

Le champ `anomalie` est de type Text pour que le texte passe automatiquement à la ligne dans les listes selon la largeur de la colonne.

### 3. Filtres

Les filtres saisis sur la fiche sont combinés entre eux (ET) et limitent le calcul. Après modification d'un filtre, il faut relancer le calcul.

| Filtre | Factures et avoirs client | Rebuts |
|---|---|---|
| Client (texte) | Factures des clients dont le nom contient ce texte | Part de ces clients uniquement |
| Enseigne | Factures de cette enseigne (`is_enseigne_id` de la facture) | Part des clients de cette enseigne |
| Commercial | Factures des clients de ce commercial | Part des clients de ce commercial |
| Produit | Lignes de cet article uniquement | Rebuts de cet article |
| Facture client | Cette facture uniquement | Part du client de la facture, pour les lots de cette facture |

Pour les rebuts, avec un filtre client, enseigne, commercial ou facture :

- seuls les rebuts des lots facturés aux clients filtrés (toutes dates confondues) sont traités ;
- la répartition du coût est toujours calculée sur **tous** les clients ayant acheté le lot, puis seules les parts des clients filtrés sont conservées. Le coût affecté à un client est donc le même qu'avec un calcul complet ;
- les rebuts non répartis (sans lot ou sans facture client) ne sont pas repris, car ils n'ont pas de client.

Avec le filtre Facture client, la part de rebut du client est calculée sur l'ensemble de ses factures du lot, pas seulement sur la facture filtrée.

### 4. Performances

- Index ajouté sur `stock_move_line.lot_id` : 7,4 s → 0,3 s (analyse de 18 factures).
- Lectures des lots et des achats des lots en SQL groupées et mises en cache (`_preload_*`), écritures par l'ORM : 166 s → 140 s (9 mois, 47 751 lignes).
- Factures d'achat de tous les articles en une seule requête : 140 s → **55 s**, dont 37 s de `create()`, résultats identiques au centime.
- Calcul interactif, sans cron.
- Multi-processus non retenu : peu de gain avec des threads (GIL), et des processus séparés imposent des transactions séparées (analyse partielle en cas d'erreur).

### 5. Liste des lignes

- Liens cliquables : `widget="many2one"` (standard) et non `many2one_clickable`, qui n'existe pas (reste d'un module OCA v10). Sans widget, un many2one s'affiche en texte non cliquable.
- Retour à la ligne automatique sur ces colonnes : classe `o_is_analyse_marge_lot_ligne_list` sur la liste et règle CSS dans `static/src/scss/style.scss`.

## Boutons du formulaire

| Bouton | Résultat |
|---|---|
| **Calculer** | Recalcule les lignes de l'analyse (avec confirmation) |
| **Marge par client** | Tableau croisé par client |
| **Marge par enseigne** | Tableau croisé par enseigne |
| **Marge par commercial** | Tableau croisé par commercial |
| **Marge par produit** | Tableau croisé par article |
| **Marge par facture client** | Tableau croisé par facture / avoir (les rebuts sont regroupés sous « Aucun ») |

Les tableaux croisés n'affichent que la marge brute totale (factures, avoirs et rebuts) ; les autres mesures et le détail par type restent disponibles via les menus Mesures et d'en-tête du tableau. Trois compteurs sont présents en haut de la fiche : **Lignes**, **Anomalies** (toutes les lignes en anomalie : factures, avoirs et rebuts) et **Lots sans facture d'achat** (lignes de factures client en anomalie, CDC 2.5).

## Limites et points à valider

Méthode :

1. **Avoirs sur quantité** : le coût d'achat est annulé comme si la marchandise revenait en stock (comme l'ancien programme). Pour un avoir sans retour (qualité), la marge est surestimée du coût d'achat (jusqu'à 65 k€ sur le 1er semestre 2026). À trancher.
2. **Coûts d'achat** : avoirs fournisseurs et remises de fin d'année ignorés (coût surestimé), frais annexes des fournisseurs ignorés (coût sous-estimé). Seules les factures validées sont prises en compte.
3. **Transport (CDC 2.4)** : question ouverte ; exclu par défaut (articles non gérés par lot).
4. **Rebuts** : tous répartis sur les clients du lot, y compris les sinistres (ex : dégât des eaux).
5. **Approximations** : livraison en plusieurs fois sans BL sur la ligne de facture (répartition sur tous les lots de la commande) ; lot reçu plusieurs fois (dernière facture retenue) ; avoir non lié à une commande (repli sur l'article).

Incohérences possibles :

6. **Commercial** : celui de la fiche client **actuelle**, pas celui au moment de la facture.
7. **Enseigne** : celle de la facture pour les ventes, celle de la fiche client actuelle pour les rebuts.
8. **Période récente** : factures fournisseur pas encore saisies, donc nombreuses anomalies ; analyser de préférence des mois clôturés.
9. **Prix de repli** : dernière facture de l'article, parfois ancienne (19 lignes sur 529 à plus de 6 mois au 1er semestre 2026).
10. **Données** : commandes d'achat « Facturées » sans facture, lots en double ou au n° fantaisiste, facture fournisseur FF10544 datée de 7538, services paramétrés « suivi par lot ».

Contrôles faits sur le 1er semestre 2026 : unités identiques à la vente et à l'achat sur toutes les lignes ; 99 % des lignes avec une marge cohérente (159 lignes vendues à plus de 20 % sous le prix d'achat, 13 lignes sans prix d'achat).

Recommandation : rapprocher régulièrement les totaux de l'analyse de ceux de la comptabilité (ex : audit marge brute) sur les périodes clôturées.
