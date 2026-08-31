import argparse
import json
import os


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def get_args():
    parser = argparse.ArgumentParser(
        description=(
            "Check ServiceNow Developer Portal PDIs and, only when explicitly "
            "requested, send a wake request for an already assigned PDI."
        )
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--status",
        action="store_true",
        help="authenticate and report each configured PDI status without mutation",
    )
    action.add_argument(
        "--wake-up",
        dest="wake_up",
        action="store_true",
        help="immediately request a wake for each active assigned PDI",
    )
    action.add_argument(
        "--reconcile",
        action="store_true",
        help="record daily status and evaluate the persisted wake cadence",
    )
    action.add_argument(
        "--add-account",
        dest="add_account",
        action="store_true",
        help="interactively add an account to a local encrypted config",
    )
    action.add_argument(
        "--remove-account",
        dest="remove_account",
        metavar="ACCOUNT",
        help="remove one explicitly named account from a local encrypted config",
    )
    parser.add_argument(
        "--allow-wake",
        action="store_true",
        help="permit --reconcile to send a due wake request",
    )
    parser.add_argument(
        "--config-file",
        dest="config_file",
        help="path to the encrypted account configuration",
    )
    parser.add_argument(
        "--state-file",
        default=os.environ.get(
            "WAKE_PDI_STATE_FILE", "/var/lib/wake-pdi/schedule-state.json"
        ),
        help="non-secret scheduler state path used by --reconcile",
    )
    parser.add_argument(
        "--wake-interval-hours",
        type=_positive_integer,
        default=_positive_integer(os.environ.get("WAKE_PDI_WAKE_INTERVAL_HOURS", "96")),
        help="minimum interval between Portal-accepted wake requests (default: 96)",
    )
    parser.add_argument(
        "--auth-mode",
        choices=("browser", "requests"),
        default=os.environ.get("WAKE_PDI_AUTH_MODE", "browser"),
        help=(
            "authentication transport; browser is required for Portal SSO, while "
            "the requests path is diagnostic-only and rejects guest sessions"
        ),
    )
    parser.add_argument(
        "--not-headless",
        dest="not_headless",
        action="store_true",
        help="show the browser for a local interactive diagnostic run",
    )

    args = vars(parser.parse_args())
    if args["allow_wake"] and not args["reconcile"]:
        parser.error("--allow-wake requires --reconcile")
    if args["reconcile"] and not args["state_file"]:
        parser.error("--reconcile requires a non-empty --state-file")
    if args["not_headless"] and args["auth_mode"] != "browser":
        parser.error("--not-headless requires --auth-mode browser")
    return args


def print_result(data):
    instance_info = json.loads(data)

    print("Instance Information:")
    print("---------------------")
    print(f"Instance Name: {instance_info.get('name')}")
    print(f"URL: {instance_info.get('url')}")
    print(f"Status: {instance_info.get('instanceStatus', {}).get('display_state')}")
    print(f"State: {instance_info.get('instanceStatus', {}).get('state')}")

    print("\nDeveloper Controls:")
    print("-------------------")
    print(f"Can Activate: {instance_info.get('canActivate')}")
    print(f"Extension Button Displayed: {instance_info.get('display_btn_extend_instance')}")
    print(f"Tooltip: {json.loads(instance_info['btn_extend_instance_tooltip']).get('enabled')}")

    print("\nRelease Information:")
    print("--------------------")
    print(f"Release: {instance_info.get('release')}")
    print(f"Full Release Version: {instance_info.get('full_release')}")
    print(f"Upgrade Version: {instance_info.get('upgradeVersion')}")

    print("\nMaintenance and Activity Status:")
    print("--------------------------------")
    print(f"Forced Maintenance: {instance_info.get('forced_maintenance')}")
    print(f"Under Unplanned Maintenance: {instance_info.get('underUnplannedMaintenance')}")
    print(f"Time Since Last Activity: {instance_info.get('timeToLastActivity')}")
    print(f"Days Since Last Extension: {instance_info.get('daysSinceExtended')}")
    print(f"Remaining Inactivity Days: {instance_info.get('remainingInactivityDays')} days")

    print("\nInstalled Applications:")
    print("------------------------")
    for app, status in instance_info.get("installedApps", {}).items():
        print(f"{app}: {status}")

    print("\nAdditional Information:")
    print("-----------------------")
    temporary_password = instance_info.get("tempPassword")
    print(f"Temporary Password: {'[redacted]' if temporary_password else 'not returned'}")
    print(f"System ID: {instance_info.get('sys_id')}")
