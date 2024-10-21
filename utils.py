import sys

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
