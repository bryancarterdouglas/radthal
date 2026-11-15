#!/usr/bin/env python3
"""Tests de init.py (preparation des dossiers et du secret RPC de ckpool), sans Docker.
Lancer :  python3 interface/test_init.py"""
import hashlib
import hmac
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INIT = os.path.join(HERE, "init.py")


def run_init(root):
    env = dict(os.environ, DATA_DIR=root + "/data", STATE_DIR=root + "/ui", SECRETS_DIR=root + "/secrets", CKPOOL_LOGS=root + "/logs")
    return subprocess.run([sys.executable, "-I", INIT], env=env, capture_output=True, text=True, timeout=30)


def auth_ok(line, password):
    user, rest = line[len("rpcauth="):].split(":", 1)
    salt, digest = rest.split("$", 1)
    return user == "ckpool" and hmac.compare_digest(digest, hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest())


class InitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def conf_lines(self):
        with open(self.root + "/data/bitcoin.conf") as f:
            return f.read().splitlines()

    def password(self):
        with open(self.root + "/secrets/rpc-pass") as f:
            return f.read().strip()

    def test_first_start_creates_everything(self):
        r = run_init(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        for d in ("data", "ui", "secrets", "logs"):
            self.assertTrue(os.path.isdir(self.root + "/" + d), d)
        self.assertEqual(len(self.password()), 64)
        lines = [l for l in self.conf_lines() if l.startswith("rpcauth=")]
        self.assertEqual(len(lines), 1)
        self.assertTrue(auth_ok(lines[0], self.password()))        # le noeud accepterait bien ce mot de passe

    def test_permissions_are_private(self):
        run_init(self.root)
        mode = lambda p: stat.S_IMODE(os.stat(self.root + "/" + p).st_mode)
        self.assertEqual(mode("secrets/rpc-pass"), 0o400)
        self.assertEqual(mode("secrets"), 0o700)
        self.assertEqual(mode("data"), 0o700)
        self.assertEqual(mode("data/bitcoin.conf"), 0o600)

    def test_restart_keeps_password_and_never_duplicates_the_line(self):
        run_init(self.root)
        first = self.password()
        run_init(self.root)
        run_init(self.root)
        self.assertEqual(self.password(), first)
        lines = [l for l in self.conf_lines() if l.startswith("rpcauth=")]
        self.assertEqual(len(lines), 1)
        self.assertTrue(auth_ok(lines[0], first))

    def test_other_settings_in_bitcoin_conf_are_kept(self):
        os.makedirs(self.root + "/data")
        with open(self.root + "/data/bitcoin.conf", "w") as f:
            f.write("maxconnections=20\nrpcauth=autre:abc$def\n")
        run_init(self.root)
        lines = self.conf_lines()
        self.assertIn("maxconnections=20", lines)
        self.assertIn("rpcauth=autre:abc$def", lines)               # le compte d'un autre outil n'est pas touche

    def test_stale_ckpool_line_is_replaced_when_password_is_lost(self):
        run_init(self.root)
        os.chmod(self.root + "/secrets/rpc-pass", 0o600)
        os.remove(self.root + "/secrets/rpc-pass")                  # secret perdu : un nouveau est cree
        run_init(self.root)
        lines = [l for l in self.conf_lines() if l.startswith("rpcauth=ckpool:")]
        self.assertEqual(len(lines), 1)
        self.assertTrue(auth_ok(lines[0], self.password()))

    def test_salt_changes_but_old_hash_is_not_kept(self):
        run_init(self.root)
        a = [l for l in self.conf_lines() if l.startswith("rpcauth=")][0]
        run_init(self.root)
        b = [l for l in self.conf_lines() if l.startswith("rpcauth=")][0]
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
