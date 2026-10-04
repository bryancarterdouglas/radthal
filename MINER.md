# Miner Radthal en solo (ckpool)

Radthal se mine en SHA-256 : un mineur ASIC pour Bitcoin (Avalon, Antminer, Bitaxe…) convient. Il ne se branche pas
directement sur le nœud : il passe par **ckpool**, un petit serveur de minage qui tourne à côté du nœud. En mode « solo »,
quand ton mineur trouve un bloc, **toute la récompense va à ton adresse** `rdt1…`.

Plus il y a de mineurs honnêtes, plus la chaîne est difficile à réécrire : miner aide vraiment le réseau.

> Cette recette est celle du créateur du projet (Linux, Docker, nœud et ckpool sur la même machine, en « réseau hôte »).
> Elle remplace l'installation `docker compose` du README : ne lance pas les deux sur la même machine, ils utilisent
> le même port 9333.

## Avant de commencer

- Les commandes sont à taper sur la machine Linux qui fera tourner le nœud, dans le dossier de ce dépôt.
- Il te faut l'adresse d'un nœud Radthal en ligne (voir « Nœuds connus » du README). Sans connexion à un autre nœud,
  Bitcoin Core refuse de fournir du travail aux mineurs.
- Ne rends jamais accessibles depuis internet le port **3333** (mineurs) ni **8332** (RPC). Seul **9333** peut l'être.

## 1. Le nœud

```bash
docker build -t radthal .
mkdir -p ~/radthal-data
```

Crée le fichier `~/radthal-data/bitcoin.conf` (remplace le mot de passe et l'adresse du nœud) :

```bash
cat > ~/radthal-data/bitcoin.conf <<'CONF'
server=1
rpcuser=radthal
rpcpassword=CHOISIS-UN-LONG-MOT-DE-PASSE
dnsseed=0
fixedseeds=0
addnode=ADRESSE_DU_NOEUD:9333
CONF
sudo chown -R 1000:1000 ~/radthal-data && sudo chmod 600 ~/radthal-data/bitcoin.conf
```

Lance le nœud :

```bash
docker run -d --name radthal --restart unless-stopped --network host -v ~/radthal-data:/data radthal
```

Attends quelques minutes, puis vérifie : `docker exec radthal radthal-cli getconnectioncount` doit afficher 1 ou plus, et
`docker exec radthal radthal-cli getblockchaininfo` doit montrer `blocks` qui rattrape la chaîne.

## 2. Ton adresse de réception

```bash
docker exec radthal radthal-cli createwallet minage
docker exec radthal radthal-cli -rpcwallet=minage getnewaddress
```

Note l'adresse (elle commence par `rdt1`). Sauvegarde le portefeuille (voir le README, « Créer un portefeuille »).

## 3. ckpool

```bash
docker build -t ckpool -f mining/Dockerfile.ckpool mining
cp mining/ckpool.conf.example ~/ckpool.conf
nano ~/ckpool.conf
```

Dans `~/ckpool.conf`, remplace `MOT_DE_PASSE_RPC` par le mot de passe du `bitcoin.conf` et `rdt1_TON_ADRESSE` par ton adresse.
Garde le reste tel quel. Puis :

```bash
mkdir -p ~/ckpool-logs
docker run -d --name ckpool --restart unless-stopped --network host \
  -v ~/ckpool.conf:/ckpool.conf:ro -v ~/ckpool-logs:/ckpool/logs ckpool
docker logs ckpool --tail 20
```

## 4. Le mineur

Dans l'interface web de ton mineur, renseigne un serveur (pool) :

| Champ | Valeur |
|---|---|
| URL | `stratum+tcp://ADRESSE_IP_DE_TA_MACHINE:3333` |
| Utilisateur | ton adresse `rdt1…` (tu peux ajouter `.nom` derrière, ex. `rdt1….avalon1`) |
| Mot de passe | `x` |

Quand le mineur trouve un bloc, `docker logs ckpool` affiche `BLOCK ACCEPTED`.

## À savoir

- La difficulté s'ajuste tous les 2016 blocs, comme Bitcoin : un petit mineur peut attendre longtemps avant de trouver un bloc
  tant que la difficulté est élevée. C'est du minage en loterie.
- Les blocs minés ne sont dépensables qu'après 100 confirmations (règle de Bitcoin).
- Si les blocs ne défilent plus alors que le mineur tourne, regarde d'abord `docker logs ckpool --tail 50` et `docker logs radthal --tail 50`.
  Active aussi la surveillance (README, « Surveillance et alertes »).
