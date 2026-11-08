#!/usr/bin/env python3
"""Tests du menu commun (hub.py) avec de faux serveurs de pages, sans noeud ni Docker.
Lancer :  python3 interface/test_hub.py"""
import http.client
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hub  # noqa: E402

PAGE = b'<!doctype html><html><head><style>x{}</style></head><body><div class="wrap">PAGE %s</div></body></html>'


def fake_page(name):
    class P(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _out(self, code, body, ctype, extra=()):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._out(200, PAGE % name.encode(), "text/html; charset=utf-8")
            elif self.path.startswith("/api/state"):
                self._out(200, json.dumps({"name": name, "path": self.path}).encode(), "application/json")
            elif self.path == "/registre.json":
                self._out(200, b"[]", "application/json", [("Content-Disposition", 'attachment; filename="r.json"')])
            else:
                self._out(404, b"nope", "text/plain")

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            self._out(200, json.dumps({"name": name, "got": self.rfile.read(n).decode(), "ct": self.headers.get("Content-Type")}).encode(),
                      "application/json")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), P)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class HubTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {v: fake_page(v) for v in ("node", "wallet")}
        ports = {v: s.server_address[1] for v, s in cls.pages.items()}
        ports["stamp"] = 1                                      # une page qui n'est pas (encore) lancee : rien n'ecoute
        cls.hub = hub.make_server(("127.0.0.1", 0), ["node", "wallet", "stamp"], ports)
        threading.Thread(target=cls.hub.serve_forever, daemon=True).start()
        cls.port = cls.hub.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.hub.shutdown()
        for s in cls.pages.values():
            s.shutdown()

    def req(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request(method, path, body, headers or {})
        r = c.getresponse()
        data = r.read()
        out = (r.status, dict((k.lower(), v) for k, v in r.getheaders()), data)
        c.close()
        return out

    def test_root_goes_to_first_page(self):
        st, h, _ = self.req("GET", "/")
        self.assertEqual((st, h["location"]), (302, "/p/node/"))

    def test_missing_slash_is_added(self):
        # sans le "/" final, les adresses relatives de la page ("api/state") pointeraient au mauvais endroit
        st, h, _ = self.req("GET", "/p/wallet")
        self.assertEqual((st, h["location"]), (302, "/p/wallet/"))

    def test_page_gets_menu_with_current_page_marked(self):
        st, h, data = self.req("GET", "/p/wallet/")
        self.assertEqual(st, 200)
        html = data.decode("utf-8")
        self.assertIn("PAGE wallet", html)
        self.assertEqual(html.count('id="rdt-hub"'), 1)
        self.assertLess(html.index('id="rdt-hub"'), html.index('class="wrap"'))          # le menu est tout en haut
        for v, label in (("node", "Nœud"), ("wallet", "Portefeuille"), ("stamp", "Horodatage")):
            self.assertIn('<a href="/p/%s/"' % v, html)
            self.assertIn(">%s</a>" % label, html)
        self.assertIn('<a href="/p/wallet/" class="on" aria-current="page">', html)
        self.assertNotIn('<a href="/p/node/" class="on"', html)
        self.assertEqual(h["cache-control"], "no-store")

    def test_relative_api_path_reaches_the_right_page(self):
        # le navigateur est sur /p/node/ : "api/state?x=1" devient /p/node/api/state?x=1
        st, h, data = self.req("GET", "/p/node/api/state?x=1")
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(data), {"name": "node", "path": "/api/state?x=1"})      # le serveur de la page voit son adresse habituelle
        self.assertNotIn(b"rdt-hub", data)                                                   # pas de menu dans le JSON
        self.assertEqual(self.req("GET", "/p/wallet/api/state")[2].count(b'"wallet"'), 1)

    def test_post_body_and_type_are_forwarded(self):
        body = json.dumps({"montant": "1,5", "note": "é"}).encode("utf-8")
        st, h, data = self.req("POST", "/p/wallet/api/send", body, {"Content-Type": "application/json"})
        self.assertEqual(st, 200)
        got = json.loads(data)
        self.assertEqual((got["name"], got["ct"]), ("wallet", "application/json"))
        self.assertEqual(json.loads(got["got"]), {"montant": "1,5", "note": "é"})

    def test_download_headers_are_kept(self):
        st, h, data = self.req("GET", "/p/node/registre.json")
        self.assertEqual((st, data), (200, b"[]"))
        self.assertIn("attachment", h["content-disposition"])

    def test_page_errors_are_passed_on(self):
        self.assertEqual(self.req("GET", "/p/node/nimporte-quoi")[0], 404)

    def test_unknown_page_and_paths(self):
        self.assertEqual(self.req("GET", "/p/inconnue/")[0], 404)
        self.assertEqual(self.req("GET", "/api/state")[0], 404)         # les pages ne sont joignables que par /p/<page>/
        self.assertEqual(self.req("GET", "/p/../etc/passwd")[0], 404)

    def test_page_not_started_yet_retries_by_itself(self):
        st, h, data = self.req("GET", "/p/stamp/")
        self.assertEqual(st, 502)
        self.assertIn(b'http-equiv="refresh"', data)

    def test_too_large_post_is_refused(self):
        # on annonce plus que la limite sans rien envoyer : le menu doit refuser avant de lire
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.putrequest("POST", "/p/wallet/api/send")
        c.putheader("Content-Length", str(hub.MAX_BODY + 1))
        c.endheaders()
        self.assertEqual(c.getresponse().status, 413)
        c.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
