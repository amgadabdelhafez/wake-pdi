import json
import tempfile
import unittest
from pathlib import Path

from config import ConfigurationError, remove_account


class RemoveAccountTests(unittest.TestCase):
    def _write_config(self, root: Path, accounts: dict) -> Path:
        config_path = root / "config.json"
        config_path.write_text(json.dumps(accounts), encoding="utf-8")
        return config_path

    def test_removes_only_the_explicit_account(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = self._write_config(
                Path(temporary_directory),
                {
                    "PDI_1": {"sn_dev_username": "first@example.invalid"},
                    "PDI_2": {"sn_dev_username": "second@example.invalid"},
                },
            )

            remaining = remove_account(config_path, "PDI_1")

            self.assertEqual(list(remaining), ["PDI_2"])
            self.assertEqual(
                json.loads(config_path.read_text(encoding="utf-8")), remaining
            )

    def test_rejects_unknown_or_last_account_removal(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            multiple = self._write_config(
                root, {"PDI_1": {}, "PDI_2": {}}
            )
            with self.assertRaisesRegex(ConfigurationError, "unknown account"):
                remove_account(multiple, "PDI_3")

            singleton = self._write_config(root, {"PDI_1": {}})
            with self.assertRaisesRegex(ConfigurationError, "last configured"):
                remove_account(singleton, "PDI_1")


if __name__ == "__main__":
    unittest.main()
