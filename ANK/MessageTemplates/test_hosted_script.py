import importlib.util
import os
import stat
import tempfile
from pathlib import Path
from unittest import TestCase


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "reconcile_hosted_whatsapp.py"
SPEC = importlib.util.spec_from_file_location("reconcile_hosted_whatsapp", SCRIPT_PATH)
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)


class HostedScriptTests(TestCase):
    def test_rejects_non_https_url(self):
        with self.assertRaises(SCRIPT.ScriptError):
            SCRIPT.validate_base_url("http://api.anewknot.com")

    def test_secure_report_is_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            SCRIPT.secure_json(path, {"ok": True})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_apply_requires_exact_confirmation(self):
        old = dict(os.environ)
        try:
            os.environ["META_ACCESS_TOKEN"] = "token"
            os.environ["ANK_ADMIN_EMAIL"] = "admin@example.com"
            os.environ["ANK_ADMIN_PASSWORD"] = "password"
            with self.assertRaises(SCRIPT.ScriptError) as context:
                SCRIPT.main(["--apply", "--confirm", "wrong"])
            self.assertEqual(context.exception.exit_code, 5)
        finally:
            os.environ.clear()
            os.environ.update(old)
