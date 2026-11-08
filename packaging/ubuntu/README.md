# Radthal pour Ubuntu (paquet .deb)

Un fichier à double-cliquer : il installe l'application **Radthal** (icône dans le menu des applications) et un service qui fait tourner
le nœud avec Docker, en arrière-plan et au démarrage de l'ordinateur.

## Comment ça marche

| Élément | Rôle |
|---|---|
| `src/radthal-app` | La fenêtre (GTK + WebKit) : menu à gauche, page à droite, sans barre d'adresse ni onglets. Fermer la fenêtre n'arrête **pas** le nœud. |
| `src/radthal-stack` | Le moteur (lancé en root par le service) : télécharge les images, démarre / arrête les conteneurs, écrit son avancement dans `/run/radthal/status` et son journal dans `/run/radthal/log`. L'application l'appelle avec `pkexec` (demande du mot de passe) pour installer Docker, arrêter / relancer le nœud et copier les sauvegardes. |
| `src/radthal.service` | Service systemd `radthal` (activé à l'installation). |
| `src/radthal.env` | Réglages (`/etc/radthal/radthal.env`) : nœud de départ, version des images, `UI_BIND`, `PEER_NAMES`… |
| `make-compose.py` | Génère le `docker-compose.yml` du paquet **à partir de celui du dépôt** (images toutes faites, sans `watch`) : une seule source de vérité. |
| `build-deb.sh` | Assemble le paquet : `dist/radthal_<version>_all.deb`. |

Les images viennent de `ghcr.io/bryancarterdouglas/radthal` et `…/radthal-interface` (construites par GitHub, voir `.github/workflows/images.yml`).
Si elles sont introuvables (hors ligne, paquet privé), le service **compile** le nœud sur l'ordinateur à partir des fichiers du paquet
(`/usr/share/radthal/build/`, 10 à 60 minutes la première fois).

Docker n'est pas une dépendance du paquet (pour ne pas entrer en conflit avec Docker installé par snap) : s'il manque, l'application propose de
l'installer (`apt install docker.io docker-compose-v2`).

Les données (chaîne, portefeuille) restent dans le volume Docker `radthal_radthal-data`, le même que celui de l'installation par `git clone` :
on peut passer de l'une à l'autre (arrête d'abord l'ancienne avec `docker compose down`, sans `-v`). Désinstaller le paquet ne supprime rien.

## Construire et tester

```bash
bash packaging/ubuntu/build-deb.sh            # il faut dpkg-deb, python3-yaml, python3-pil
python3 packaging/ubuntu/test_radthal_app.py     # logique de l'application + essai de la fenêtre avec une fausse bibliothèque graphique
```

La fenêtre elle-même (GTK / WebKit) ne peut être vue que sur un Ubuntu avec écran : les tests vérifient l'enchaînement du code, pas l'aspect.

## Installer

```bash
sudo apt install ./radthal_0.1.1_all.deb
```

Puis ouvrir **Radthal** dans le menu des applications. État du nœud sans fenêtre : `radthal-app --status`. Journal : `journalctl -u radthal`.
