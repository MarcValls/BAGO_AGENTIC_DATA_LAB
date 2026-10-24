import unittest
from prepare_context import allowed


class ExportPolicy(unittest.TestCase):
    def test_known_public_entries(self):
        for path in ("src/providers/runtime.py", "frontend/src/main.tsx", "frontend/public/brand.svg",
                     "frontend/package-lock.json", "requirements-test.txt", "requirements-whatsapp.txt", "SECURITY.md", ".bago/team/kit/protocol/TEAM_PROTOCOL.md", "docs/governed-execution/GEX_V1_SCHEMA.json", "docs/public-web/MANUAL.md", "frontend/src/features/decision-inspector/evidence/EvidenceExplorer.tsx", "frontend/src/ui-kit-preview.tsx", "frontend/packages/bago-adl-ui-kit/tokens.css"):
            with self.subTest(path=path):
                self.assertTrue(allowed(path))

    def test_known_private_or_generated_entries(self):
        for path in (".bago/providers/registry.json", ".bago/traces/private.json", ".worktrees/task/src/file.py",
                     "frontend/.env", "frontend/.env.local", "frontend/.build/index.html", "frontend/node_modules/x.js",
                     "src/private/session.json", "frontend/profiles/browser.json", "tests/evidence/data.json", "docs/public-web/evidence/private.json", "docs/public-web/other.md",
                     "src/contacts_service/history/UPSTREAM_SOURCE.py", "src/contacts_service/history/other.py", "src/contacts_service/history/private.json", "src/other/history/UPSTREAM_SOURCE.py", "src/credentials.json", "src/db.sqlite3", "docs/coordination/archive/trace.json", "frontend/src/private/client_secret.json"):
            with self.subTest(path=path):
                self.assertFalse(allowed(path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
