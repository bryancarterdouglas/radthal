#!/usr/bin/env python3
"""Tests de la logique de l'application (sans GTK) et un essai de la fenetre avec une fausse bibliotheque graphique.
Lancer :  python3 packaging/ubuntu/test_radthal_app.py"""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def load_app():
    path = os.path.join(HERE, "src", "radthal-app")
    loader = importlib.machinery.SourceFileLoader("radthal_app", path)
    spec = importlib.util.spec_from_loader("radthal_app", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


app = load_app()


class Logic(unittest.TestCase):
    def test_describe_ready(self):
        self.assertEqual(app.describe("", "", "inactive", True, 0)[0], "ready")

    def test_describe_docker_missing_offers_install(self):
        c = app.describe("docker-missing", "", "active", False, 0)
        self.assertEqual((c[0], c[3]), ("docker-missing", "install"))
        self.assertEqual(app.describe("compose-missing", "", "active", False, 0)[3], "install")

    def test_describe_progress_has_no_button(self):
        for st in ("waiting-docker", "pulling", "building", "starting"):
            c = app.describe(st, "x", "activating", False, 0)
            self.assertIn(c[0], ("working", "waiting"))
            self.assertIsNone(c[3])

    def test_describe_running_then_stuck(self):
        self.assertEqual(app.describe("running", "", "active", False, 10)[0], "working")
        c = app.describe("running", "", "active", False, 400)
        self.assertEqual((c[0], c[3]), ("stuck", "restart"))

    def test_describe_stopped_error_and_no_status(self):
        self.assertEqual(app.describe("stopped", "", "inactive", False, 0)[3], "start")
        self.assertEqual(app.describe("error", "boum", "failed", False, 0)[3], "restart")
        self.assertIn("boum", app.describe("error", "boum", "failed", False, 0)[2])
        self.assertEqual(app.describe("", "", "failed", False, 0)[3], "restart")
        self.assertEqual(app.describe("", "", "inactive", False, 0)[3], "start")
        self.assertEqual(app.describe("", "", "activating", False, 0)[0], "working")

    def test_allowed_addresses(self):
        for ok in ("http://127.0.0.1:3777/", "http://127.0.0.1:3782/cert/x", "http://localhost:3781", "about:blank",
                   "blob:http://127.0.0.1:3782/abc", "data:text/plain,hi"):
            self.assertTrue(app.is_allowed(ok), ok)
        for bad in ("https://example.org/", "http://127.0.0.1:8332/", "http://127.0.0.1:3776/", "http://127.0.0.1:3783/",
                    "http://evil.example/http://127.0.0.1:3777/", "file:///etc/passwd", "", None):
            self.assertFalse(app.is_allowed(bad), bad)

    def test_downloads(self):
        self.assertTrue(app.is_download("http://127.0.0.1:3782/registre.json"))
        self.assertTrue(app.is_download("http://127.0.0.1:3782/cert/" + "a" * 64 + ".json"))
        self.assertFalse(app.is_download("http://127.0.0.1:3782/api/state"))
        self.assertFalse(app.is_download("http://127.0.0.1:3782/"))
        self.assertFalse(app.is_download("https://example.org/x.json"))

    def test_unique_path(self):
        with tempfile.TemporaryDirectory() as d:
            p1 = app.unique_path(d, "registre.json")
            open(p1, "w").close()
            p2 = app.unique_path(d, "registre.json")
            self.assertNotEqual(p1, p2)
            self.assertTrue(p2.endswith("registre (1).json"))
            self.assertEqual(os.path.dirname(app.unique_path(d, "../../etc/passwd")), d)

    def test_summarize(self):
        st = {"ok": True, "sections": [{"type": "cards", "items": [{"id": "height", "num": 23026}, {"id": "peers", "num": 1}]}]}
        self.assertEqual(app.summarize(st), "Nœud en marche · 23 026 blocs · 1 connexion")
        st["sections"][0]["items"][1]["num"] = 3
        self.assertTrue(app.summarize(st).endswith("3 connexions"))
        self.assertIn("ne répond pas", app.summarize({"ok": False, "sections": []}))
        self.assertEqual(app.summarize(None), "")
        self.assertEqual(app.summarize({"ok": True, "sections": ["bizarre", {"items": None}]}), "Nœud en marche")

    def test_status_file(self):
        with tempfile.TemporaryDirectory() as d:
            old = app.RUN_DIR
            app.RUN_DIR = d
            try:
                self.assertEqual(app.read_status(), ("", ""))
                with open(os.path.join(d, "status"), "w") as f:
                    f.write("pulling\nimage x\n")
                self.assertEqual(app.read_status(), ("pulling", "image x"))
                self.assertIn("pas encore de journal", app.log_tail())
                with open(os.path.join(d, "log"), "w") as f:
                    f.write("a\nb\n")
                self.assertEqual(app.log_tail(1), "b\n")
            finally:
                app.RUN_DIR = old


# ---- essai de la fenetre avec une fausse bibliotheque : verifie l'enchainement du code, pas l'aspect ni les vrais appels GTK
class Meta(type):
    def __getattr__(cls, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return Any()


class Any(metaclass=Meta):
    """Accepte tout appel et tout attribut."""
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return Any()
    def __getattr__(self, n):
        if n.startswith("__"):          # les outils de Python (copie, inspection...) ne doivent pas tourner en boucle sur la fausse bibliotheque
            raise AttributeError(n)
        return Any()
    def __iter__(self): return iter(())
    def __bool__(self): return True


class FakeModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        cls = type(name, (Any,), {})
        setattr(self, name, cls)
        return cls


class Fake(unittest.TestCase):
    def setUp(self):
        self.saved = {k: sys.modules.get(k) for k in ("gi", "gi.repository")}
        glib = FakeModule("GLib")
        glib.idle_add = lambda f, *a: f(*a)
        glib.timeout_add = lambda ms, f, *a: 1
        glib.filename_to_uri = lambda p, h: "file://" + p
        glib.get_user_special_dir = lambda d: tempfile.gettempdir()
        glib.set_prgname = lambda n: None
        glib.set_application_name = lambda n: None
        glib.UserDirectory = types.SimpleNamespace(DIRECTORY_DOWNLOAD=1)
        repo = types.ModuleType("gi.repository")
        for n in ("Gtk", "Gdk", "Gio", "WebKit2"):
            setattr(repo, n, FakeModule(n))
        repo.GLib = glib
        repo.WebKit2.PolicyDecisionType = types.SimpleNamespace(NAVIGATION_ACTION=0, NEW_WINDOW_ACTION=1, RESPONSE=2)
        gi = types.ModuleType("gi")
        gi.require_version = lambda *a: None
        gi.repository = repo
        sys.modules["gi"], sys.modules["gi.repository"] = gi, repo
        self.repo = repo

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    def test_window_flow(self):
        captured = {}
        orig = app.threading.Thread
        app.threading.Thread = lambda target=None, daemon=None, **k: types.SimpleNamespace(start=lambda: target())
        try:
            # on recupere la classe Win en interceptant App().run
            real_run = None
            Gtk = self.repo.Gtk

            class App(Gtk.Application):
                def run(self, argv):
                    captured["app"] = self
                    return 0
            Gtk.Application = App
            self.assertEqual(app.run_gui(), 0)
        finally:
            app.threading.Thread = orig
        a = captured["app"]
        # l'App fabriquee par run_gui est la classe interne : on la reutilise pour creer la fenetre
        a.do_activate()
        win = a.win
        self.assertIsNotNone(win)
        # tous les etats de l'ecran d'attente
        for st, svc, state in (("docker-missing", "active", None), ("pulling", "activating", None), ("running", "active", None),
                               ("stopped", "inactive", None), ("error", "failed", None), ("", "inactive", None)):
            win.apply(st, "detail", svc, state)
        # les pages repondent : la page choisie s'affiche, une seconde fois sans recharger
        state = {"ok": True, "sections": [{"items": [{"id": "height", "num": 5}]}]}
        win.apply("running", "", "active", state)
        win.apply("running", "", "active", state)
        self.assertTrue(win.ready)
        win.apply("stopped", "", "inactive", None)        # le noeud s'arrete puis revient
        self.assertFalse(win.ready)
        win.apply("running", "", "active", state)
        # navigation
        types_ = self.repo.WebKit2.PolicyDecisionType

        def decision(uri):
            d = Any()
            d.calls = []
            d.get_navigation_action = lambda: types.SimpleNamespace(get_request=lambda: types.SimpleNamespace(get_uri=lambda: uri))
            d.download = lambda: d.calls.append("download")
            d.ignore = lambda: d.calls.append("ignore")
            d.use = lambda: d.calls.append("use")
            d.is_mime_type_supported = lambda: False
            return d

        d = decision("http://127.0.0.1:3777/")
        self.assertFalse(win.on_policy(None, d, types_.NAVIGATION_ACTION))
        d = decision("https://example.org/")
        self.assertTrue(win.on_policy(None, d, types_.NAVIGATION_ACTION))
        self.assertIn("ignore", d.calls)
        d = decision("http://127.0.0.1:3782/registre.json")
        self.assertTrue(win.on_policy(None, d, types_.NAVIGATION_ACTION))
        self.assertIn("download", d.calls)
        d = decision("http://127.0.0.1:3777/")
        self.assertTrue(win.on_policy(None, d, types_.RESPONSE))
        self.assertIn("download", d.calls)
        self.assertIsNone(win.on_create(None, types.SimpleNamespace(get_request=lambda: types.SimpleNamespace(get_uri=lambda: "https://example.org/"))))
        # telechargement
        dl = Any()
        dl.dest = None
        dl.set_destination = lambda u: setattr(dl, "dest", u)
        self.assertTrue(win.on_destination(dl, "registre.json"))
        self.assertTrue(dl.dest.startswith("file://"))
        win.on_download_done(dl)
        # clic sur les boutons
        calls = []
        real_run = app.subprocess.run
        app.subprocess.run = lambda cmd, **k: (calls.append(cmd), types.SimpleNamespace(returncode=0, stdout="", stderr=""))[1]
        try:
            win.last_action = "install"
            win.on_action(None)
        finally:
            app.subprocess.run = real_run
        self.assertEqual(calls, [["pkexec", app.STACK, "install-docker"]])
        win.on_details(None)
        win.on_about(None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
