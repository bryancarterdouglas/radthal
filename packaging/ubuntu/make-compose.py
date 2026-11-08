#!/usr/bin/env python3
"""Genere le docker-compose.yml du paquet a partir de celui du depot (une seule source de verite) :
images toutes faites au lieu de la compilation, sans le service "watch" (il lit un fichier du depot),
reglages adaptes a l'application. Usage : make-compose.py <docker-compose.yml du depot> <sortie>"""
import sys
import yaml

src = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
svc = src["services"]
node = {k: v for k, v in svc["radthal"].items() if k not in ("build", "image")}
ui = {k: v for k, v in svc["interface"].items() if k not in ("build", "image")}
node["image"] = "${NODE_IMAGE:?image du noeud}"
ui["image"] = "${UI_IMAGE:?image des pages}"
# le noeud de depart a une valeur par defaut (le fichier de reglages peut la changer)
node["command"] = [("-addnode=${SEED_NODE:-radthal-seed.duckdns.org:9333}" if str(c).startswith("-addnode=") else c)
                   for c in node["command"]]
assert any("SEED_NODE:-" in str(c) for c in node["command"]), "ligne -addnode introuvable"
env = ui["environment"]
env["DOWN_HINT"] = "(il démarre peut-être encore : attends une minute)"
env["BACKUP_SHOW"] = "/data (ensuite : bouton « Copier mes sauvegardes » dans l'application Radthal)"
env["STATE_SHOW"] = "/state (copiée aussi par le bouton « Copier mes sauvegardes » de l'application Radthal)"
out = {"services": {"radthal": node, "interface": ui}, "volumes": {"radthal-data": None, "radthal-ui": None}}
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write("# GENERE par packaging/ubuntu/make-compose.py a partir de docker-compose.yml : ne pas modifier a la main.\n")
    f.write("# Lu par /usr/lib/radthal/radthal-stack ; les reglages viennent de /etc/radthal/radthal.env.\n")
    yaml.safe_dump(out, f, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=False)
