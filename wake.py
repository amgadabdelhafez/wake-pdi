from utils import get_args
from config import get_config
from auth import do_sign_in
import instance 
import logging
from logger import setup_logger

# Set up logging using centralized logger
logger = setup_logger(__name__)

# Configure third-party loggers to ERROR level
logging.getLogger('seleniumwire').setLevel(logging.ERROR)
logging.getLogger('seleniumwire.thirdparty.mitmproxy').setLevel(logging.ERROR)
logging.getLogger('seleniumwire.handler').setLevel(logging.ERROR)
logging.getLogger('hpack.hpack').setLevel(logging.ERROR)
logging.getLogger('hpack.table').setLevel(logging.ERROR)
logging.getLogger('h2').setLevel(logging.ERROR)
logging.getLogger('selenium').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('WDM').setLevel(logging.ERROR)

def main():
    logger.info("Starting wake.py")
    args = get_args()
    logger.info(f"Arguments: {args}")
    if not args:
        logger.error("No arguments provided, exiting")
        exit(0)
    logger.info("Getting config")
    config = get_config(args)
    logger.debug(f"Config: {config}")

    for account in config:
        logger.info(f"Processing config: {account}")
        login_info = config[account]
        logger.info("Attempting to sign in")        
        session = do_sign_in(login_info)
        
        if session.magic_link:            
            try:
                logger.info("checking user info")
                user_info = instance.get_user_info(session)
                for key, value in user_info.items():
                    logger.debug(f"{key}: {value}")
            except Exception as e:
                logger.error(f"Error checking user info: {e}")
            try:
                logger.info("checking instance info")
                instance_info = instance.get_instance_info(session)
                
                # If no instance found or instance is expired, request a new one
                if not instance_info or (isinstance(instance_info, dict) and instance_info.get('status') == 'expired'):
                    logger.info("No active instance found or instance expired, requesting new instance")
                    new_instance = instance.request_new_instance(session)
                    if new_instance and new_instance.get('status') == 'success':
                        logger.info(f"New instance provisioned: {new_instance.get('instance_url')}")
                        # Refresh instance info after getting new instance
                        instance_info = instance.get_instance_info(session)
                    else:
                        logger.error("Failed to provision new instance")
                
                if isinstance(instance_info, dict):
                    for key, value in instance_info.items():
                        logger.debug(f"{key}: {value}")
                continue
            except Exception as e:
                logger.error(f"Error checking instance info: {e}")
            try:
                logger.info("checking instance details")
                instance_details = instance.get_instance_details(session.magic_link)
                for key, value in instance_details.items():
                    logger.debug(f"{key}: {value}")
            except Exception as e:
                logger.error(f"Error checking instance details: {e}")            
            
    logger.info("Wake.py execution completed")

if __name__ == '__main__':
    main()
