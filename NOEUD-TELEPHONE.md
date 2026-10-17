# Un nœud Radthal sur un téléphone Android

**Procédure testée le 17 octobre 2026 sur un Samsung S26 Ultra** : compilation terminée, nœud synchronisé (20 591 blocs au
moment du test), hash du bloc genesis correct. Sur un autre modèle ou une autre version d'Android, des détails peuvent changer.

Principe : Termux (un terminal Linux pour Android) + une mini-installation Debian dedans. On y compile Radthal exactement
comme le fait le `Dockerfile` du dépôt, puis on lance le nœud. Le téléphone **vérifie** la chaîne, mais il n'est pas un nœud
public : les opérateurs mobiles bloquent les connexions entrantes. Pas de portefeuille ni de minage sur le téléphone.

## Avant de commencer

- Branche le téléphone au chargeur et connecte-le au **Wi-Fi** (pas de données mobiles).
- Prévois du temps pour la compilation (une quinzaine de minutes sur un téléphone récent haut de gamme, bien plus sur un modèle
  plus modeste). Le téléphone chauffe : enlève la coque et ne le pose pas sur un tissu.
- Il te faut l'adresse d'un nœud Radthal en ligne : celle de ton fichier `.env` (`SEED_NODE`) ou de « Nœuds connus » du README.
  Une adresse de réseau local (du type `192.168.x.x`) ne marche que si le téléphone est sur le même Wi-Fi que ce nœud.

## 1. Installer Termux

N'utilise pas la version du Play Store (trop ancienne). Va sur le site officiel **f-droid.org**, installe l'application F-Droid,
puis installe **Termux** depuis F-Droid (celle qui s'appelle seulement « Termux », sans les modules complémentaires).

Sur Samsung, l'installation d'une application hors du Play Store peut être bloquée par **Auto Blocker**
(Paramètres › Sécurité et confidentialité › Auto Blocker). Désactive-le le temps de l'installation, puis remets-le.

## 2. Régler Android pour qu'il ne coupe pas le travail

- Paramètres › Applications › Termux › Batterie : choisis **Sans restriction**.
- Quand Termux tourne, déroule sa notification et touche **Acquire wakelock**.

## 3. Installer Debian dans Termux

Dans Termux :

```bash
pkg update && pkg upgrade
pkg install proot-distro git
proot-distro install debian
proot-distro login debian
```

Quand l'invite de commandes affiche `root@localhost`, tu es dans Debian. Pour y revenir plus tard : ouvre Termux et retape
`proot-distro login debian`.

## 4. Compiler Radthal

Toujours dans Debian :

```bash
apt update
apt install -y build-essential cmake pkgconf python3 libevent-dev libboost-dev libsqlite3-dev git ca-certificates
git clone https://github.com/bryancarterdouglas/radthal.git
git clone --depth 1 --branch v31.1 https://github.com/bitcoin/bitcoin.git
cd bitcoin
git apply --check ../radthal/radthal.patch && git apply ../radthal/radthal.patch
echo "PATCH OK"
```

Puis la compilation, **dans un environnement propre** (obligatoire : sans cela, le compilateur de Debian mélange ses fichiers
avec ceux d'Android, et la compilation échoue avec des erreurs comme `memcpy was not declared` ou `__assert2`) :

```bash
rm -rf build
env -i HOME=/root TERM=xterm PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin bash -c 'cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_GUI=OFF -DBUILD_TESTS=OFF -DBUILD_BENCH=OFF -DBUILD_TX=OFF -DBUILD_UTIL=OFF -DBUILD_WALLET_TOOL=OFF -DENABLE_IPC=OFF -DWITH_ZMQ=OFF && cmake --build build -j3'
```

Garde l'écran allumé pendant la compilation. Si elle s'arrête (`Killed`, `signal 9`), relance la même commande avec `-j1` à la
place de `-j3` ; elle reprend là où elle s'était arrêtée. À la fin : `ls ~/bitcoin/build/bin` doit montrer `bitcoind` et `bitcoin-cli`.

## 5. Configurer et lancer le nœud

**Remplace `ADRESSE_DU_NOEUD:9333` par l'adresse d'un nœud Radthal avant de coller**, puis colle le bloc entier :

```bash
mkdir -p ~/radthal-data
printf 'server=1\nlisten=0\ndiscover=0\ndnsseed=0\nfixedseeds=0\naddnode=ADRESSE_DU_NOEUD:9333\n' > ~/radthal-data/bitcoin.conf
printf '#!/bin/sh\nexec env -i HOME=/root PATH=/usr/bin:/bin /root/bitcoin/build/bin/bitcoin-cli -datadir=/root/radthal-data "$@"\n' > /usr/local/bin/radthal-cli
printf '#!/bin/sh\nexec env -i HOME=/root PATH=/usr/bin:/bin /root/bitcoin/build/bin/bitcoind -datadir=/root/radthal-data -daemon "$@"\n' > /usr/local/bin/radthal-start
chmod +x /usr/local/bin/radthal-cli /usr/local/bin/radthal-start
radthal-start
```

## 6. Vérifier

Attends une minute, puis :

```bash
radthal-cli getconnectioncount
radthal-cli getblockchaininfo | grep -E '"blocks"|"headers"|"initialblockdownload"'
radthal-cli getblockhash 0
```

- `getconnectioncount` : 1 ou plus.
- `blocks` rejoint `headers`, et `initialblockdownload` passe à `false`.
- `getblockhash 0` doit afficher `00000000abe4c97c4b0efb25e556acfe8d76ffb08d2bbbe5bc5694f90459c198`. Si le résultat est différent,
  ce n'est pas la bonne chaîne : arrête-toi.

## Arrêter et relancer

```bash
radthal-cli stop     # arrêter proprement
radthal-start        # relancer
```

Si tu fermes Termux ou si Android l'arrête, le nœud s'arrête aussi. Pour le relancer : ouvre Termux, tape
`proot-distro login debian`, puis `radthal-start`.
