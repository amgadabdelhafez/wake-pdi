import logging
from utils import get_args
from config import get_config
from auth import do_sign_in
import instance 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
        logger.info("Using Selenium-based authentication")
        session = do_sign_in(login_info)
        
        if session :
            logger.info("Sign in successful, checking login status and getting instance ID")
            user_info = instance.get_user_info(session)
            logger.info(f"User info: {user_info}")
            instance_details = instance.get_instance_details(session.magic_link)
            logger.info(f"Instance details: {instance_details['instance_id']}")
            # is_logged_in, cookies = instance.get_instance_id(session)
            instance_info = instance.get_instance_info(session)
            logger.info(f"Instance info: {instance_info}")
            # Check for any useful information in the response
            if isinstance(instance_info, dict):
                for key, value in instance_info.items():
                    logger.debug(f"Key: {key}, Value: {value}")
                if 'sys_id' in key:
                        logger.info(f"Found instance sys_id: {value}")
       
    logger.info("Wake.py execution completed")

if __name__ == '__main__':
    main()
