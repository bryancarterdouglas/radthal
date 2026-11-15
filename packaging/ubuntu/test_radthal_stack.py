#!/usr/bin/env python3
"""Teste le moteur du paquet (radthal-stack) avec de FAUX docker / ss / ip : on regarde ce qu'il demande a Docker, sans Docker.
Et le docker-compose.yml genere pour le paquet (services, ports, volumes, variables)."""
import os, stat, subprocess, sys, tempfile, textwrap, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
STACK = os.path.join(HERE, "src", "radthal-stack")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

FAKE_DOCKER = r'''#!/bin/bash
# faux docker : note ce qu'on lui demande dans $FAKE_LOG ; son comportement vient de variables FAKE_*
echo "docker $*" >> "$FAKE_LOG"
args=" $* "
case "$1" in
  info) exit 0 ;;
  pull) case "$2" in *"${FAKE_PULL_FAIL:-@@aucun@@}"*) exit 1 ;; *) exit 0 ;; esac ;;
  image) case "$3" in *"${FAKE_HAVE_IMAGE:-@@aucun@@}"*) exit 0 ;; *) exit 1 ;; esac ;;
  port) [ "${FAKE_OUR_PORT:-0}" = 1 ] && { echo "0.0.0.0:3333"; exit 0; } || exit 1 ;;
  compose)
    case "$args" in *" -f - "*) cat > /dev/null ;; esac     # le fichier compose arrive sur l'entree standard
    case "$args" in
      *" version "*) exit 0 ;;
      *" ps "*) [ "${FAKE_OUR_PORT:-0}" = 1 ] && echo "abc123"; exit 0 ;;
      *" up "*)
        echo "ENV STRATUM_BIND=<${STRATUM_BIND-UNSET}> STRATUM_HOST_PORT=<${STRATUM_HOST_PORT-UNSET}> STRATUM_HOST=<${STRATUM_HOST-UNSET}> MINING_NOTE=<${MINING_NOTE-UNSET}> CKPOOL_IMAGE=<${CKPOOL_IMAGE-UNSET}>" >> "$FAKE_LOG"
        [ "${FAKE_UP_FAIL:-0}" = 1 ] && exit 1
        exit 0 ;;
      *) exit 0 ;;
    esac ;;
esac
exit 0
'''
FAKE_SS = '#!/bin/bash\n[ "${FAKE_PORT_BUSY:-0}" = 1 ] && echo "LISTEN 0 4096 0.0.0.0:3333 0.0.0.0:*"\nexit 0\n'
FAKE_IP = '#!/bin/bash\necho "1.1.1.1 via 192.0.2.1 dev eth0 src 192.0.2.7 uid 1000"\n'


