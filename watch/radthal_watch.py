#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radthal_watch.py - surveillance d'un noeud Radthal (Python 3, aucune dependance).

Ce que le script surveille :
  * BLOCAGE      : aucun nouveau bloc depuis STALL_MINUTES minutes
  * REORG        : la chaine a ete reecrite (les derniers blocs ont ete remplaces)
  * BRANCHE      : une branche concurrente de FORK_ALERT_LEN blocs ou plus est apparue
  * BLOC INVALIDE: le noeud a rejete un bloc (ex. bad-cb-height)
  * ISOLEMENT    : 0 connexion pendant NOPEER_MINUTES minutes
  * INJOIGNABLE  : le noeud ne repond plus au RPC

Les alertes vont dans les logs (docker logs) et, si NTFY_URL est renseigne, en
notification sur le telephone via https://ntfy.sh (application "ntfy").

Variables d'environnement (toutes facultatives) :
  RPC_URL            adresse RPC du noeud                    (defaut http://127.0.0.1:8332)
  RPC_COOKIE         fichier .cookie du noeud                (defaut /data/.cookie s'il existe)
  RPC_USER           nom d'utilisateur RPC (si pas de cookie)
  RPC_PASSFILE       fichier contenant le mot de passe RPC
  RPC_PASSWORD       ou le mot de passe directement
  NTFY_URL           ex. https://ntfy.sh/radthal-ab12cd34ef56
  WATCH_NAME         nom affiche dans les alertes            (defaut Radthal)
  POLL_SECONDS       delai entre deux controles              (defaut 30)
  STALL_MINUTES      blocage apres ... minutes sans bloc     (defaut 120)
  NOPEER_MINUTES     isolement apres ... minutes             (defaut 15)
  REORG_ALERT_DEPTH  alerte si au moins ... blocs remplaces  (defaut 2)
  FORK_ALERT_LEN     alerte si branche d'au moins ... blocs  (defaut 2)
  HEARTBEAT_MINUTES  ligne d'etat dans les logs              (defaut 60)

Options : --test-notify (envoie une notification de test)  --once (un seul controle)
"""
import base64
import json
import os
import signal
import sys
import time
import unicodedata
import urllib.error
import urllib.request

WINDOW = 500          # nombre de blocs recents gardes en memoire pour detecter une reorg
START_WINDOW = 50     # au demarrage on n'en charge que 50


class RpcError(Exception):
    def __init__(self, code, message):
        Exception.__init__(self, "RPC %s: %s" % (code, message))
        self.code = code
        self.message = message


class Rpc:
    """Client JSON-RPC minimal pour bitcoind."""

    def __init__(self, url, cookie=None, user=None, passfile=None, password=None):
        self.url = url
        self.cookie = cookie
        self.user = user
        self.passfile = passfile
        self.password = password

    def _auth(self):
        # Le cookie est relu a chaque appel : bitcoind le regenere a chaque demarrage.
        if self.cookie and os.path.exists(self.cookie):
            with open(self.cookie, "r") as f:
                cred = f.read().strip()
        else:
            pw = self.password
            if self.passfile:
                with open(self.passfile, "r") as f:
                    pw = f.read().strip()
            if self.user is None or pw is None:
                raise RpcError(-1, "aucun identifiant RPC (RPC_COOKIE ou RPC_USER + RPC_PASSFILE)")
            cred = "%s:%s" % (self.user, pw)
        return "Basic " + base64.b64encode(cred.encode("utf-8")).decode("ascii")

    def __call__(self, method, *params):
        body = json.dumps({"jsonrpc": "1.0", "id": "watch", "method": method,
                           "params": list(params)}).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", self._auth())
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            e.close()
            try:
                err = json.loads(raw).get("error")
            except ValueError:
                err = None
            if err:
                raise RpcError(err.get("code"), err.get("message"))
            raise RpcError(e.code, "HTTP %s %s" % (e.code, e.reason))
        if data.get("error"):
            raise RpcError(data["error"].get("code"), data["error"].get("message"))
        return data["result"]


def ascii_fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def make_ntfy(url, name):
    """Retourne une fonction notify(priorite, titre, texte) vers ntfy.sh (ou rien si pas d'URL)."""
    def notify(prio, title, body):
        if not url:
            return
        tags = {5: "rotating_light", 4: "warning", 3: "white_check_mark"}.get(prio, "information_source")
        req = urllib.request.Request(url, data=body.encode("utf-8"), method="POST")
        req.add_header("Title", ascii_fold("%s - %s" % (name, title)))   # en-tete : ASCII seulement
        req.add_header("Priority", str(prio))
        req.add_header("Tags", tags)
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    return notify


def fmt_dur(seconds):
    m = int(seconds // 60)
    if m < 120:
        return "%d min" % m
    return "%.1f h" % (m / 60.0)


class Watcher:
    def __init__(self, rpc, notify, cfg, clock=time.time, log=None):
        self.rpc = rpc
        self.notify = notify
        self.cfg = cfg
        self.clock = clock
        self.log = log or (lambda msg: print("%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True))
        self.tip_h = None
        self.tip_hash = None
        self.chain = {}            # hauteur -> hash (chaine active recente)
        self.last_change = None    # moment ou le dernier bloc est apparu
        self.active = {}           # alertes en cours : cle -> debut
        self.seen_tips = set()
        self.reorg_old_tips = set()
        self.max_reorg = 0
        self.rpc_fails = 0
        self.nopeer_since = None
        self.conns = None
        self.last_heartbeat = None

    # ---------- alertes ----------
    def emit(self, prio, title, body):
        self.log("[ALERTE] %s : %s" % (title, body))
        try:
            self.notify(prio, title, body)
        except Exception as e:  # une notification ratee ne doit jamais arreter la surveillance
            self.log("notification impossible : %s" % e)

    def raise_(self, key, prio, title, body):
        if key in self.active:
            return
        self.active[key] = self.clock()
        self.emit(prio, title, body)

    def clear(self, key, title, body):
        if key not in self.active:
            return
        since = self.active.pop(key)
        self.emit(3, title, "%s (duree : %s)" % (body, fmt_dur(self.clock() - since)))

    # ---------- un controle ----------
    def poll(self):
        try:
            info = self.rpc("getblockchaininfo")
        except (RpcError, OSError, ValueError) as e:
            self.rpc_fails += 1
            self.log("noeud injoignable (%d) : %s" % (self.rpc_fails, e))
            if self.rpc_fails >= 3:
                self.raise_("rpc", 4, "noeud injoignable", "Le noeud ne repond plus : %s" % e)
            return
        if self.rpc_fails:
            self.rpc_fails = 0
            self.clear("rpc", "noeud de nouveau joignable", "Le noeud repond a nouveau.")

        h, tip = info["blocks"], info["bestblockhash"]
        now = self.clock()
        try:
            if self.tip_hash is None:
                self.init_state(h, tip, now)
            elif tip != self.tip_hash:
                self.on_new_tip(h, tip, now)
            self.check_stall(info, h, now)
            self.check_peers(now)
            self.check_forks(h)
        except (RpcError, OSError, ValueError) as e:
            self.log("controle interrompu (on reessaie au prochain tour) : %s" % e)
            return
        self.heartbeat(now)

    def init_state(self, h, tip, now):
        lo = max(0, h - START_WINDOW + 1)
        for x in range(lo, h + 1):
            self.chain[x] = self.rpc("getblockhash", x)
        hdr = self.rpc("getblockheader", tip)
        self.tip_h, self.tip_hash = h, tip
        self.last_change = min(hdr.get("time", now), now)
        tips = self.rpc("getchaintips")
        self.seen_tips = set(t["hash"] for t in tips)
        forks = [t for t in tips if t["status"] in ("valid-fork", "invalid")]
        self.log("surveillance demarree : hauteur %d, %d branche(s) deja connue(s) ignoree(s)" % (h, len(forks)))

    def _agrees(self, height):
        return self.rpc("getblockhash", height) == self.chain.get(height)

    def on_new_tip(self, h, tip, now):
        old_h, old_hash = self.tip_h, self.tip_hash
        fork = None
        reorg = False
        if h >= old_h and self.rpc("getblockhash", old_h) == old_hash:
            start = old_h + 1                       # la chaine a simplement avance
        else:
            reorg = True
            top = min(old_h, h)
            heights = sorted(x for x in self.chain if x <= top)
            if heights and self._agrees(heights[0]):
                lo, hi = 0, len(heights) - 1        # dernier bloc commun, par dichotomie
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if self._agrees(heights[mid]):
                        lo = mid
                    else:
                        hi = mid - 1
                fork = heights[lo]
                start = fork + 1
            else:
                # divergence plus ancienne que ce que le script a en memoire
                depth_min = old_h - heights[0] + 1 if heights else 1
                self.chain = {}
                start = max(0, h - WINDOW + 1)
        # remet a jour la memoire de la chaine active
        for x in range(max(start, h - WINDOW + 1), h + 1):
            self.chain[x] = self.rpc("getblockhash", x)
        for x in [k for k in self.chain if k > h or k < h - WINDOW + 1]:
            del self.chain[x]

        was_stalled = "stall" in self.active
        self.tip_h, self.tip_hash, self.last_change = h, tip, now
        if was_stalled:
            self.clear("stall", "la chaine repart", "Nouveau bloc a la hauteur %d." % h)
        if not reorg:
            return
        self.reorg_old_tips.add(old_hash)
        if fork is None:
            depth = depth_min                       # au moins autant
            label = "au moins %d blocs" % depth_min
        else:
            depth = old_h - fork
            label = "%d bloc(s)" % depth
        if depth >= 1:
            self.max_reorg = max(self.max_reorg, depth)
            self.log("reorganisation : %s remplace(s), nouvelle hauteur %d" % (label, h))
        if depth >= self.cfg["reorg_depth"]:
            prio = 5 if depth >= 6 else 4
            where = "" if fork is None else " au-dessus du bloc %d" % fork
            self.emit(prio, "chaine reecrite : %s" % label,
                      "Les derniers blocs ont ete remplaces (%s)%s. Nouvelle hauteur : %d. "
                      "Un autre mineur plus puissant, ou un probleme de ton cote ?" % (label, where, h))

    def check_stall(self, info, h, now):
        if info.get("initialblockdownload"):
            return
        age = now - self.last_change
        if age > self.cfg["stall_min"] * 60:
            self.raise_("stall", 4, "plus de nouveau bloc depuis %s" % fmt_dur(age),
                        "Dernier bloc : hauteur %d. Le mineur est-il allume ? ckpool tourne-t-il ?" % h)

    def check_peers(self, now):
        self.conns = self.rpc("getconnectioncount")
        if self.conns == 0:
            if self.nopeer_since is None:
                self.nopeer_since = now
            elif now - self.nopeer_since > self.cfg["nopeer_min"] * 60:
                self.raise_("nopeer", 4, "noeud isole",
                            "0 connexion depuis %s. Un noeud isole peut miner sur sa propre branche."
                            % fmt_dur(now - self.nopeer_since))
        else:
            self.nopeer_since = None
            self.clear("nopeer", "noeud reconnecte", "%d connexion(s)." % self.conns)

    def check_forks(self, h):
        for t in self.rpc("getchaintips"):
            hsh = t["hash"]
            if hsh in self.seen_tips:
                continue
            self.seen_tips.add(hsh)
            status, blen, th = t["status"], t.get("branchlen", 0), t["height"]
            if hsh in self.reorg_old_tips or th < h - 1000:
                continue                              # deja signale par l'alerte de reorg / trop ancien
            if status == "valid-fork" and blen >= self.cfg["fork_len"]:
                self.emit(4, "branche concurrente de %d blocs" % blen,
                          "Une branche valide de %d blocs (hauteur %d) existe a cote de la chaine "
                          "principale (hauteur %d)." % (blen, th, h))
            elif status == "invalid":
                self.emit(3, "bloc invalide rejete",
                          "Le noeud a rejete une branche (hauteur %d). Regarde les logs du noeud "
                          "(mot cle : invalid / bad-)." % th)

    def heartbeat(self, now, force=False):
        every = self.cfg["heartbeat_min"] * 60
        if not force and self.last_heartbeat is not None and now - self.last_heartbeat < every:
            return
        self.last_heartbeat = now
        age = now - self.last_change if self.last_change else 0
        self.log("OK hauteur=%s connexions=%s dernier_bloc=il_y_a_%s plus_grande_reorg=%d alertes_en_cours=%s"
                 % (self.tip_h, self.conns, fmt_dur(age), self.max_reorg,
                    ",".join(sorted(self.active)) or "aucune"))


def env_num(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


def main(argv):
    cfg = {
        "stall_min": env_num("STALL_MINUTES", 120),
        "nopeer_min": env_num("NOPEER_MINUTES", 15),
        "reorg_depth": int(env_num("REORG_ALERT_DEPTH", 2)),
        "fork_len": int(env_num("FORK_ALERT_LEN", 2)),
        "heartbeat_min": env_num("HEARTBEAT_MINUTES", 60),
    }
    poll = env_num("POLL_SECONDS", 30)
    name = os.environ.get("WATCH_NAME", "Radthal")
    cookie = os.environ.get("RPC_COOKIE") or ("/data/.cookie" if os.path.exists("/data/.cookie") else None)
    rpc = Rpc(os.environ.get("RPC_URL", "http://127.0.0.1:8332"), cookie=cookie,
              user=os.environ.get("RPC_USER"), passfile=os.environ.get("RPC_PASSFILE"),
              password=os.environ.get("RPC_PASSWORD"))
    notify = make_ntfy(os.environ.get("NTFY_URL"), name)

    if "--test-notify" in argv:
        if not os.environ.get("NTFY_URL"):
            print("NTFY_URL n'est pas renseigne : rien a tester.")
            return 1
        notify(3, "test", "Si tu lis ce message sur ton telephone, les alertes fonctionnent.")
        print("Notification de test envoyee a", os.environ["NTFY_URL"])
        return 0

    w = Watcher(rpc, notify, cfg)
    if "--once" in argv:
        w.poll()
        w.heartbeat(w.clock(), force=True)
        return 0

    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))   # docker stop
    w.log("demarrage : %s, blocage=%g min, reorg>=%d, notification=%s"
          % (rpc.url, cfg["stall_min"], cfg["reorg_depth"], "oui" if os.environ.get("NTFY_URL") else "non (logs seulement)"))
    while True:
        try:
            w.poll()
        except Exception as e:  # on ne s'arrete jamais
            w.log("erreur inattendue : %r" % e)
        time.sleep(poll)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
