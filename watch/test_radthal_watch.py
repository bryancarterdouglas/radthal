#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de radthal_watch.py avec un faux noeud (aucun vrai noeud necessaire).

Lancer :  python3 -m unittest -v watch/test_radthal_watch.py
"""
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radthal_watch as rw  # noqa: E402


class FakeChain:
    """Petite chaine de blocs simulee, avec les memes reponses RPC que bitcoind."""

    def __init__(self, length=120):
        self.counter = 0
        self.blocks = {}      # hash -> (height, prev)
        self.active = []      # hash par hauteur
        self.invalid = set()
        self.conns = 3
        self.ibd = False
        self.down = False
        self.tips_calls = 0
        g = self._new(None, 0)
        self.active.append(g)
        self.mine(length - 1)

    def _new(self, prev, height):
        self.counter += 1
        hsh = hashlib.sha256(str(self.counter).encode()).hexdigest()
        self.blocks[hsh] = (height, prev)
        return hsh

    def mine(self, n=1):
        for _ in range(n):
            self.active.append(self._new(self.active[-1], len(self.active)))

    def reorg(self, depth, newlen):
        """Remplace les `depth` derniers blocs par `newlen` nouveaux blocs."""
        del self.active[len(self.active) - depth:]
        self.mine(newlen)

    def side_branch(self, base_height, length):
        """Branche valide qui ne devient pas la chaine active."""
        prev = self.active[base_height]
        h = base_height
        for _ in range(length):
            h += 1
            prev = self._new(prev, h)
        return prev

    # --- API RPC ---
    def __call__(self, method, *params):
        if self.down:
            raise OSError("connexion refusee")
        return getattr(self, "rpc_" + method)(*params)

    def rpc_getblockchaininfo(self):
        return {"blocks": len(self.active) - 1, "bestblockhash": self.active[-1],
                "initialblockdownload": self.ibd}

    def rpc_getblockhash(self, h):
        if h < 0 or h >= len(self.active):
            raise rw.RpcError(-8, "Block height out of range")
        return self.active[h]

    def rpc_getblockheader(self, hsh):
        height, prev = self.blocks[hsh]
        return {"hash": hsh, "height": height, "time": 10_000_000 - 60, "previousblockhash": prev}  # il y a 1 min

    def rpc_getconnectioncount(self):
        return self.conns

    def rpc_getchaintips(self):
        self.tips_calls += 1
        children = set(p for (_, p) in self.blocks.values() if p)
        tips = []
        for hsh, (height, prev) in self.blocks.items():
            if hsh in children:
                continue
            if hsh == self.active[-1]:
                tips.append({"height": height, "hash": hsh, "branchlen": 0, "status": "active"})
                continue
            # longueur de la branche = blocs qui ne sont pas sur la chaine active
            blen, cur = 0, hsh
            while cur not in self.active:
                blen += 1
                cur = self.blocks[cur][1]
            status = "invalid" if hsh in self.invalid else "valid-fork"
            tips.append({"height": height, "hash": hsh, "branchlen": blen, "status": status})
        return tips


class Clock:
    def __init__(self):
        self.t = 10_000_000.0

    def __call__(self):
        return self.t

    def advance(self, minutes):
        self.t += minutes * 60


CFG = {"stall_min": 120, "nopeer_min": 15, "reorg_depth": 2, "fork_len": 2, "heartbeat_min": 60, "tips_min": 10}


class Base(unittest.TestCase):
    def setUp(self):
        self.chain = FakeChain()
        self.clock = Clock()
        self.alerts = []
        self.logs = []
        self.w = rw.Watcher(self.chain, lambda p, t, b: self.alerts.append((p, t, b)),
                            dict(CFG), clock=self.clock, log=self.logs.append)
        self.w.poll()   # initialisation
        self.alerts.clear()

    def titles(self):
        return [t for (_, t, _) in self.alerts]


class TestWatcher(Base):
    def test_startup_is_silent_and_ignores_old_forks(self):
        chain = FakeChain()
        chain.side_branch(60, 5)                      # branche ancienne deja presente au demarrage
        alerts = []
        w = rw.Watcher(chain, lambda p, t, b: alerts.append(t), dict(CFG), clock=self.clock, log=lambda m: None)
        w.poll()
        self.assertEqual(alerts, [])

    def test_normal_growth_no_alert(self):
        for _ in range(10):
            self.chain.mine(3)
            self.clock.advance(1)
            self.w.poll()
        self.assertEqual(self.alerts, [])
        self.assertEqual(self.w.max_reorg, 0)

    def test_depth1_reorg_logged_not_alerted(self):
        self.chain.reorg(1, 2)
        self.w.poll()
        self.assertEqual(self.alerts, [])
        self.assertEqual(self.w.max_reorg, 1)

    def test_depth3_reorg_alert_once_no_duplicate_fork_alert(self):
        self.chain.reorg(3, 4)
        self.w.poll()
        self.w.poll()
        self.clock.advance(11)                        # le controle des branches a lieu apres
        self.w.poll()
        self.assertEqual(len(self.alerts), 1, self.alerts)
        prio, title, _ = self.alerts[0]
        self.assertEqual(prio, 4)
        self.assertIn("3 bloc(s)", title)
        self.assertEqual(self.w.max_reorg, 3)

    def test_deep_reorg_is_urgent(self):
        self.chain.reorg(7, 8)
        self.w.poll()
        self.assertEqual(self.alerts[0][0], 5)

    def test_reorg_to_shorter_chain(self):
        self.chain.reorg(3, 2)        # nouvelle chaine plus courte (plus de travail cumule)
        self.w.poll()
        self.assertEqual(len(self.alerts), 1, self.alerts)
        self.assertIn("3 bloc(s)", self.alerts[0][1])

    def test_reorg_older_than_memory(self):
        self.chain.mine(10)
        self.w.poll()
        self.alerts.clear()
        self.chain.reorg(100, 101)    # plus profond que les 60 blocs gardes en memoire
        self.w.poll()
        self.assertEqual(len(self.alerts), 1, self.alerts)
        self.assertEqual(self.alerts[0][0], 5)
        self.assertIn("au moins", self.alerts[0][1])

    def test_reorg_during_burst_of_blocks(self):
        self.chain.reorg(4, 30)       # reorg ET beaucoup de nouveaux blocs entre deux controles
        self.w.poll()
        self.assertEqual(len(self.alerts), 1, self.alerts)
        self.assertIn("4 bloc(s)", self.alerts[0][1])
        # et la memoire est coherente : un nouveau bloc normal ne declenche rien
        self.chain.mine(1)
        self.w.poll()
        self.assertEqual(len(self.alerts), 1)

    def test_competing_branch_alert(self):
        self.chain.side_branch(100, 3)
        self.clock.advance(11)
        self.w.poll()
        self.assertEqual(self.titles(), ["branche concurrente de 3 blocs"])
        self.clock.advance(11)
        self.w.poll()
        self.assertEqual(len(self.alerts), 1)         # une seule fois

    def test_short_branch_ignored(self):
        self.chain.side_branch(100, 1)
        self.clock.advance(11)
        self.w.poll()
        self.assertEqual(self.alerts, [])

    def test_invalid_block_alert(self):
        tip = self.chain.side_branch(100, 1)
        self.chain.invalid.add(tip)
        self.clock.advance(11)
        self.w.poll()
        self.assertEqual(self.titles(), ["bloc invalide rejete"])

    def test_chaintips_not_requested_at_every_poll(self):
        before = self.chain.tips_calls
        for _ in range(10):
            self.clock.advance(0.5)                    # 30 s
            self.w.poll()
        self.assertEqual(self.chain.tips_calls, before)
        self.clock.advance(10)
        self.w.poll()
        self.assertEqual(self.chain.tips_calls, before + 1)

    def test_chaintips_backoff_when_node_is_slow(self):
        state = {"t": 0.0}
        chain = FakeChain()
        orig = chain.rpc_getchaintips

        def slow():
            state["t"] += 20                           # le noeud met 20 s a repondre
            return orig()
        chain.rpc_getchaintips = slow
        w = rw.Watcher(chain, lambda *a: None, dict(CFG), clock=self.clock,
                       log=lambda m: None, mono=lambda: state["t"])
        w.poll()
        self.assertGreaterEqual(w.next_tips_check - self.clock(), 2000)   # 100 x 20 s

    def test_old_branches_are_not_kept_in_memory(self):
        chain = FakeChain(length=1500)
        chain.side_branch(100, 5)                      # vieille branche, bien avant les 1000 derniers blocs
        alerts = []
        w = rw.Watcher(chain, lambda p, t, b: alerts.append(t), dict(CFG), clock=self.clock, log=lambda m: None)
        w.poll()
        self.assertEqual(len(w.seen_tips), 1)          # seulement la chaine active
        self.clock.advance(11)
        w.poll()
        self.assertEqual(alerts, [])

    def test_stall_alert_and_recovery(self):
        self.clock.advance(121)
        self.w.poll()
        self.assertEqual(len(self.alerts), 1)
        self.assertEqual(self.alerts[0][0], 4)
        self.assertIn("plus de nouveau bloc", self.alerts[0][1])
        self.clock.advance(30)
        self.w.poll()
        self.assertEqual(len(self.alerts), 1)         # pas de doublon
        self.chain.mine(1)
        self.w.poll()
        self.assertEqual(len(self.alerts), 2)
        self.assertEqual(self.alerts[1][1], "la chaine repart")
        self.assertEqual(self.alerts[1][0], 3)
        self.assertIn("duree", self.alerts[1][2])
        self.clock.advance(121)                        # et on peut re-alerter plus tard
        self.w.poll()
        self.assertEqual(len(self.alerts), 3)

    def test_no_stall_before_threshold(self):
        self.clock.advance(100)
        self.w.poll()
        self.assertEqual(self.alerts, [])

    def test_no_stall_alert_during_initial_block_download(self):
        self.chain.ibd = True
        self.clock.advance(500)
        self.w.poll()
        self.assertEqual(self.alerts, [])

    def test_isolated_node(self):
        self.chain.conns = 0
        self.w.poll()                                  # debut de l'isolement
        self.clock.advance(10)
        self.w.poll()
        self.assertEqual(self.alerts, [])
        self.clock.advance(6)
        self.w.poll()
        self.assertEqual(self.titles(), ["noeud isole"])
        self.chain.conns = 2
        self.w.poll()
        self.assertEqual(self.titles(), ["noeud isole", "noeud reconnecte"])

    def test_rpc_down_and_back(self):
        self.chain.down = True
        for _ in range(2):
            self.w.poll()
        self.assertEqual(self.alerts, [])              # on laisse 3 essais
        self.w.poll()
        self.assertEqual(self.titles(), ["noeud injoignable"])
        self.w.poll()
        self.assertEqual(len(self.alerts), 1)
        self.chain.down = False
        self.w.poll()
        self.assertEqual(self.titles(), ["noeud injoignable", "noeud de nouveau joignable"])

    def test_notification_failure_does_not_crash(self):
        def boom(p, t, b):
            raise OSError("ntfy hors ligne")
        w = rw.Watcher(self.chain, boom, dict(CFG), clock=self.clock, log=self.logs.append)
        w.poll()
        self.chain.reorg(3, 4)
        w.poll()                                       # ne doit pas lever d'exception
        self.assertTrue(any("notification impossible" in m for m in self.logs))


class MockNode(http.server.BaseHTTPRequestHandler):
    chain = None
    expected_auth = None
    ntfy = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        if self.path == "/ntfy":
            MockNode.ntfy.append((self.headers.get("Title"), self.headers.get("Priority"),
                                  self.headers.get("Tags"), body.decode("utf-8")))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")
            return
        import base64
        if self.headers.get("Authorization") != "Basic " + base64.b64encode(MockNode.expected_auth.encode()).decode():
            self.send_response(401)
            self.end_headers()
            return
        req = json.loads(body)
        try:
            res = MockNode.chain(req["method"], *req["params"])
            out, code = {"result": res, "error": None, "id": req["id"]}, 200
        except rw.RpcError as e:
            out, code = {"result": None, "error": {"code": e.code, "message": e.message}, "id": req["id"]}, 500
        data = json.dumps(out).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class TestHttp(unittest.TestCase):
    """Teste le vrai client HTTP : cookie, mot de passe, erreurs RPC et notifications ntfy."""

    def setUp(self):
        MockNode.chain = FakeChain()
        MockNode.ntfy = []
        MockNode.expected_auth = "__cookie__:aaa111"
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), MockNode)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.cookie = os.path.join(self.tmp.name, ".cookie")
        with open(self.cookie, "w") as f:
            f.write("__cookie__:aaa111\n")

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def url(self, path=""):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def test_cookie_auth_rpc_errors_and_rotation(self):
        rpc = rw.Rpc(self.url(), cookie=self.cookie)
        self.assertEqual(rpc("getblockchaininfo")["blocks"], 119)
        with self.assertRaises(rw.RpcError) as cm:
            rpc("getblockhash", 99999)
        self.assertEqual(cm.exception.code, -8)
        # le noeud redemarre : nouveau cookie, le client doit le relire tout seul
        MockNode.expected_auth = "__cookie__:bbb222"
        with self.assertRaises(rw.RpcError):
            rpc("getblockchaininfo")                  # ancien cookie -> 401
        with open(self.cookie, "w") as f:
            f.write("__cookie__:bbb222")
        self.assertEqual(rpc("getblockchaininfo")["blocks"], 119)

    def test_user_password_file_without_newline(self):
        passfile = os.path.join(self.tmp.name, "pw")
        with open(passfile, "w") as f:
            f.write("s3cret")                          # comme ~/radthal/rpcpass.txt : sans retour a la ligne
        MockNode.expected_auth = "radthal:s3cret"
        rpc = rw.Rpc(self.url(), user="radthal", passfile=passfile)
        self.assertEqual(rpc("getconnectioncount"), 3)

    def test_end_to_end_ntfy_notification(self):
        rpc = rw.Rpc(self.url(), cookie=self.cookie)
        notify = rw.make_ntfy(self.url("/ntfy"), "Radthal")
        w = rw.Watcher(rpc, notify, dict(CFG), clock=Clock(), log=lambda m: None)
        w.poll()
        MockNode.chain.reorg(3, 4)
        w.poll()
        self.assertEqual(len(MockNode.ntfy), 1, MockNode.ntfy)
        title, prio, tags, body = MockNode.ntfy[0]
        self.assertEqual(title, "Radthal - chaine reecrite : 3 bloc(s)")
        self.assertTrue(title.isascii())
        self.assertEqual(prio, "4")
        self.assertEqual(tags, "warning")
        self.assertIn("remplac", body)

    def test_ascii_fold(self):
        self.assertEqual(rw.ascii_fold("noeud injoignable à l'état"), "noeud injoignable a l'etat")


if __name__ == "__main__":
    unittest.main(verbosity=2)
