import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

import mfa_vault
import utils
import wake
from config import ConfigurationError


class MfaVaultPassphraseTests(unittest.TestCase):
    def test_import_encrypts_a_private_source_and_loads_it_without_plaintext_output(self):
        key = Fernet.generate_key()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.write_bytes(b"shared-passphrase")
            os.chmod(source, 0o600)
            destination = root / "encrypted-passphrase"

            with (
                patch.object(mfa_vault, "get_key", return_value=key),
                patch.dict(
                    os.environ,
                    {"WAKE_PDI_MFA_VAULT_PASSPHRASE_FILE": str(destination)},
                    clear=False,
                ),
            ):
                imported = mfa_vault.import_mfa_vault_passphrase(source)
                loaded = mfa_vault.load_mfa_vault_passphrase()

            self.assertEqual(imported, destination)
            self.assertEqual(loaded, b"shared-passphrase")
            self.assertNotEqual(destination.read_bytes(), b"shared-passphrase")
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)

    def test_import_refuses_an_insecure_or_multiline_source(self):
        key = Fernet.generate_key()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.write_bytes(b"passphrase\n")
            destination = root / "encrypted-passphrase"

            with (
                patch.object(mfa_vault, "get_key", return_value=key),
                patch.dict(
                    os.environ,
                    {"WAKE_PDI_MFA_VAULT_PASSPHRASE_FILE": str(destination)},
                    clear=False,
                ),
            ):
                with self.assertRaises(mfa_vault.MfaVaultPassphraseError):
                    mfa_vault.import_mfa_vault_passphrase(source)

            os.chmod(source, 0o600)
            with (
                patch.object(mfa_vault, "get_key", return_value=key),
                patch.dict(
                    os.environ,
                    {"WAKE_PDI_MFA_VAULT_PASSPHRASE_FILE": str(destination)},
                    clear=False,
                ),
            ):
                with self.assertRaises(mfa_vault.MfaVaultPassphraseError):
                    mfa_vault.import_mfa_vault_passphrase(source)

    def test_import_fails_closed_when_the_wakepdi_encryption_key_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.write_bytes(b"shared-passphrase")
            os.chmod(source, 0o600)

            with patch.object(
                mfa_vault,
                "get_key",
                side_effect=ConfigurationError("unavailable"),
            ):
                with self.assertRaises(mfa_vault.MfaVaultPassphraseError):
                    mfa_vault.import_mfa_vault_passphrase(source)

    def test_temporary_passphrase_file_is_owner_only_and_removed(self):
        with mfa_vault.temporary_mfa_vault_passphrase_file(b"shared-passphrase") as path:
            self.assertTrue(path.is_file())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

        self.assertFalse(path.exists())

    def test_cli_accepts_the_local_passphrase_import_without_loading_account_config(self):
        with patch("sys.argv", ["wake.py", "--import-mfa-vault-passphrase", "/trusted/source"]):
            args = utils.get_args()

        self.assertEqual(args["import_mfa_vault_passphrase"], "/trusted/source")

        with (
            patch.object(wake, "get_args", return_value=args),
            patch.object(mfa_vault, "import_mfa_vault_passphrase") as import_passphrase,
        ):
            self.assertEqual(wake.main(), 0)

        import_passphrase.assert_called_once_with("/trusted/source")
