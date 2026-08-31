# WakePDI

WakePDI checks configured ServiceNow Developer Portal PDIs and can send the
Portal's explicit direct-wake request for an already assigned PDI. It does not
provision, reset, release, or otherwise create an instance.

## Safety model

- The image does nothing but print CLI help by default.
- `--status` authenticates and reports status without requesting a wake.
- `--wake-up` is an explicit manual action for active assigned PDIs only.
- `--reconcile --allow-wake` is the scheduler-only path: it reads status first,
  persists an opaque local schedule record, and wakes only when the configured
  interval has elapsed.
- Missing, expired, and `No Instance Assigned` accounts are reported and
  skipped. The application never calls the Portal's instance-provisioning API.
- Credentials stay in the encrypted configuration and decryption-key files;
  neither configuration, cookies, HTTP headers, passwords, nor session tokens
  are written to application logs.

The default wake interval is 96 hours. The intended Kubernetes workload runs
once per day, uses the persisted state to decide whether a wake is due, and
rechecks every result on the following daily run.

The Portal's current interactive sign-in requires a browser session. The
scheduler image uses Firefox plus a pinned GeckoDriver under the restricted
pod profile. It does not package Chromium and does not use an unsafe
`--no-sandbox` fallback. The lightweight HTTP sign-in remains diagnostic-only:
it detects and rejects guest sessions rather than treating a token as proof of
an authenticated Portal session.

Firefox treats DOM readiness, not third-party analytics completion, as the
page-load boundary and applies a 45-second navigation timeout. The scheduler
then waits explicitly for the Portal's own sign-in controls. This keeps a
blocked tracking resource from holding a daily reconciliation indefinitely.

## Commands

Use a local encrypted account configuration only from a trusted directory.
The default paths are `data/config.json` and `data/dec_key.bin`; the latter can
be overridden with `WAKE_PDI_KEY_FILE`.

```sh
# Read-only Portal status for every configured account.
python wake.py --status

# Visible browser flow for a human-completed Portal SSO challenge. This permits
# up to 10 minutes after credential handoff; unattended runs retain a 60-second
# completion window.
python wake.py --status --auth-mode browser --not-headless

# Deliberately wake active assigned PDIs now. This is a Portal mutation.
python wake.py --wake-up

# Scheduler path: persist non-secret timing state, then wake only if due.
python wake.py --reconcile --allow-wake \
  --state-file /var/lib/wake-pdi/schedule-state.json \
  --wake-interval-hours 96
```

`--add-account` and `--remove-account <ACCOUNT>` are local account-management
commands. They update encrypted local configuration only; they are not
intended for Kubernetes.

## Container

The container uses a non-root application user, a default seccomp profile at
deployment, no added Linux capabilities, a read-only root filesystem, and
temporary writable locations only for scheduler state, log, and runtime data.
It uses Firefox WebDriver for the interactive Portal SSO flow and does not
require an unconfined seccomp profile or an unsafe browser sandbox bypass.

Build locally:

```sh
docker build -t wake-pdi:local .
docker run --rm wake-pdi:local
```

The Kubernetes delivery contract is maintained separately in
`/Users/amgad/dev_projects/homelab-k8s-baseline/workloads/wake-pdi`. It mounts
the encrypted configuration as a read-only Secret and stores only schedule
timestamps and hashed account identifiers on an explicit NFS PVC.
