#!/usr/bin/env python3
"""Prepare les dossiers de l'application Umbrel "Radthal" avant le demarrage du noeud.

Lance en root par le service "init", qui s'arrete ensuite. Il fait trois choses, sans rien casser si on le relance :
  - cree les dossiers de donnees et les donne a l'utilisateur 1000 (celui du noeud et des pages) ;
  - cree une seule fois un secret RPC pour ckpool (/secrets/rpc-pass), lisible par lui seul ;
  - declare ce secret au noeud : une ligne "rpcauth=ckpool:..." dans bitcoin.conf, refaite a chaque demarrage (sel neuf,
    meme mot de passe). Le reste de bitcoin.conf n'est pas touche, et le noeud garde son cookie RPC pour les pages.

Dossiers (variables d'environnement) : DATA_DIR=/data, STATE_DIR=/state, SECRETS_DIR=/secrets, CKPOOL_LOGS=/ckpool-logs.
"""
import hashlib
import hmac
import os
import secrets
import sys

UID = GID = 1000
RPC_USER = "ckpool"


def own(path, mode):
    os.chmod(path, mode)
    if os.geteuid() == 0:                       # hors root (tests), on ne change pas le proprietaire
        os.chown(path, UID, GID)


def rpcauth_line(password, user=RPC_USER):
    """Meme calcul que share/rpcauth/rpcauth.py de Bitcoin Core : HMAC-SHA256 du mot de passe, avec un sel aleatoire."""
    salt = secrets.token_hex(16)
    digest = hmac.new(salt.encode("utf-8"), password.encode("utf-8"), hashlib.sha256).hexdigest()
    return "rpcauth=%s:%s$%s" % (user, salt, digest)


def main():
    data = os.environ.get("DATA_DIR", "/data")
    state = os.environ.get("STATE_DIR", "/state")
    sec = os.environ.get("SECRETS_DIR", "/secrets")
    logs = os.environ.get("CKPOOL_LOGS", "/ckpool-logs")
    for d, mode in ((data, 0o700), (state, 0o755), (sec, 0o700), (logs, 0o755)):
        os.makedirs(d, exist_ok=True)
        own(d, mode)

    pass_file = os.path.join(sec, "rpc-pass")
    password = ""
    if os.path.exists(pass_file):
        password = open(pass_file, encoding="utf-8").read().strip()
    if not password:
        password = secrets.token_hex(32)
        tmp = pass_file + ".tmp"
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o400), "w", encoding="utf-8") as f:
            f.write(password + "\n")
        os.replace(tmp, pass_file)
    own(pass_file, 0o400)

    conf = os.path.join(data, "bitcoin.conf")
    lines = []
    if os.path.exists(conf):
        lines = [l for l in open(conf, encoding="utf-8").read().splitlines() if not l.strip().startswith("rpcauth=%s:" % RPC_USER)]
    lines.append(rpcauth_line(password))
    tmp = conf + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, conf)
    own(conf, 0o600)
    print("dossiers prets, secret RPC de ckpool en place")


if __name__ == "__main__":
    sys.exit(main())
