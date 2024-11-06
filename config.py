import os
import json
import getpass
from cryptography.fernet import Fernet
from dotenv import dotenv_values

def get_key():
    return bytes(dotenv_values('archive/dec_key.bin')['key'], 'utf-8')

def generate_key():
    key = Fernet.generate_key()
    os.makedirs('archive', exist_ok=True)
    with open('archive/dec_key.bin', "w") as key_file:
        key_file.write("key=" + key.decode("utf-8") + "\n")
    return key

def add_account(number_of_accounts):
    sn_dev_username = input("Enter username (SN Dev Portal Email):")
    sn_dev_password = getpass.getpass("Enter password (SN Dev Portal Password):")

    nickname = input(f"Enter account nickname (default: PDI_{number_of_accounts + 1}):")
    if nickname == "":
        nickname = f"PDI_{number_of_accounts + 1}"

    preferred_version = input("Enter preferred version (default: 1 (latest version)):")
    if preferred_version == "":
        preferred_version = "1"

    key = get_key()
    refKey = Fernet(key)
    mypwdbyt = bytes(sn_dev_password, 'utf-8')
    encrypted_password = refKey.encrypt(mypwdbyt)

    new_account = {
        nickname: {
            "sn_dev_username": sn_dev_username,
            "sn_dev_password": str(encrypted_password),
            "instance_name": "",
            "instance_password": "",
            "preferred_version": preferred_version,
            "instance_release": "",
            "instance_version": "",
            "last_checked": ""
        }
    }

    return new_account

def get_config(args):
    config_file_name = args['config_file_name'] if args['config_file'] else "data/config.json"
    os.makedirs('data', exist_ok=True)

    if os.path.exists(config_file_name):
        print(f"config file found: {config_file_name}")
        with open(config_file_name, "r") as config_file:
            config_file_content = config_file.read()
            if config_file_content != '':
                if "add-account" in args:
                    config = json.loads(config_file_content)
                    new_account = add_account(number_of_accounts=len(config))
                    config[list(new_account.keys())[0]] = list(new_account.values())[0]
                    with open(config_file_name, "w") as config_file:
                        json.dump(config, config_file, indent=4)
                config = json.loads(config_file_content)
                print(f"number of accounts found: {len(config.keys())}")
            else:
                print("no accounts found, updating config file..")
                config = first_run(config_file_name)
    else:
        print("no config found, generating config file..")
        config = first_run(config_file_name)
    return config

def first_run(config_file_name):
    generate_key()
    new_account = add_account(number_of_accounts=0)
    with open(config_file_name, "w") as config_file:
        json.dump(new_account, config_file, indent=4)
    return new_account

def update_env_instance(env, instance_info):
    env_path = f"config/{env}"
    os.makedirs('config', exist_ok=True)
    with open(env_path, "a") as dot_env_file:
        dot_env_file.write(f"instance_name={instance_info['instance_name']}\n")
        dot_env_file.write(f"instance_release={instance_info['instance_release']}\n")
