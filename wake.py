from utils import get_args
from config import get_config
from auth import do_sign_in
import instance 
import os
import logging

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Only add handlers if they haven't been added yet
if not logger.handlers:
    # File handler
    file_handler = logging.FileHandler('logs/wake.log')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Set up root logger for third-party modules
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        root_logger.setLevel(logging.INFO)

def main():
    logger.info("Starting wake.py")
    args = get_args()
    logger.info(f"Arguments: {args}")
    if not args:
        logger.info("No arguments provided, exiting")
        exit(0)
    logger.info("Getting config")
    config = get_config(args)
    logger.info(f"Config: {config}")

    for account in config:
        logger.info(f"Processing config: {account}")
        login_info = config[account]
        logger.info("Attempting to sign in")        
        session = do_sign_in(login_info)
        
        if session:
            logger.info("Sign in successful")
        if session.magic_link:
            try:
                logger.info("checking user info")
                user_info = instance.get_user_info(session)
                for key, value in user_info.items():
                    logger.info(f"Key: {key}, Value: {value}")

                logger.info("checking instance details")
                instance_details = instance.get_instance_details(session.magic_link)
                for key, value in instance_details.items():
                    logger.info(f"Key: {key}, Value: {value}")

                logger.info("checking instance info")
                instance_info = instance.get_instance_info(session)
                # Check for any useful information in the response
                if isinstance(instance_info, dict):
                    for key, value in instance_info.items():
                        logger.info(f"Key: {key}, Value: {value}")
            except Exception as e:
                logger.error(f"Error: {e}")
                continue
    logger.info("Wake.py execution completed")

if __name__ == '__main__':
    main()
