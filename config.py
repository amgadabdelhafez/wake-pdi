import getpass
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import dotenv_values


DEFAULT_CONFIG_FILE = "data/config.json"
DEFAULT_KEY_FILE = "data/dec_key.bin"


class ConfigurationError(RuntimeError):
    """Raised when the encrypted account configuration is unavailable or invalid."""


def _key_file() -> Path:
    return Path(os.environ.get("WAKE_PDI_KEY_FILE", DEFAULT_KEY_FILE))


def get_key() -> bytes:
    key_file = _key_file()
    if not key_file.is_file():
        raise ConfigurationError(f"missing decryption key file: {key_file}")
    key = dotenv_values(key_file).get("key")
    if not key:
        raise ConfigurationError(f"decryption key is absent or invalid: {key_file}")
    return key.encode("utf-8")


def generate_key() -> bytes:
    key = Fernet.generate_key()
    key_file = _key_file()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    with open(key_file, "w", encoding="utf-8") as key_handle:
        key_handle.write(f"key={key.decode('utf-8')}\n")
    os.chmod(key_file, 0o600)
    return key


def _read_config(config_file: Path) -> dict:
    if not config_file.is_file():
        raise ConfigurationError(
            f"missing encrypted account configuration: {config_file}; "
            "create it locally with --add-account or mount the credential Secret"
        )
    try:
        with open(config_file, "r", encoding="utf-8") as config_handle:
            config = json.load(config_handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError(f"unable to read account configuration: {config_file}") from error
    if not isinstance(config, dict) or not config:
        raise ConfigurationError(f"account configuration contains no accounts: {config_file}")
    return config


def _write_config(config_file: Path, config: dict) -> None:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(config_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as config_handle:
        json.dump(config, config_handle, indent=4)
        config_handle.write("\n")
    os.chmod(config_file, 0o600)


def add_account(number_of_accounts: int) -> dict:
    sn_dev_username = input("Enter username (SN Dev Portal Email):")
    sn_dev_password = getpass.getpass("Enter password (SN Dev Portal Password):")

    nickname = input(f"Enter account nickname (default: PDI_{number_of_accounts + 1}):")
    if nickname == "":
        nickname = f"PDI_{number_of_accounts + 1}"

    preferred_version = input("Enter preferred version (default: 1 (latest version)):")
    if preferred_version == "":
        preferred_version = "1"

    encrypted_password = Fernet(get_key()).encrypt(sn_dev_password.encode("utf-8"))
    return {
        nickname: {
            "sn_dev_username": sn_dev_username,
            "sn_dev_password": str(encrypted_password),
            "instance_name": "",
            "instance_password": "",
            "preferred_version": preferred_version,
            "instance_release": "",
            "instance_version": "",
            "last_checked": "",
        }
    }


def remove_account(config_file: Path, nickname: str) -> dict:
    """Remove one explicitly named account from a local account configuration."""
    config = _read_config(config_file)
    if nickname not in config:
        raise ConfigurationError(f"unknown account nickname: {nickname}")
    if len(config) == 1:
        raise ConfigurationError("refusing to remove the last configured account")

    del config[nickname]
    _write_config(config_file, config)
    return config


def get_config(args: dict) -> dict:
    config_file = Path(args.get("config_file") or DEFAULT_CONFIG_FILE)
    if args.get("remove_account"):
        return remove_account(config_file, args["remove_account"])
    if not args.get("add_account"):
        return _read_config(config_file)

    if config_file.is_file():
        config = _read_config(config_file)
    else:
        if not _key_file().is_file():
            generate_key()
        config = {}

    new_account = add_account(number_of_accounts=len(config))
    config.update(new_account)
    _write_config(config_file, config)
    return config


def update_env_instance(env: str, instance_info: dict) -> None:
    env_path = Path("config") / env
    env_path.parent.mkdir(parents=True, exist_ok=True)
    with open(env_path, "a", encoding="utf-8") as dot_env_file:
        dot_env_file.write(f"instance_name={instance_info['instance_name']}\n")
        dot_env_file.write(f"instance_release={instance_info['instance_release']}\n")
