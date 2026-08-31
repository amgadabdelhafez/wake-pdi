import logging
import os
import sys

from logger import setup_logger
from scheduler import ScheduleState, is_active_assigned_pdi, status_summary, utc_now
from utils import get_args


logger = setup_logger(__name__)

for third_party_logger in (
    "seleniumwire",
    "seleniumwire.thirdparty.mitmproxy",
    "seleniumwire.handler",
    "hpack.hpack",
    "hpack.table",
    "h2",
    "selenium",
    "urllib3",
    "WDM",
):
    logging.getLogger(third_party_logger).setLevel(logging.ERROR)


def _close_session(session) -> None:
    try:
        session.close()
    except Exception:
        logger.warning("Unable to close a Portal session cleanly")


def _wake_account(
    account_number: int, session, state: ScheduleState | None, account: str, wake_instance
) -> bool:
    now = utc_now()
    if state:
        state.record_wake_attempt(account, now)
    wake_result = wake_instance(session)
    if wake_result is None:
        logger.error("Account %d wake request was not accepted by the Portal", account_number)
        return False
    if state:
        state.record_wake_accepted(account, now)
    logger.info(
        "Account %d wake request was accepted; the next daily run will verify status",
        account_number,
    )
    return True


def main() -> int:
    args = get_args()
    if args["not_headless"]:
        os.environ["CHROME_HEADLESS"] = "false"

    try:
        from config import ConfigurationError, get_config
    except ImportError as error:
        logger.error("Configuration dependencies are unavailable: %s", error)
        return 2

    try:
        config = get_config(args)
    except ConfigurationError as error:
        logger.error("Configuration error: %s", error)
        return 2

    if args["add_account"] or args["remove_account"]:
        logger.info("Account configuration updated locally")
        return 0

    try:
        if args["auth_mode"] == "requests":
            from auth_requests import do_sign_in_requests as do_sign_in
        else:
            from auth import do_sign_in
        from instance import get_instance_info, wake_instance
    except ImportError as error:
        logger.error("Authentication dependencies are unavailable: %s", error)
        return 2

    schedule_state = None
    if args["reconcile"]:
        try:
            schedule_state = ScheduleState.load(args["state_file"])
        except RuntimeError as error:
            logger.error("Scheduler state error: %s", error)
            return 2

    failed_accounts = 0
    for account_number, (account, login_info) in enumerate(config.items(), start=1):
        logger.info("Checking configured account %d", account_number)
        session = do_sign_in(login_info)
        if session is None:
            logger.error("Account %d could not authenticate", account_number)
            failed_accounts += 1
            continue

        try:
            instance_info = get_instance_info(session)
            if not isinstance(instance_info, dict):
                logger.error("Account %d status was unavailable", account_number)
                failed_accounts += 1
                continue

            summary = status_summary(instance_info)
            logger.info(
                "Account %d status: state=%s display_state=%s",
                account_number,
                summary["state"] or "unknown",
                summary["display_state"] or "unknown",
            )
            now = utc_now()
            if schedule_state:
                schedule_state.record_status(account, summary, now)

            if not is_active_assigned_pdi(instance_info):
                logger.warning(
                    "Account %d has no active assigned PDI; wake and provisioning are skipped",
                    account_number,
                )
                continue

            if args["wake_up"]:
                if not _wake_account(account_number, session, None, account, wake_instance):
                    failed_accounts += 1
                continue

            if args["reconcile"] and args["allow_wake"]:
                due, reason = schedule_state.wake_due(
                    account, now, args["wake_interval_hours"]
                )
                if due:
                    logger.info("Account %d is due for a wake: %s", account_number, reason)
                    if not _wake_account(
                        account_number, session, schedule_state, account, wake_instance
                    ):
                        failed_accounts += 1
                else:
                    logger.info("Account %d wake deferred: %s", account_number, reason)
        finally:
            _close_session(session)

    if schedule_state:
        try:
            schedule_state.save()
        except OSError as error:
            logger.error("Unable to persist scheduler state: %s", error)
            failed_accounts += 1

    return 1 if failed_accounts else 0


if __name__ == "__main__":
    sys.exit(main())
