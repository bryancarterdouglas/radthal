#!/usr/bin/env python3
"""Menu commun des pages Radthal : toutes les pages derriere un seul port.

Utile quand on ne peut ouvrir qu'un port, par exemple dans Umbrel (une application = un port, protege par le
mot de passe d'Umbrel). Les pages elles-memes n'ecoutent alors qu'en local (127.0.0.1) : seul ce menu est joignable.

  /               -> la premiere page
  /p/<vue>/...    -> la page <vue>, avec une barre de menu ajoutee en haut

Reglages (variables d'environnement) : HUB_PORT (port du menu), VIEWS (pages, dans l'ordre du menu).
Les pages parlent a leur serveur avec des adresses relatives ("api/state"), donc elles marchent sous /p/<vue>/ sans changement.
"""
import http.client
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LABELS = {"node": "Nœud", "dashboard": "Tableau de bord", "mempool": "Mempool", "ckpool": "ckpool",
          "wallet": "Portefeuille", "stamp": "Horodatage"}
MAX_BODY = 5 * 1024 * 1024          # une requete (message, certificat...) reste toujours petite
KEEP = ("Content-Type", "Content-Disposition", "Cache-Control")      # en-tetes de la page recopies tels quels

CSS = ("#rdt-hub{position:sticky;top:0;z-index:10;background:#0d1320;border-bottom:1px solid #2e3a50;"
       "font:600 13px/1 Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}"
       "#rdt-hub div{max-width:1040px;margin:0 auto;padding:8px 12px;display:flex;gap:4px;overflow-x:auto;white-space:nowrap}"
       "#rdt-hub a{color:#96a2b4;text-decoration:none;padding:9px 14px;border-radius:999px;border:1px solid transparent}"
       "#rdt-hub a:hover{color:#f2f4f8}"
       "#rdt-hub a.on{color:#f2f4f8;background:#161e2e;border-color:#2e3a50;box-shadow:inset 0 -2px 0 #ff7a2f}")


def nav_html(views, current):
    links = "".join('<a href="/p/%s/"%s>%s</a>' % (v, ' class="on" aria-current="page"' if v == current else "", LABELS.get(v, v))
                    for v in views)
    return ('<style>%s</style><nav id="rdt-hub" aria-label="Pages Radthal"><div>%s</div></nav>' % (CSS, links)).encode("utf-8")


def make_handler(views, ports, host="127.0.0.1"):
    """views : liste des pages, dans l'ordre du menu ; ports : page -> port local de son serveur."""

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="text/plain; charset=utf-8", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                if k.lower() != "cache-control":
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, where):
            self.send_response(302)
            self.send_header("Location", where)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _route(self):
            sp = urllib.parse.urlsplit(self.path)
            if sp.path in ("/", "/index.html"):
                return self._redirect("/p/%s/" % views[0])
            m = re.fullmatch(r"/p/([a-z]+)(/.*)?", sp.path)
            if not m or m.group(1) not in ports:
                return self._send(404, b"not found")
            view, rest = m.group(1), m.group(2)
            if rest is None:                                   # /p/node -> /p/node/ : les adresses relatives en dependent
                return self._redirect("/p/%s/%s" % (view, "?" + sp.query if sp.query else ""))
            body = None
            if self.command == "POST":
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = -1
                if n < 0 or n > MAX_BODY:
                    return self._send(413, b"too large")
                body = self.rfile.read(n)
            fwd = {k: self.headers[k] for k in ("Content-Type", "Accept") if self.headers.get(k)}
            try:
                c = http.client.HTTPConnection(host, ports[view], timeout=90)
                try:
                    c.request(self.command, rest + ("?" + sp.query if sp.query else ""), body, fwd)
                    r = c.getresponse()
                    data, status = r.read(), r.status
                    out = {k: r.getheader(k) for k in KEEP if r.getheader(k)}
                finally:
                    c.close()
            except Exception:
                page = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="3">'
                        '<body style="font:16px system-ui;background:#090d15;color:#f2f4f8;padding:2em">'
                        "Cette page démarre. Elle se recharge toute seule dans quelques secondes…")
                return self._send(502, page.encode("utf-8"), "text/html; charset=utf-8")
            ctype = out.get("Content-Type", "")
            if status == 200 and ctype.startswith("text/html"):
                data = data.replace(b"<body>", b"<body>" + nav_html(views, view), 1)
            self._send(status, data, ctype or "application/octet-stream", out)

        do_GET = do_POST = _route

    return H


def make_server(addr, views, ports, host="127.0.0.1"):
    srv = ThreadingHTTPServer(addr, make_handler(views, ports, host))
    srv.daemon_threads = True
    return srv


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from launcher import PAGES                                  # vue -> (script, port local)
    wanted = [v.strip() for v in os.environ.get("VIEWS", "node").split(",") if v.strip()]
    wanted = [v for v in wanted if v in PAGES and v != "hub"]
    if not wanted:
        sys.exit("VIEWS vide ou inconnu")
    make_server(("0.0.0.0", int(os.environ.get("HUB_PORT", "3790"))), wanted, {v: PAGES[v][1] for v in wanted}).serve_forever()
