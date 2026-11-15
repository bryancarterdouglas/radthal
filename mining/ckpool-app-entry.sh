#!/bin/sh
# Lance ckpool dans l'application Umbrel "Radthal" (dossier radthal-one de la boutique Umbrel-radthal).
#
# ckpool et le noeud partagent le meme reseau : le noeud repond sur 127.0.0.1:8332. Le mot de passe RPC de ckpool est un
# secret cree une seule fois par le service "init" (interface/init.py) : il n'est ni dans l'image, ni lisible par les pages.
# Mode "-B" (solo) : le nom d'utilisateur du mineur est son adresse rdt1... ; 98 % du bloc vont a cette adresse et
# 2 % au developpeur (la donation est forcee a 2 % au minimum dans le ckpool de cette image, voir Dockerfile.ckpool).
set -eu

PASS="$(cat "${RPC_PASS_FILE:-/secrets/rpc-pass}")"
[ -n "$PASS" ] || { echo "mot de passe RPC vide" >&2; exit 1; }

CONF=/tmp/ckpool.conf
umask 077
cat > "$CONF" <<EOF
{
"btcd": [{"url": "127.0.0.1:8332", "auth": "ckpool", "pass": "$PASS", "notify": false}],
"serverurl": ["0.0.0.0:3333"],
"donation": 2,
"mindiff": 1,
"startdiff": 42,
"logdir": "${LOGDIR:-/ckpool/logs}"
}
EOF

exec /ckpool/src/ckpool -B -c "$CONF"
