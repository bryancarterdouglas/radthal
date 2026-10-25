<p align="center">
  <img src="docs/logo-radthal.png" width="220" alt="Logo Radthal : un R bleu dans un cercle bleu, entouré de perles grises et de six points rouges">
</p>

<h1 align="center">Radthal</h1>

🇬🇧 [English version](README.en.md) · 🌐 [Site de présentation](https://bryancarterdouglas.github.io/radthal/)

Radthal est une crypto-monnaie expérimentale : un **fork de Bitcoin Core v31.1** avec les règles de Bitcoin
(SHA-256, ajustement de la difficulté tous les 2016 blocs, blocs de 10 minutes visés, halving tous les 210 000 blocs)
et sa propre chaîne, avec une différence de fond : une [part de 2 % pour le créateur](#la-part-du-développeur-2-) à partir du
bloc 25 000. Ce dépôt permet à **n'importe qui de faire tourner un nœud complet** et d'aider le réseau.

> Projet de bricoleur, sans aucune garantie. Radthal n'a aucun lien avec Bitcoin ni avec les développeurs de Bitcoin Core.
> Voir les [avertissements](#avertissements).

## Pourquoi Radthal ?

Sur Bitcoin, un mineur de salon n'a pratiquement aucune chance de trouver un bloc en solo : le réseau est des millions de fois plus
puissant que lui. Radthal reprend les mêmes règles sur une chaîne neuve et minuscule, où **un seul mineur domestique compte encore** et où
l'on peut tout observer de près : un nœud complet sur un Raspberry Pi, un serveur de minage, un portefeuille, des alertes. C'est un
terrain d'expérience et d'apprentissage, pas un placement.

Pour comprendre le principe en images : la [vidéo de présentation](https://youtu.be/20HJ0tP18fI) (voix générée par ordinateur).

Ce qu'il faut savoir avant de t'y intéresser :

- **L'avantage est temporaire.** Si beaucoup de mineurs arrivent, la difficulté monte et la part de chacun baisse.
- **Le réseau est petit, donc fragile.** Le point de contrôle protège l'historique (voir plus bas), mais il repose sur la confiance
  dans le créateur du projet : ce n'est pas aussi décentralisé que Bitcoin.
- **Une part de 2 % de chaque récompense va au créateur du projet à partir du bloc 25 000** (règle annoncée à l'avance, voir
  [La part du développeur](#la-part-du-développeur-2-)).
- **Aucune valeur, aucun marché, aucune promesse.** Radthal n'est pas un investissement et ne doit jamais être présenté comme tel.

## Paramètres du réseau

| | |
|---|---|
| Base de code | Bitcoin Core **v31.1** + `radthal.patch` |
| Algorithme de minage | SHA-256 (les ASIC Bitcoin fonctionnent) |
| Magic bytes | `52 44 54 31` (« RDT1 ») |
| Port réseau (P2P) | **9333** |
| Adresses | bech32 `rdt1…` · base58 : préfixe 60 (adresses), 85 (scripts) |
| Bloc genesis | 2026-10-03 00:00 UTC · message « Radthal 03/Oct/2026 premier bloc » · nonce 2161066804 · récompense 50 |
| Hash du genesis | `00000000abe4c97c4b0efb25e556acfe8d76ffb08d2bbbe5bc5694f90459c198` |
| Merkle root du genesis | `2ee4c2f3be7d69f29ad3245f440a3af80cb3a290b6c2390b84ae82b680ab0c1e` |
| Différences de consensus | BIP34 actif dès le bloc 17 ; SegWit et Taproot actifs dès le départ ; pas de « travail minimum » ni de bloc de confiance préconfigurés ; **part du développeur de 2 % dès le bloc 25 000** |
| Part du développeur | à partir du bloc **25 000** : 2 % de la récompense de chaque bloc vont à `rdt1qslzd9g3s34r7kc2pmhhvlv3uds37ddvvd5zuz6` (voir [La part du développeur](#la-part-du-développeur-2-)) |
| Point de contrôle | bloc **20 300**, hash `000000000000011f952520848001cef3f59c00afe6539290469827aefc1e77c3` (voir [Protection contre la réécriture](#protection-contre-la-réécriture-point-de-contrôle)) |

Le fichier `radthal.patch` fait foi : il contient toutes les modifications par rapport à Bitcoin Core v31.1.

## La part du développeur (2 %)

**À partir du bloc 25 000**, chaque bloc verse **2 % de sa récompense** à l'adresse du créateur du projet : 1 RDT sur les 50 RDT
d'un bloc (la part suit ensuite les halvings). Les 98 % restants vont au mineur. La quantité de RDT créée par bloc ne change pas :
la part est prélevée sur la récompense, rien n'est ajouté.

| | |
|---|---|
| Début | bloc **25 000** (les blocs d'avant ne changent pas) |
| Adresse | `rdt1qslzd9g3s34r7kc2pmhhvlv3uds37ddvvd5zuz6` |
| Montant | au moins 2 % de la récompense du bloc (hors frais de transaction) |

- **C'est public et vérifiable.** La règle est dans `radthal.patch` (fonctions `GetDevFeeAmount` et `GetDevFeeScript`) : à partir du
  bloc 25 000, un bloc dont la première transaction (la « coinbase ») ne verse pas cette part est refusé par les nœuds à jour
  (erreur `bad-cb-devfee`). Chaque bloc concerné contient donc une sortie vers cette adresse, visible dans l'explorateur de blocs.
- **Mets ton nœud à jour avant le bloc 25 000** (`git pull && docker compose up -d --build`, ou la recette de [MINER.md](MINER.md)).
  Un nœud qui n'est pas à jour accepte aussi des blocs sans cette part, que les nœuds à jour refusent : il se retrouverait sur une
  autre chaîne que le reste du réseau.
- **Si tu mines avec le `ckpool` de ce dépôt**, il verse la part tout seul (il prélève 2 % du total, frais compris) : il suffit de
  reconstruire son image (voir [MINER.md](MINER.md)). Un ancien `ckpool` produirait des blocs refusés à partir du bloc 25 000.
- **Si tu utilises un autre logiciel de minage**, la coinbase doit contenir une sortie vers l'adresse ci-dessus d'au moins le montant
  demandé. À partir du bloc 25 000, `getblocktemplate` donne le script et le montant dans le champ `devfee`, et `coinbasevalue`
  inclut cette part.
- **Pas d'accord avec cette règle ?** Radthal est un logiciel libre : tu peux garder l'ancienne version, mais tu suivras alors ta
  propre chaîne, séparée de celle-ci.

## Ce qu'il te faut

- Un ordinateur ou un Raspberry Pi sous Linux avec **Docker** (et le plugin `docker compose`) installé.
- 4 Go de RAM conseillés pour compiler (sinon mets `BUILD_JOBS=1` dans `.env`) et quelques Go libres.
- Une connexion internet. La chaîne est encore toute petite : la synchronisation prend quelques minutes.

## Installation

Première fois sur Linux ? Le [tutoriel vidéo pour débutant](https://youtu.be/NB6UsRZOKIE) (Linux, Umbrel, Docker, GitHub) montre
toutes les étapes ci-dessous, une par une.

```bash
git clone https://github.com/bryancarterdouglas/radthal.git
cd radthal
cp env.example .env
```

Ouvre `.env` et remplace `SEED_NODE` par l'adresse d'un nœud Radthal en ligne (voir « Nœuds connus » plus bas).

```bash
docker compose up -d --build
```

La première fois, Docker **compile** Bitcoin Core : compte de quelques dizaines de minutes sur un PC à plus d'une heure
sur un Raspberry Pi. Ensuite, le démarrage est immédiat.

Pas d'ordinateur sous la main ? Un téléphone Android peut aussi faire tourner un nœud qui vérifie la chaîne (il n'est pas
joignable depuis l'extérieur) : voir **[NOEUD-TELEPHONE.md](NOEUD-TELEPHONE.md)**, procédure testée sur un seul modèle de téléphone.

## Vérifier que ça marche

```bash
docker compose exec radthal radthal-cli getconnectioncount     # doit afficher 1 ou plus
docker compose exec radthal radthal-cli getblockchaininfo       # "blocks" doit grimper puis suivre la chaîne
docker compose exec radthal radthal-cli getblockhash 0          # doit afficher le hash du genesis ci-dessus
```

Si `getblockhash 0` affiche autre chose que le hash du tableau, tu n'es pas sur la bonne chaîne : ne continue pas.

Les logs en direct : `docker compose logs -f radthal` (Ctrl+C pour quitter, le nœud continue de tourner).

## Créer un portefeuille

```bash
docker compose exec radthal radthal-cli createwallet "monportefeuille"
docker compose exec radthal radthal-cli -rpcwallet=monportefeuille getnewaddress
```

L'adresse obtenue commence par `rdt1`. **Sauvegarde ton portefeuille** (`backupwallet`) et garde la copie ailleurs que
sur la même machine : si le disque meurt, les coins sont perdus.

```bash
docker compose exec radthal radthal-cli -rpcwallet=monportefeuille backupwallet /data/sauvegarde.dat
docker compose cp radthal:/data/sauvegarde.dat ./sauvegarde.dat
```

## Recevoir un paiement : combien de confirmations ?

Chaque nouveau bloc au-dessus d'une transaction est une « confirmation ». Plus il y en a, plus il est difficile de réécrire la
transaction. Repères prudents (en supposant des blocs de 10 minutes) :

| Situation | Confirmations conseillées |
|---|---|
| Test entre amis, montant symbolique | 10 (environ 1 h 40) |
| Montant qui compte | 100 (environ 17 h) |
| Gros montant, ou échange contre un bien | 300 ou plus, ou attendre que le réseau ait grandi |

Ces chiffres ne sont pas magiques : tant que la puissance totale du réseau est faible, même 100 confirmations peuvent être
réécrites par quelqu'un qui dispose de beaucoup plus de puissance. Ils pourront baisser quand le réseau grandira.
Les blocs que tu mines toi-même ne sont dépensables qu'après 100 confirmations (règle de Bitcoin).

Pour voir où en est un paiement :

```bash
docker compose exec radthal radthal-cli -rpcwallet=monportefeuille listtransactions "*" 5     # champ "confirmations"
docker compose exec radthal radthal-cli -rpcwallet=monportefeuille gettransaction IDENTIFIANT_DE_LA_TRANSACTION
```

## Surveillance et alertes

Le service `watch` du `docker-compose.yml` démarre avec le nœud. Il vérifie toutes les 30 secondes (les branches concurrentes, toutes les 10 minutes si `TIPS_CHECK_MINUTES` est supérieur à 0 dans `.env`) et signale dans les logs
(`docker compose logs -f watch`) :

- **plus de nouveau bloc** depuis `STALL_MINUTES` (120 par défaut) : le mineur est éteint, ckpool est planté…
- **chaîne réécrite** : les derniers blocs ont été remplacés (alerte à partir de 2 blocs, « urgente » à partir de 6) ;
- **branche concurrente** de 2 blocs ou plus, ou **bloc invalide** rejeté par le nœud ;
- **nœud isolé** (0 connexion pendant 15 minutes) ou **nœud injoignable**.

Pour recevoir les alertes sur ton téléphone, installe l'application gratuite **ntfy**, abonne-toi à un sujet au nom difficile à
deviner (par exemple `radthal-3fa9c21b7d40`, c'est public : toute personne qui connaît le nom peut le lire), puis mets
`NTFY_URL=https://ntfy.sh/radthal-3fa9c21b7d40` dans `.env` et relance `docker compose up -d`. Test :

```bash
docker compose exec watch python /app/radthal_watch.py --test-notify
```

La recherche des branches concurrentes demande au nœud la liste de **toutes** ses branches mortes. Sur un nœud neuf, elle est
minuscule et `TIPS_CHECK_MINUTES=10` est parfait. Sur un nœud qui a miné ses premiers blocs à difficulté 1 (des milliers de blocs
par seconde), elle peut compter des centaines de milliers de lignes, et chaque demande fait grossir la mémoire du nœud d'environ
300 Mo sans jamais la rendre : mets alors `TIPS_CHECK_MINUTES=0`. Le script se désactive aussi tout seul au-delà de 2000 branches.
L'alerte « chaîne réécrite » n'en dépend pas.

Le script (`watch/radthal_watch.py`, sans dépendance) et ses tests (`python3 -m unittest watch/test_radthal_watch.py`) sont dans ce
dépôt. La surveillance **prévient**, elle n'empêche rien : face à une vraie attaque, il faut plus de puissance de minage honnête.

## Protection contre la réécriture (point de contrôle)

Bitcoin Core a retiré ses points de contrôle (checkpoints) ; `radthal.patch` en remet un, sous sa forme la plus simple : le bloc
**20 300** doit avoir exactement le hash du tableau ci-dessus, et une fois ce bloc connu, plus aucune branche ne peut se greffer
sous lui. Une chaîne concurrente, même bien plus puissante, qui ne passe pas par ce bloc ne peut donc plus réécrire l'historique
d'avant. Elle peut encore réécrire ce qui vient après : le point de contrôle protège le passé, pas les derniers blocs.

À savoir :

- **Il ne protège que les nœuds qui ont cette version.** Un nœud plus ancien suivrait toujours la chaîne d'un attaquant : mets à jour
  (`git pull && docker compose up -d --build`).
- **C'est une règle de confiance** : le créateur du projet choisit quel bloc fait foi. C'est assumé pour une petite chaîne.
- Les en-têtes que ton nœud connaît déjà ne sont jamais revérifiés, une mise à jour ne touche donc pas à ta chaîne existante.
- Pour l'avancer plus tard : changer `RADTHAL_CHECKPOINT_HEIGHT` et `RADTHAL_CHECKPOINT_HASH` dans `radthal.patch` (fichier
  `src/validation.cpp`) et recompiler. Choisis un bloc enterré sous au moins 100 blocs, jamais un des tout derniers.

Vérifier que ton nœud est sur la bonne chaîne à cet endroit (doit afficher le hash du tableau) :

```bash
docker compose exec radthal radthal-cli getblockhash 20300
```

## Aider le réseau : ouvrir le port 9333

Par défaut ton nœud se connecte aux autres, mais personne ne peut se connecter à lui. Pour renforcer le réseau, redirige
le port **TCP 9333** de ta box vers ta machine. N'ouvre **que** ce port : jamais le RPC (8332 par défaut), qui donne accès au
portefeuille. Ouvrir le port rend ton adresse IP visible aux autres nœuds.

## Miner

Radthal utilise SHA-256, comme Bitcoin : un mineur ASIC pour Bitcoin convient. Plus il y a de mineurs honnêtes, plus la chaîne est
difficile à réécrire. Le guide pas à pas (nœud + serveur de minage `ckpool`) est dans **[MINER.md](MINER.md)**.

## L'interface (facultatif)

Pour suivre et utiliser son nœud sans ligne de commande, l'auteur a six petites pages web sur son Raspberry Pi (Umbrel).

**Quatre pages pour regarder** : **nœud**, **tableau de bord**, **mempool** et **ckpool**. Elles se mettent à jour toutes les
3 secondes et ne servent qu'à **regarder** : elles ne modifient rien. Ce sont de vraies captures d'un nœud en marche (solde masqué,
adresse du réseau local remplacée). Les ventilateurs animés du mineur sont une illustration ; les chiffres, eux, viennent du nœud et de ckpool.

| Tableau de bord | ckpool (le minage) | Nœud |
|:---:|:---:|:---:|
| <a href="docs/interface-tableau-de-bord.jpg"><img src="docs/interface-tableau-de-bord.jpg" width="260" alt="Tableau de bord Radthal : derniers blocs, surveillance des forks, difficulté, puissance du réseau, mon mineur"></a> | <a href="docs/interface-ckpool.jpg"><img src="docs/interface-ckpool.jpg" width="260" alt="Page ckpool : mon mineur, hashrate, parts acceptées, appareils, connexion d'un mineur"></a> | <a href="docs/interface-noeud.jpg"><img src="docs/interface-noeud.jpg" width="260" alt="Page du nœud : synchronisation, connexions, pairs, ports"></a> |

(Clique sur une image pour l'agrandir.)

**Deux pages qui agissent** : elles demandent le mot de passe du portefeuille à chaque action une fois qu'il est protégé (les clés
restent dans le nœud, les pages ne les voient jamais) :

- **Radthal Wallet** : solde, adresse de réception avec QR code, envoi de RDT (aperçu puis confirmation), historique, sauvegarde,
  protection du portefeuille par un mot de passe (à faire avant d'envoyer quoi que ce soit) et **messages dans la chaîne**.
- **Radthal Horodatage** : prouver qu'un document existait, sous cette forme exacte, à la date d'un bloc.

L'horodatage et les messages écrivent dans la chaîne par une sortie de données (`OP_RETURN`), que le programme du nœud accepte par défaut.
L'auteur les a essayés de bout en bout sur son propre nœud (envoi, confirmation dans un bloc, vérification).

| Radthal Wallet : messages | Radthal Horodatage |
|:---:|:---:|
| <a href="docs/interface-portefeuille-messages.jpg"><img src="docs/interface-portefeuille-messages.jpg" width="300" alt="Radthal Wallet : écrire un message de 280 caractères au plus et lire les messages trouvés dans la chaîne"></a> | <a href="docs/interface-horodatage.jpg"><img src="docs/interface-horodatage.jpg" width="300" alt="Radthal Horodatage : horodater un document, vérifier un document, liste des horodatages avec leur certificat"></a> |

(Captures du nœud de l'auteur, sur téléphone, découpées : le solde, l'adresse et le QR code du portefeuille ne sont pas montrés.)

*L'horodatage.* La page calcule l'empreinte du document (SHA-256) **dans ton navigateur** ; le document ne quitte jamais ton
appareil et seule l'empreinte (36 octets) est écrite dans la chaîne, pour environ 0,0000017 RDT de frais. Une fois le bloc trouvé, tu
télécharges un certificat (petit fichier `.json`) : avec le document exact, il permet à quelqu'un d'autre de vérifier l'horodatage
sur son propre nœud. Ce que ça prouve : un document identique existait au plus tard à la date du bloc. Ce que ça ne prouve pas :
qui l'a écrit, ni l'heure exacte (l'heure d'un bloc est fixée par son mineur). La chaîne est petite et le mineur de l'auteur la fait
avancer : pour un vrai litige, double la preuve avec un service reconnu. Changer une seule lettre du document change l'empreinte.

*Les messages.* On peut écrire un court message (280 caractères au plus) dans la chaîne. **Un message est public et définitif** :
tous ceux qui ont un nœud Radthal peuvent le lire, personne ne peut l'effacer ni le modifier. N'y mets jamais rien de personnel. La
page affiche aussi les messages des 3 000 derniers blocs, écrits par n'importe qui : ils ne sont ni vérifiés ni modérés, et seul le
texte est affiché (jamais de lien cliquable, d'image ni de code). Les photos et les vidéos ne passent pas : seule une petite
quantité de texte peut être écrite.

Les fichiers sont dans le dépôt **[Umbrel-radthal](https://github.com/bryancarterdouglas/Umbrel-radthal)**. Ils sont faits pour
l'installation de l'auteur et utilisent des fichiers de son Raspberry Pi : ce n'est **pas** une installation en un clic pour tout le
monde. Les pages sont en HTTP sur le réseau local : ne les expose jamais sur Internet. Le nœud Docker de ce dépôt n'en a pas besoin.

## Nœuds connus

| Adresse | Remarque |
|---|---|
| `radthal-seed.duckdns.org:9333` | nœud du créateur |

Tu fais tourner un nœud ouvert au public ? Ouvre une « issue » pour qu'on l'ajoute à la liste.

## Mettre à jour / arrêter

```bash
docker compose stop            # arrêt propre (le nœud sauvegarde son état)
docker compose up -d           # redémarrage
git pull && docker compose up -d --build     # mise à jour du dépôt
```

**Mets à jour avant le bloc 25 000** : la [part du développeur](#la-part-du-développeur-2-) devient alors une règle du réseau, et un nœud qui n'est pas à jour se sépare des autres.

Tes données (chaîne et portefeuille) sont dans le volume Docker `radthal_radthal-data` et survivent aux mises à jour.

## Dépannage

- **0 connexion** : l'adresse `SEED_NODE` est fausse ou le nœud est hors ligne. Vérifie dans `docker compose logs radthal`.
- **La compilation s'arrête sans message ou avec « Killed »** : manque de mémoire. Mets `BUILD_JOBS=1` dans `.env`.
- **`docker compose` introuvable** : installe le plugin Compose, ou utilise `docker-compose` (avec un tiret).
- **Le nœud dit « initial sync » alors qu'il est à jour, et plus aucun bloc n'est miné** : le dernier bloc a plus de 24 heures
  (coupure de courant, mineur éteint…), et Bitcoin Core refuse alors de fournir du travail aux mineurs. Le `docker-compose.yml` de ce
  README applique déjà les réglages `-maxtipage=315360000` et `-minimumchainwork`. Si tu as lancé ton nœud à la main (voir [MINER.md](MINER.md)), ajoute
  `maxtipage=315360000` et `minimumchainwork` (valeur dans [MINER.md](MINER.md)) à son `bitcoin.conf` et redémarre-le.

## Avertissements

- Radthal est un projet expérimental, sans valeur garantie. Ne promets jamais de gains à quelqu'un.
- Une chaîne jeune avec peu de puissance de minage est fragile : un mineur plus puissant peut réécrire les derniers blocs.
- Tu es seul responsable de tes clés et de tes sauvegardes.
- Un message écrit dans la chaîne est public et définitif. Un horodatage Radthal ne remplace pas un service reconnu en cas de litige.
- Aucune relation avec Bitcoin ou ses développeurs. Le code vient de [Bitcoin Core](https://github.com/bitcoin/bitcoin) (licence MIT).

---

## English summary

Radthal is an experimental fork of **Bitcoin Core v31.1** with Bitcoin's rules (SHA-256, 2016-block difficulty retarget,
10-minute target, 210,000-block halving) on its own chain, with one open difference: from block 25,000 on, 2% of every block reward
goes to the creator's address `rdt1qslzd9g3s34r7kc2pmhhvlv3uds37ddvvd5zuz6` (a consensus rule, announced in advance; see the French
section "La part du développeur"; update your node before block 25,000). This repository builds a full node with Docker:
`cp env.example .env`, set `SEED_NODE` to a running node, then `docker compose up -d --build`.
On Bitcoin, a home miner has practically no chance of finding a block solo; on this tiny new chain a single home miner still matters
(for as long as few people mine), which makes it a hands-on learning playground, not an investment.
Optional Umbrel web pages (author's own Raspberry Pi setup, not one-click): node, dashboard, mempool and ckpool views, plus a wallet
with short public on-chain messages (OP_RETURN, 280 characters) and a document timestamping page (SHA-256 fingerprint computed in the
browser, only the hash goes on-chain).
P2P port **9333**; never expose the RPC port. Genesis hash:
`00000000abe4c97c4b0efb25e556acfe8d76ffb08d2bbbe5bc5694f90459c198`. Experimental software, no warranty, no affiliation with Bitcoin.
Videos (in French, computer-generated voice): [overview](https://youtu.be/20HJ0tP18fI) and [step-by-step install tutorial](https://youtu.be/NB6UsRZOKIE).

Licence : MIT (voir `LICENSE`).
