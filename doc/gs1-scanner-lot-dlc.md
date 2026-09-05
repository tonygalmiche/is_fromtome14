# Scanner GS1-128 pour lecture lot/DLC (agroalimentaire)

## Contexte

Besoin : équiper l'activité agroalimentaire d'un terminal de scan capable de lire les
codes-barres GS1-128 pour en extraire automatiquement le numéro de **lot** et la
**DLC** (date limite de consommation), afin d'alimenter `stock.lot` dans Odoo.

## Matériel envisagé

Zebra TC22 (terminal mobile Android avec scanner imageur intégré).

- Lit nativement toutes les symbologies 1D/2D standards : Code 128 (donc GS1-128),
  GS1 DataBar, GS1 DataMatrix.
- Ce qui compte n'est pas la lecture physique du code (matériel standard, aucun
  souci), mais le **parsing des Application Identifiers (AI)** GS1 contenus dans
  la chaîne scannée — ça, c'est le logiciel (Odoo) qui doit s'en charger, pas le
  terminal.

### Utilisation sans app native

- Le TC22 peut fonctionner en **mode clavier (keyboard wedge)** via DataWedge :
  le scan est injecté comme une saisie clavier dans le champ actif de la page —
  y compris dans le navigateur Chrome embarqué pointant sur l'app web Odoo.
- Donc **pas besoin de développer une application Android native** : navigateur
  Chrome + DataWedge en mode clavier + module Odoo qui parse le GS1 suffisent.
- Point de vigilance technique : le séparateur GS (ASCII 29, `\x1d`) entre AI de
  longueur variable (ex. le lot) est un caractère non imprimable, qui peut être
  perdu en traversant DataWedge → navigateur → champ Odoo si rien n'est configuré.
  **Il faudra configurer DataWedge pour remplacer ce caractère GS par un
  délimiteur imprimable** (ex. `|`) avant l'envoi au navigateur ; le parsing
  Odoo découpera alors la chaîne sur ce même délimiteur. Avec cette
  configuration, la lecture du lot/DLC fonctionne de façon fiable — c'est la
  méthode standard documentée par Zebra pour ce cas d'usage.

### Choix du module de scan : SE55 (plutôt que SE4710)

Deux moteurs de scan sont proposés en option sur le TC22 : **SE4710** (standard)
et **SE55** (nouvelle génération, retenu pour cet achat).

Raison du choix : les étiquettes agroalimentaires posent deux difficultés
récurrentes que le SE55 gère mieux que le SE4710 —

- **Étiquettes abîmées / sous film plastique** : le SE55 a un meilleur algorithme
  de décodage, plus tolérant aux codes partiellement effacés, froissés, ou
  déformés par les reflets/plis d'un film plastique d'emballage. Le SE4710
  décroche plus facilement dans ces conditions.
- **Lecture à distance** : le SE55 offre une portée de lecture plus grande et
  reste précis sur des codes plus petits ou plus loin du terminal, utile quand
  les cartons/palettes ne peuvent pas toujours être scannés de près.

Point important : ce choix est **purement matériel**. Le moteur de scan ne fait
que capturer et décoder l'image du code-barres en une chaîne de texte — que ce
soit le SE4710 ou le SE55, Odoo reçoit exactement la même chaîne GS1-128 décodée
en sortie. **Le choix du moteur n'a donc aucun impact sur le développement côté
Odoo** (le parsing des AI reste identique) ; il améliore uniquement la fiabilité
et le confort de lecture sur le terrain.

## Budget matériel — déploiement 4 terminaux

Parc cible à terme : **4 terminaux TC22 (SE55, batterie 3200 mAh)**.