def put(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def get(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_exec(path, text):
    put(path, text)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)


class StackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bin = os.path.join(self.tmp, "bin"); os.makedirs(self.bin)
        self.share = os.path.join(self.tmp, "share"); os.makedirs(self.share)
        self.etc = os.path.join(self.tmp, "etc"); os.makedirs(self.etc)
        self.run_dir = os.path.join(self.tmp, "run")
        self.log = os.path.join(self.tmp, "docker.log")
        put(self.log, "")
        put(os.path.join(self.share, "docker-compose.yml"), "services: {}\n")
        write_exec(os.path.join(self.bin, "docker"), FAKE_DOCKER)
        write_exec(os.path.join(self.bin, "ss"), FAKE_SS)
        write_exec(os.path.join(self.bin, "ip"), FAKE_IP)

    def up(self, env_file="", **fake):
        put(os.path.join(self.etc, "radthal.env"), env_file)
        env = dict(os.environ, PATH=self.bin + ":" + os.environ["PATH"], RADTHAL_SHARE=self.share, RADTHAL_ETC=self.etc,
                   RADTHAL_RUN=self.run_dir, RADTHAL_DOCKER_WAIT="1", FAKE_LOG=self.log)
        for k in ("STRATUM_BIND", "STRATUM_HOST", "STRATUM_HOST_PORT", "MINING_NOTE"):
            env.pop(k, None)
        env.update({"FAKE_" + k: str(v) for k, v in fake.items()})
        r = subprocess.run(["bash", STACK, "up"], env=env, capture_output=True, text=True, timeout=60)
        status = get(os.path.join(self.run_dir, "status")).split("\n")[0]
        lines = get(self.log).splitlines()
        return r, status, lines

    @staticmethod
    def up_lines(lines):
        return [l for l in lines if l.startswith("docker compose") and " up " in l]

    @staticmethod
    def env_line(lines):
        return [l for l in lines if l.startswith("ENV ")][-1]

    def test_mining_on_by_default(self):
        r, status, lines = self.up()
        self.assertEqual(status, "running", r.stderr)
        ups = self.up_lines(lines)
        self.assertEqual(len(ups), 1)
        self.assertTrue(ups[0].endswith("up -d --remove-orphans"), ups[0])      # tous les services, ckpool compris
        env = self.env_line(lines)
        self.assertIn("STRATUM_BIND=<UNSET>", env)                               # le fichier compose prend alors 0.0.0.0
        self.assertIn("STRATUM_HOST_PORT=<UNSET>", env)                          # ... et 3333
        self.assertIn("STRATUM_HOST=<192.0.2.7>", env)                           # adresse du reseau local, pour la page ckpool
        self.assertIn("MINING_NOTE=<>", env)
        self.assertIn("radthal-ckpool:latest", env)
        self.assertIn("docker pull ghcr.io/bryancarterdouglas/radthal-ckpool:latest", lines)

    def test_port_busy_disables_mining_without_stopping_the_node(self):
        r, status, lines = self.up(PORT_BUSY=1)
        self.assertEqual(status, "running", r.stderr)
        self.assertTrue(any(l.startswith("docker compose") and " stop ckpool" in l for l in lines))
        ups = self.up_lines(lines)
        self.assertEqual(len(ups), 1)
        self.assertTrue(ups[0].endswith("up -d --remove-orphans init radthal interface"), ups[0])
        env = self.env_line(lines)
        self.assertIn("STRATUM_BIND=<127.0.0.1>", env)                           # jamais ouvert au reseau dans ce cas
        self.assertIn("STRATUM_HOST_PORT=<>", env)                               # vide : Docker choisit un port libre
        self.assertIn("3333", env.split("MINING_NOTE=")[1])

    def test_port_held_by_our_own_node_is_not_a_conflict(self):
        # coupure de courant : Docker a relance nos conteneurs avant le service, le port 3333 est a nous
        r, status, lines = self.up(PORT_BUSY=1, OUR_PORT=1)
        self.assertEqual(status, "running", r.stderr)
        self.assertTrue(self.up_lines(lines)[0].endswith("up -d --remove-orphans"))
        self.assertIn("MINING_NOTE=<>", self.env_line(lines))

    def test_ckpool_image_missing_disables_mining_only(self):
        r, status, lines = self.up(PULL_FAIL="radthal-ckpool")
        self.assertEqual(status, "running", r.stderr)
        self.assertTrue(self.up_lines(lines)[0].endswith("init radthal interface"))
        self.assertIn("image de ckpool", self.env_line(lines))

    def test_ckpool_image_already_there_is_used_when_offline(self):
        r, status, lines = self.up(PULL_FAIL="radthal-ckpool", HAVE_IMAGE="radthal-ckpool")
        self.assertEqual(status, "running", r.stderr)
        self.assertTrue(self.up_lines(lines)[0].endswith("up -d --remove-orphans"))

    def test_one_tag_per_image(self):
        r, status, lines = self.up(env_file="RADTHAL_TAG=0.1.5\nUI_TAG=essai\n")
        self.assertEqual(status, "running", r.stderr)
        self.assertIn("docker pull ghcr.io/bryancarterdouglas/radthal:0.1.5", lines)
        self.assertIn("docker pull ghcr.io/bryancarterdouglas/radthal-interface:essai", lines)
        self.assertIn("docker pull ghcr.io/bryancarterdouglas/radthal-ckpool:0.1.5", lines)

    def test_settings_file_wins(self):
        r, status, lines = self.up(env_file="STRATUM_HOST=198.51.100.9\nSTRATUM_BIND=127.0.0.1\n")
        self.assertEqual(status, "running", r.stderr)
        env = self.env_line(lines)
        self.assertIn("STRATUM_HOST=<198.51.100.9>", env)
        self.assertIn("STRATUM_BIND=<127.0.0.1>", env)

    def test_docker_failure_is_reported(self):
        r, status, lines = self.up(UP_FAIL=1)
        self.assertEqual(status, "error")


class ComposeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import yaml
        out = os.path.join(tempfile.mkdtemp(), "compose.yml")
        subprocess.run([sys.executable, os.path.join(HERE, "make-compose.py"), os.path.join(REPO, "docker-compose.yml"), out], check=True)
        cls.text = get(out)
        cls.c = yaml.safe_load(cls.text)

    def test_services(self):
        self.assertEqual(list(self.c["services"]), ["init", "radthal", "ckpool", "interface"])

    def test_ckpool_shares_the_node_network_and_cannot_write_the_secret(self):
        ck = self.c["services"]["ckpool"]
        self.assertEqual(ck["network_mode"], "service:radthal")
        self.assertIn("radthal-secrets:/secrets:ro", ck["volumes"])
        self.assertNotIn("ports", ck)                                            # le port est publie par le noeud
        self.assertEqual(ck["user"], "1000:1000")

    def test_node_waits_for_init_and_publishes_stratum_with_a_lan_default(self):
        node = self.c["services"]["radthal"]
        self.assertEqual(node["depends_on"], {"init": {"condition": "service_completed_successfully"}})
        self.assertIn("${STRATUM_BIND:-0.0.0.0}:${STRATUM_HOST_PORT-3333}:3333", node["ports"])
        self.assertIn("9333:9333", node["ports"])

    def test_rpc_is_never_published(self):
        for p in self.c["services"]["radthal"]["ports"]:
            self.assertNotIn("8332", p)
            self.assertNotIn("8333", p)

    def test_only_init_and_ckpool_see_the_secret(self):
        for name, svc in self.c["services"].items():
            has = any("radthal-secrets" in v for v in svc.get("volumes", []))
            self.assertEqual(has, name in ("init", "ckpool"), name)
        self.assertEqual(self.c["services"]["ckpool"]["volumes"][0], "radthal-secrets:/secrets:ro")

    def test_interface_gets_the_ckpool_page_and_logs_read_only(self):
        ui = self.c["services"]["interface"]
        self.assertIn("ckpool", ui["environment"]["VIEWS"])
        self.assertIn("radthal-ckpool-logs:/ckpool/logs:ro", ui["volumes"])
        self.assertEqual(ui["environment"]["STRATUM_PORT"], "3333")
        self.assertIn("STRATUM_HOST", ui["environment"])
        self.assertIn("MINING_NOTE", ui["environment"])

    def test_volumes(self):
        self.assertEqual(set(self.c["volumes"]), {"radthal-data", "radthal-ui", "radthal-secrets", "radthal-ckpool-logs"})

    def test_data_volume_keeps_its_name_so_existing_nodes_are_kept(self):
        self.assertIn("radthal-data:/data", self.c["services"]["radthal"]["volumes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
