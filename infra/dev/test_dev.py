import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import dev


class DevGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bago-dev-guards-")
        self.root = Path(self.temporary.name)
        self.code = self.root / "context-public/repository/frontend/src/synthetic.tsx"
        self.code.parent.mkdir(parents=True)
        self.code.write_text("SYNTHETIC_ORIGINAL")
        manifest = {"source": "synthetic-checkout", "head": "synthetic-head", "files": [{"path": "frontend/src/synthetic.tsx", "sha256": hashlib.sha256(self.code.read_bytes()).hexdigest()}]}
        file = self.root / "context-public/SOURCE_MANIFEST.json"
        file.write_text(json.dumps(manifest))
        (self.root / "context-public/EXPORT_IDENTITY.json").write_text(json.dumps({"candidate_id": "fixture", "source_manifest_sha256": hashlib.sha256(file.read_bytes()).hexdigest()}))
        self.scope = patch.object(dev, "ROOT", self.root)
        self.scope.start()
        self.env = {"BAGO_DEV_CANDIDATE": "fixture", "COMPOSE_PROJECT_NAME": "foreign-project"}

    def tearDown(self):
        self.scope.stop()
        self.temporary.cleanup()

    def test_modified_source_blocks_up_but_stop_and_ps_keep_owned_target(self):
        self.code.write_text("SYNTHETIC_CHANGED")
        with patch.object(dev.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as docker:
            self.assertEqual(2, dev.run_action("up", self.env))
            docker.assert_not_called()
            for action in ("stop", "ps"):
                self.assertEqual(0, dev.run_action(action, self.env))
                args, kwargs = docker.call_args
                self.assertEqual("bago-dev-fixture", args[0][args[0].index("--project-name")+1])
                self.assertNotIn("foreign-project", args[0])
                self.assertNotIn("COMPOSE_PROJECT_NAME", kwargs["env"])
        _, summary = dev.preflight(self.env, allow_stale=True)
        self.assertEqual("STALE", summary["fingerprint_state"])

    def test_foreign_source_pair_blocks_before_docker(self):
        with patch.object(dev.subprocess, "run") as docker:
            self.assertEqual(2, dev.run_action("up", dict(self.env, BAGO_DEV_SOURCE=str(self.root / "another-frontend"))))
            docker.assert_not_called()

    def test_unmanifested_file_blocks_up_but_stop_reports_stale(self):
        (self.code.parent / "new.tsx").write_text("SYNTHETIC_NEW_UNREVIEWED")
        with patch.object(dev.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as docker:
            self.assertEqual(2, dev.run_action("up", self.env))
            docker.assert_not_called()
            self.assertEqual(0, dev.run_action("stop", self.env))
            self.assertIn("bago-dev-fixture", docker.call_args.args[0])
        _, summary = dev.preflight(self.env, allow_stale=True)
        self.assertEqual("STALE", summary["fingerprint_state"])

    def test_foreign_candidate_cannot_relabel_export(self):
        with self.assertRaises(ValueError):
            dev.preflight(dict(self.env, BAGO_DEV_CANDIDATE="another-candidate"))

    def test_ports_compare_as_integers(self):
        with self.assertRaises(ValueError):
            dev.preflight(dict(self.env, BAGO_DEV_FRONTEND_PORT="05173", BAGO_DEV_API_PORT="5173"))

    def test_embedded_proxy_credentials_rejected(self):
        with self.assertRaises(ValueError):
            dev.preflight(dict(self.env, BAGO_API_PROXY_TARGET="http://synthetic:fixture@host.docker.internal:8080"))

    def test_candidate_and_instance_project_is_explicit(self):
        env, summary = dev.preflight(dict(self.env, BAGO_DEV_INSTANCE_SUFFIX="-install"))
        self.assertEqual("bago-dev-fixture-install", summary["project"])
        self.assertIn("bago-dev-fixture-install", dev.compose_command(summary))
        self.assertEqual("MATCH", summary["fingerprint_state"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
