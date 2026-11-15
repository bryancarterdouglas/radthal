#!/usr/bin/env python3
"""Genere le docker-compose.yml du paquet a partir de celui du depot (une seule source de verite) :
images toutes faites au lieu de la compilation, sans le service "watch" (il lit un fichier du depot),
reglages adaptes a l'application, et le minage : un service "init" (secret RPC de ckpool) et le service "ckpool"
(meme montage que l'application Umbrel Radthal : ckpool partage le reseau du noeud, le RPC reste sur 127.0.0.1).
Usage : make-compose.py <docker-compose.yml du depot> <sortie>"""
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
# --- minage -------------------------------------------------------------------------------------------------------
# Le port du mineur (stratum) est publie par le noeud (ckpool partage son reseau). Par defaut il est ouvert au reseau
# local, car un mineur est un autre appareil ; /etc/radthal/radthal.env peut le restreindre (STRATUM_BIND). Si le port
# 3333 est deja pris, radthal-stack met STRATUM_HOST_PORT a vide (Docker choisit alors un port libre) et n'allume pas ckpool.
node["ports"] = list(node["ports"]) + ["${STRATUM_BIND:-0.0.0.0}:${STRATUM_HOST_PORT-3333}:3333"]
node["depends_on"] = {"init": {"condition": "service_completed_successfully"}}
init = {
    "image": "${UI_IMAGE:?image des pages}",
    "user": "0:0",
    "restart": "no",
    "command": ["python", "/app/init.py"],
    "volumes": ["radthal-data:/data", "radthal-ui:/state", "radthal-secrets:/secrets", "radthal-ckpool-logs:/ckpool-logs"],
}
ckpool = {
    "image": "${CKPOOL_IMAGE:?image de ckpool}",
    "restart": "unless-stopped",
    "network_mode": "service:radthal",
    "depends_on": ["radthal"],
    "user": "1000:1000",
    "entrypoint": ["/usr/local/bin/ckpool-app-entry"],
    "volumes": ["radthal-secrets:/secrets:ro", "radthal-ckpool-logs:/ckpool/logs"],
}
ui["volumes"] = list(ui["volumes"]) + ["radthal-ckpool-logs:/ckpool/logs:ro"]
env["VIEWS"] = "${UI_VIEWS:-node,dashboard,mempool,ckpool,wallet,stamp}"
env["LOGS"] = "/ckpool/logs"
env["STRATUM_PORT"] = "3333"
env["MINING_NOTE"] = "${MINING_NOTE:-}"         # vide, sauf si radthal-stack desactive le minage (port pris, image absente)
env["STRATUM_HOST"] = "${STRATUM_HOST:-}"      # adresse de cet ordinateur sur le reseau local, trouvee par radthal-stack
out = {"services": {"init": init, "radthal": node, "ckpool": ckpool, "interface": ui},
       "volumes": {"radthal-data": None, "radthal-ui": None, "radthal-secrets": None, "radthal-ckpool-logs": None}}
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write("# GENERE par packaging/ubuntu/make-compose.py a partir de docker-compose.yml : ne pas modifier a la main.\n")
    f.write("# Lu par /usr/lib/radthal/radthal-stack ; les reglages viennent de /etc/radthal/radthal.env.\n")
    yaml.safe_dump(out, f, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=False)
