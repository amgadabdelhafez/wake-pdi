import sys
import json

def get_args():
    args = {}
    if len(sys.argv) == 1:
        print("""
Control your SN Dev PDIs using this CLI tool.
You can wake your instances up, reset, upgrade, or release your instances, request a new instance with specific version.
--wake-up             wakes up all instances in config file
--request-instance    requests an instance with a specific version [TODO]
--reset-instance      resets an instance to its out-of-the-box settings
--release-instance    releases an instance back to pool
--upgrade-instance    upgrades an instance back to pool [TODO]
--add-account         add a new account credentials to config file
--config-file         use a specific config file instead of default config.json
--not-headless        show browser window (for debugging)
--use_requests        use requests-based authentication instead of Selenium
        """)
        return False

    if '--not-headless' in sys.argv:
        args['not-headless'] = True

    if '--add-account' in sys.argv:
        args['add-account'] = True

    if '--use_requests' in sys.argv:
        args['use_requests'] = True

    if '--config-file' in sys.argv:
        args['config_file'] = True
        if sys.argv[sys.argv.index("--config-file") + 1] != '':
            args['config_file_name'] = sys.argv[sys.argv.index("--config-file") + 1]
    else:
        args['config_file'] = False

    if '--release-instance' in sys.argv:
        args['release_instance'] = True
        if sys.argv[sys.argv.index("--release-instance") + 1] != '':
            args['release_instance_name'] = sys.argv[sys.argv.index("--release-instance") + 1]
    else:
        args['release_instance'] = False

    if '--reset-instance' in sys.argv:
        args['reset_instance'] = True
        if sys.argv[sys.argv.index("--reset-instance") + 1] != '':
            args['reset_instance_name'] = sys.argv[sys.argv.index("--reset-instance") + 1]
    else:
        args['reset_instance'] = False

    return args

def print_result(data):

    # Parse JSON data
    instance_info = json.loads(data)

    # Extract and print useful information
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
    print(f"Temporary Password: {instance_info.get('tempPassword')}")
    print(f"System ID: {instance_info.get('sys_id')}")
