# Radthal

Radthal est une crypto-monnaie expérimentale : un **fork de Bitcoin Core v31.1** avec les règles de Bitcoin
(SHA-256, ajustement de la difficulté tous les 2016 blocs, blocs de 10 minutes visés, halving tous les 210 000 blocs)
et sa propre chaîne. Ce dépôt permet à **n'importe qui de faire tourner un nœud complet** et d'aider le réseau.

> Projet de bricoleur, sans aucune garantie. Radthal n'a aucun lien avec Bitcoin ni avec les développeurs de Bitcoin Core.
> Voir les [avertissements](#avertissements).

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
| Différences de consensus | BIP34 actif dès le bloc 17 ; SegWit et Taproot actifs dès le départ ; pas de « travail minimum » ni de bloc de confiance préconfigurés |
| Point de contrôle | bloc **20 300**, hash `000000000000011f952520848001cef3f59c00afe6539290469827aefc1e77c3` (voir [Protection contre la réécriture](#protection-contre-la-réécriture-point-de-contrôle)) |

Le fichier `radthal.patch` fait foi : il contient toutes les modifications par rapport à Bitcoin Core v31.1.

## Ce qu'il te faut

- Un ordinateur ou un Raspberry Pi sous Linux avec **Docker** (et le plugin `docker compose`) installé.
- 4 Go de RAM conseillés pour compiler (sinon mets `BUILD_JOBS=1` dans `.env`) et quelques Go libres.
- Une connexion internet. La chaîne est encore toute petite : la synchronisation prend quelques minutes.

## Installation

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

Tes données (chaîne et portefeuille) sont dans le volume Docker `radthal_radthal-data` et survivent aux mises à jour.

## Dépannage

- **0 connexion** : l'adresse `SEED_NODE` est fausse ou le nœud est hors ligne. Vérifie dans `docker compose logs radthal`.
- **La compilation s'arrête sans message ou avec « Killed »** : manque de mémoire. Mets `BUILD_JOBS=1` dans `.env`.
- **`docker compose` introuvable** : installe le plugin Compose, ou utilise `docker-compose` (avec un tiret).
- **Le nœud dit « initial sync » alors qu'il est à jour, et plus aucun bloc n'est miné** : le dernier bloc a plus de 24 heures
  (coupure de courant, mineur éteint…), et Bitcoin Core refuse alors de fournir du travail aux mineurs. Ajoute `maxtipage=315360000`
  au `bitcoin.conf` du nœud qui sert au minage (voir [MINER.md](MINER.md)) et redémarre-le. Le nœud simple de ce README, qui ne
  mine pas, peut s'en passer.

## Avertissements

- Radthal est un projet expérimental, sans valeur garantie. Ne promets jamais de gains à quelqu'un.
- Une chaîne jeune avec peu de puissance de minage est fragile : un mineur plus puissant peut réécrire les derniers blocs.
- Tu es seul responsable de tes clés et de tes sauvegardes.
- Aucune relation avec Bitcoin ou ses développeurs. Le code vient de [Bitcoin Core](https://github.com/bitcoin/bitcoin) (licence MIT).

---

## English summary

Radthal is an experimental fork of **Bitcoin Core v31.1** with Bitcoin's rules (SHA-256, 2016-block difficulty retarget,
10-minute target, 210,000-block halving) on its own chain. This repository builds a full node with Docker:
`cp env.example .env`, set `SEED_NODE` to a running node, then `docker compose up -d --build`.
P2P port **9333**; never expose the RPC port. Genesis hash:
`00000000abe4c97c4b0efb25e556acfe8d76ffb08d2bbbe5bc5694f90459c198`. Experimental software, no warranty, no affiliation with Bitcoin.

Licence : MIT (voir `LICENSE`).
