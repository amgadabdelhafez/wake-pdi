import logging
import os
import sys
from pathlib import Path

from logger import setup_logger
from scheduler import ScheduleState, is_active_assigned_pdi, status_summary, utc_now
from session_store import SessionStoreError
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


def _durable_session_only() -> bool:
    return os.environ.get("WAKE_PDI_DURABLE_SESSION_ONLY", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _capture_durable_sessions(config, args, do_sign_in, get_instance_info) -> int:
    from session_store import (
        SessionStoreError,
        encrypt_session_store,
        session_record_from_requests_session,
        write_session_store,
    )

    account_records = {}
    failed_accounts = 0
    for account_number, (account, login_info) in enumerate(config.items(), start=1):
        logger.info("Capturing durable Portal session for configured account %d", account_number)
        sign_in_options = {}
        if args.get("mfa_code_prompt"):
            sign_in_options["mfa_code_prompt"] = True
        if args.get("mfa_totp"):
            sign_in_options["mfa_totp"] = True
        session = do_sign_in(login_info, **sign_in_options)
        if session is None:
            logger.error("Account %d could not authenticate; session store was not updated", account_number)
            failed_accounts += 1
            continue
        try:
            instance_info = get_instance_info(session)
            if not isinstance(instance_info, dict):
                logger.error(
                    "Account %d did not return Portal status; session store was not updated",
                    account_number,
                )
                failed_accounts += 1
                continue
            account_records[account] = session_record_from_requests_session(
                session, max_age_hours=args["session_max_age_hours"]
            )
        except SessionStoreError as error:
            logger.error("Account %d session capture failed: %s", account_number, error)
            failed_accounts += 1
        finally:
            _close_session(session)

    if failed_accounts:
        logger.error("At least one account did not produce a Portal-validated durable session")
        return 1
    try:
        if args.get("capture_sessions_stdout"):
            # stdout is reserved for a direct trusted pipe to the Kubernetes API.
            # Operational logs use stderr, so no plaintext or log lines enter it.
            sys.stdout.buffer.write(encrypt_session_store(account_records))
            sys.stdout.buffer.flush()
        else:
            write_session_store(Path(args["session_file"]), account_records)
    except SessionStoreError as error:
        logger.error("Durable Portal session store was not persisted: %s", error)
        return 1
    logger.info("Captured durable Portal sessions for %d configured accounts", len(account_records))
    return 0


def _session_for_account(
    account_number: int,
    account: str,
    login_info,
    *,
    durable_session_only: bool,
    session_file: Path,
    do_sign_in,
    load_account_session=None,
):
    """Return an authenticated account session without weakening durable-only mode."""
    if durable_session_only:
        try:
            return load_account_session(session_file, account)
        except SessionStoreError as error:
            logger.error(
                "Account %d requires manual MFA renewal; durable Portal session is unavailable (%s)",
                account_number,
                error,
            )
            return None
    return do_sign_in(login_info)


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
    return True


def _extend_account(
    account_number: int, session, state, account: str, instance_info, cat_item_id, extend_instance
) -> bool:
    now = utc_now()
    if state:
        state.record_extend_attempt(account, now)
    result = extend_instance(session, instance_info, cat_item_id)
    if result is None:
        logger.error("Account %d extend request was not accepted by the Portal", account_number)
        return False
    if state:
        state.record_extend_accepted(account, now)
    logger.info(
        "Account %d extend request was accepted; the next daily run will verify status",
        account_number,
    )
    return True


def main() -> int:
    args = get_args()
    if args["not_headless"]:
        os.environ["CHROME_HEADLESS"] = "false"

    if args["import_mfa_vault_passphrase"]:
        try:
            from mfa_vault import MfaVaultPassphraseError, import_mfa_vault_passphrase

            import_mfa_vault_passphrase(args["import_mfa_vault_passphrase"])
        except (ImportError, MfaVaultPassphraseError) as error:
            logger.error("Local MFA vault passphrase import failed: %s", error)
            return 2
        logger.info("Local MFA vault passphrase imported into encrypted storage")
        return 0

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
        from instance import get_instance_info, wake_instance, extend_instance
    except ImportError as error:
        logger.error("Authentication dependencies are unavailable: %s", error)
        return 2

    if args["capture_sessions"]:
        return _capture_durable_sessions(config, args, do_sign_in, get_instance_info)

    durable_session_only = _durable_session_only()
    session_file = Path(os.environ.get("WAKE_PDI_SESSION_FILE", "data/portal_sessions.enc"))
    if durable_session_only:
        try:
            from session_store import load_account_session
        except ImportError as error:
            logger.error("Durable-session dependencies are unavailable: %s", error)
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
        session = _session_for_account(
            account_number,
            account,
            login_info,
            durable_session_only=durable_session_only,
            session_file=session_file,
            do_sign_in=do_sign_in,
            load_account_session=load_account_session if durable_session_only else None,
        )
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

            if args["reconcile"] and args["allow_extend"]:
                due, reason = schedule_state.extend_due(
                    account,
                    now,
                    args["extend_interval_hours"],
                    instance_info.get("remainingInactivityDays"),
                    args["extend_inactivity_threshold_days"],
                )
                if due:
                    logger.info("Account %d is due for an extend: %s", account_number, reason)
                    if not _extend_account(
                        account_number,
                        session,
                        schedule_state,
                        account,
                        instance_info,
                        args["extend_cat_item_id"],
                        extend_instance,
                    ):
                        failed_accounts += 1
                else:
                    logger.info("Account %d extend deferred: %s", account_number, reason)
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
