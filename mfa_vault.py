"""Local-only encrypted storage for the passphrase used by ``mfa-vault-code``."""

from contextlib import contextmanager
import os
from pathlib import Path
import stat
import tempfile
from typing import Iterator

from cryptography.fernet import Fernet, InvalidToken

from config import ConfigurationError, get_key


DEFAULT_MFA_VAULT_PASSPHRASE_FILE = "data/mfa_vault_passphrase.enc"


class MfaVaultPassphraseError(RuntimeError):
    """Raised when the local MFA-vault passphrase cannot be handled safely."""


def _passphrase_store_path() -> Path:
    return Path(
        os.environ.get(
            "WAKE_PDI_MFA_VAULT_PASSPHRASE_FILE",
            DEFAULT_MFA_VAULT_PASSPHRASE_FILE,
        )
    )


def _validate_passphrase(passphrase: bytes) -> None:
    if not passphrase or b"\x00" in passphrase or b"\n" in passphrase or b"\r" in passphrase:
        raise MfaVaultPassphraseError("MFA vault passphrase source is invalid")


def _normalize_imported_passphrase(passphrase: bytes) -> bytes:
    """Allow one conventional text-file line ending without trimming password data."""
    if passphrase.endswith(b"\r\n"):
        return passphrase[:-2]
    if passphrase.endswith(b"\n"):
        return passphrase[:-1]
    return passphrase


def _write_private_bytes(destination: Path, contents: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, destination)
        os.chmod(destination, 0o600)
    except OSError as error:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise MfaVaultPassphraseError("Could not persist the encrypted MFA vault passphrase") from error


def import_mfa_vault_passphrase(source_file: str | Path) -> Path:
    """Encrypt one local passphrase source into the local-only WakePDI store."""
    source = Path(source_file)
    try:
        source_stat = source.lstat()
        if not stat.S_ISREG(source_stat.st_mode) or stat.S_ISLNK(source_stat.st_mode):
            raise MfaVaultPassphraseError("MFA vault passphrase source must be a regular file")
        if stat.S_IMODE(source_stat.st_mode) & 0o077:
            raise MfaVaultPassphraseError("MFA vault passphrase source must be owner-readable only")
        passphrase = _normalize_imported_passphrase(source.read_bytes())
    except OSError as error:
        raise MfaVaultPassphraseError("Could not read the MFA vault passphrase source") from error

    _validate_passphrase(passphrase)
    destination = _passphrase_store_path()
    try:
        encrypted = Fernet(get_key()).encrypt(passphrase)
    except ConfigurationError as error:
        raise MfaVaultPassphraseError("WakePDI encryption key is unavailable") from error
    _write_private_bytes(destination, encrypted)
    return destination


def load_mfa_vault_passphrase() -> bytes:
    """Decrypt the local-only MFA-vault passphrase without logging its value."""
    source = _passphrase_store_path()
    try:
        encrypted = source.read_bytes()
        passphrase = Fernet(get_key()).decrypt(encrypted)
    except (ConfigurationError, OSError, InvalidToken, ValueError) as error:
        raise MfaVaultPassphraseError("Encrypted MFA vault passphrase is unavailable") from error

    _validate_passphrase(passphrase)
    return passphrase


@contextmanager
def temporary_mfa_vault_passphrase_file(passphrase: bytes) -> Iterator[Path]:
    """Expose one passphrase via an owner-only file for the local helper process."""
    _validate_passphrase(passphrase)
    descriptor, temporary_path = tempfile.mkstemp(prefix="wake-pdi-mfa-vault-passphrase.")
    path = Path(temporary_path)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(passphrase)
            output.flush()
            os.fsync(output.fileno())
        yield path
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
