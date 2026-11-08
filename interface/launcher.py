#!/usr/bin/env python3
"""Lance les pages web Radthal dans un seul conteneur : une page par port, relancee si elle s'arrete.

  node 3777 | dashboard 3778 | mempool 3779 | ckpool 3780 | wallet 3781 | stamp 3782

VIEWS (variable d'environnement) choisit les pages a lancer, par exemple VIEWS=node,wallet.
Les reglages des pages (RPC, PASSFILE, WALLET, STATE_DIR...) sont lus par les pages elles-memes.
"""
import os
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = {                       # vue : (script, port)
    "node": ("ui_node.py", 3777),
    "dashboard": ("ui_dashboard.py", 3778),
    "mempool": ("ui_node.py", 3779),
    "ckpool": ("ui_node.py", 3780),
    "wallet": ("ui_wallet.py", 3781),
    "stamp": ("ui_horodatage.py", 3782),
}
DEFAULT_VIEWS = "node,dashboard,mempool,wallet,stamp"       # ckpool : seulement si tu mines (VIEWS=...,ckpool)


def main():
    views = [v.strip() for v in os.environ.get("VIEWS", DEFAULT_VIEWS).split(",") if v.strip()]
    unknown = [v for v in views if v not in PAGES]
    if unknown or not views:
        sys.exit("VIEWS inconnu : %s (choix possibles : %s)" % (",".join(unknown) or "(vide)", ",".join(PAGES)))
    procs = {}                  # vue -> {"p": processus ou None, "since": lancement, "fails": arrets rapides de suite, "retry": heure du prochain essai}
    stopping = []

    def start(v):
        script, port = PAGES[v]
        env = dict(os.environ, VIEW=v, PORT=str(port))
        return subprocess.Popen([sys.executable, "-u", os.path.join(HERE, script)], env=env)

    def stop(*_):
        stopping.append(1)
        for r in procs.values():
            if r["p"] is not None and r["p"].poll() is None:
                r["p"].terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    for v in views:
        procs[v] = {"p": start(v), "since": time.time(), "fails": 0, "retry": 0}
        print("page %s : port %d" % (v, PAGES[v][1]), flush=True)
    while not stopping:
        time.sleep(1)
        now = time.time()
        for v, r in procs.items():
            if stopping:
                break
            if r["p"] is not None and r["p"].poll() is not None:
                # une page qui s'arrete est relancee ; si elle s'arrete en boucle, on espace les essais (jusqu'a 30 s)
                r["fails"] = r["fails"] + 1 if now - r["since"] < 30 else 0
                r["retry"] = now + min(30, 2 ** r["fails"])
                print("page %s arretee (code %s), nouvel essai dans %d s" % (v, r["p"].returncode, r["retry"] - now), flush=True)
                r["p"] = None
            if r["p"] is None and now >= r["retry"]:
                r["p"], r["since"] = start(v), now
    for r in procs.values():
        if r["p"] is not None:
            try:
                r["p"].wait(timeout=8)
            except subprocess.TimeoutExpired:
                r["p"].kill()


if __name__ == "__main__":
    main()