| Poste | Réf. | Prix unitaire HT | Qté | Sous-total HT | Lien Gentag |
|---|---|---|---|---|---|
| Zebra TC22 (SE55 1D/2D, batterie 3200 mAh) | WLMT0-T22B6CBC2-A6 | 761,16 € | 4 | 3 044,64 € | [Fiche produit](https://www.gentag.fr/terminaux-portables/petits-terminaux/zebra-tc22-ordinateur-mobile-tc22) |
| Socle de charge 5 postes | CRD-TC2L-BS5CO-01 | 637,10 € | 1 | 637,10 € | [Fiche produit](https://www.gentag.fr/accessoires/socles-chargeurs/zebra-crd-tc2l-bs5co-01-socle-5-terminaux-tc22-tc27) |
| Adaptateur secteur (pour le socle) | PWR-BGA12V108W0WW | 114,90 € | 1 | 114,90 € | [Fiche produit](https://www.gentag.fr/alimentation/648-zebra-pwr-bga12v108w0ww-alimentation.html) |
| Cordon secteur (pour le socle) | KABDE3P18 | 4,50 € | 1 | 4,50 € | [Fiche produit](https://www.gentag.fr/cable/1065-GENTAG-KABDE3P18.html) |
| Coque de protection renforcée | SG-TC2L-BOOT-01 | 49,60 € | 4 | 198,40 € | [Fiche produit](https://www.gentag.fr/holsterprotection/1952-zebra-sg-tc2l-boot-01-coque-de-protection-tc22-et-tc27.html) |
| Dragonne | SG-TC2L-HSTRP1-01 *(réf. non retrouvée sur gentag.fr)* | ~2,60 € | 4 | ~10,40 € | *(non trouvée directement sur gentag.fr — à demander en devis)* |
| Batterie de rechange (5000 mAh) | BTRY-TC2L-3XMAXX-01 | 109,10 € | 2 | 218,20 € | [Fiche produit](https://www.gentag.fr/batteries/1948-zebra-btry-tc2l-3xmaxx-01-batterie-pour-zebra-tc21-tc26.html) |
| **Total estimatif** | | | | **≈ 4 228,14 € HT** | |

**Décisions actées**

- Coque de protection renforcée et dragonne : **confirmées** pour les 4 terminaux
  (protection contre chutes/chocs en environnement agroalimentaire).
- Batterie de rechange : **2 unités** (pas une par terminal) — suffisant pour
  couvrir un hot-swap ponctuel sans équiper chaque terminal individuellement.
- Socle de charge : **5 postes** choisi plutôt que 4 stations individuelles,
  pour la charge centralisée et une place disponible pour un 5ème terminal futur.

**Points de vigilance restants**

- La page produit du socle 5 postes et celle de la batterie de rechange
  mentionnent toutes deux, selon l'URL/le titre, tantôt "TC22/TC27" tantôt
  "TC21/TC26" — le contenu de fiche confirme la compatibilité TC22/TC27, mais
  **à faire reconfirmer explicitement par Gentag** avant commande pour éviter
  toute incompatibilité de connecteur/socle.
- La **dragonne** n'a pas été retrouvée avec une fiche produit directe sur
  gentag.fr (uniquement chez d'autres revendeurs) — à demander à Gentag en
  complément de devis, ou à commander ailleurs si non disponible chez eux.
- Câbles USB non inclus avec le socle — à clarifier si nécessaires (transfert de
  données) ou si le Wi-Fi suffit pour l'usage prévu.

## AI GS1 utiles pour l'agroalimentaire

| AI     | Signification         | Champ Odoo cible                          |
|--------|------------------------|--------------------------------------------|
| `01`   | GTIN                   | `product.barcode`                          |
| `10`   | Numéro de lot          | `stock.lot.name`                           |
| `17`   | DLC (date limite)      | `stock.lot.expiration_date` / `use_date`   |
| `15`   | DDM (best before)      | `stock.lot.use_date`                       |
| `21`   | Numéro de série        | `stock.lot.name`                           |
| `3xxx` | Poids variable         | quantité                                   |

## Community vs Enterprise — point clarifié

Odoo Community **n'est pas dépourvu** de tout support GS1 :

- Le **moteur de nomenclature** (`barcode.nomenclature` / `barcode.rule`, module
  de base `barcodes`) fait partie du **Community**. Il inclut déjà la
  "Default GS1 Nomenclature" avec les règles de parsing des AI, et une méthode
  Python (`parse_barcode()`) pour décoder une chaîne GS1-128 brute en dictionnaire
  de valeurs.
- Ce qui est **Enterprise uniquement**, c'est l'**application Barcode** avec son
  interface mobile clé-en-main (`stock_barcode` — écran de scan pour inventaires,
  transferts, etc.).

**Conséquence** : pas besoin de tout redévelopper depuis zéro. Le développement
nécessaire est un module custom raisonnable :

- un champ/widget sur la vue concernée (ex. réception, mouvement de stock) qui
  appelle `env['barcode.nomenclature'].parse_barcode()` sur la chaîne scannée,
- qui crée/retrouve le `stock.lot` correspondant et remplit `expiration_date`
  automatiquement à partir de l'AI `17`.

## Pour démarrer le dev : 1 seul terminal suffit

Les accessoires (coque, socle, batteries) ne sont utiles qu'au déploiement en
production. Pour le dev, il faut juste :

- 1 TC22 seul,
- accès Wi-Fi à une instance Odoo de dev,
- DataWedge configuré en mode clavier,
- quelques étiquettes/codes GS1-128 de test.



## Sources consultées

- [GS1 barcode nomenclature — Odoo 18.0 documentation](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/barcode/operations/gs1_nomenclature.html)
- [Overview of GS1 Barcode Nomenclature in Odoo 18 (Cybrosys)](https://www.cybrosys.com/blog/overview-of-gs1-barcode-nomenclature-in-odoo-18)
- [Default barcode nomenclature — Odoo 18.0 documentation](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/barcode/operations/barcode_nomenclature.html)
