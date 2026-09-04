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
- Credentials stay in the encrypted configuration and decryption-key files.
  The optional durable Portal-session store is encrypted before it is mounted as
  a Kubernetes Secret item. Neither configuration, cookies, HTTP headers,
  passwords, nor session tokens are written to application logs.

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

## Durable Portal session route

An unattended Kubernetes Job cannot complete the emailed MFA challenge. Its
only supported route is an explicitly captured, encrypted Portal-session store.
This is a compact requests-session record containing the Portal cookies and
Developer Portal token needed by the status and direct-wake API. It is not a
browser profile and does not contain browser cache, history, or saved form
data.

Capture requires visible browser MFA for **every configured account**. Choose
one local code source when the identity provider asks for a one-time code:
`--mfa-code-prompt` reads one numeric code from the terminal without echoing it;
`--mfa-totp` invokes the local `mfa-vault-code` helper after the recognized
challenge appears. When the identity provider first presents a visible
Authenticator-app choice, TOTP mode selects that recognized control before it
requests a code. It derives `servicenow/<configured-email>` for each configured
account, accepts only a 4 to 12 digit result, and invokes the helper without a
shell. Neither mode logs or retains the code, submits it only to a recognized
visible ServiceNow or Google one-time-code field, and operates only in the
local visible-browser capture flow, never in K3s. WakePDI validates Portal
status before including an account in the new store. If any account fails, it
emits no session data and preserves any prior store.

When `mfa-vault-code` needs a local vault passphrase, import it once into the
separate local-only WakePDI Fernet store. The passphrase store is never emitted
to stdout, included in the Portal session store, copied into a Kubernetes
Secret, or used by unattended K3s jobs. At TOTP time WakePDI decrypts it only
to a short-lived owner-only file passed to the helper by path, then removes that
temporary file. Keep the plaintext import source owner-readable only and remove
it manually after confirming the encrypted import if that is appropriate for
your local recovery process. The import accepts one normal terminal newline in
the plaintext file but rejects all other newline characters.

Each stored session has a maximum 120-hour lifetime by default: the 96-hour
wake cadence plus one daily reconciliation opportunity. An earlier cookie
expiry wins. This is a local renewal bound, not a claim about ServiceNow's
actual token lifetime. Every scheduler run independently validates the Portal
session; missing, unreadable, expired, or Portal-rejected sessions fail closed,
require manual MFA renewal, and never fall back to headless browser login.

The encrypted session file belongs in the same Kubernetes Secret as
`config.json` and `dec_key.bin`, under the name `portal_sessions.enc`. Do not
print, commit, or paste its contents. Because the decrypting key is mounted in
that same workload Secret, this encryption prevents accidental plaintext
handling and log disclosure; Kubernetes Secret access, namespace policy, and
the workload's read-only mount remain the primary access boundary.

## Commands

Use a local encrypted account configuration only from a trusted directory.

Browser selection is controlled by `WAKE_PDI_BROWSER`. When it is unset, local
runs default to Chrome (`chrome_utils.py`; a matching ChromeDriver is fetched by
`webdriver-manager`). The container image pins `WAKE_PDI_BROWSER=firefox` with
`firefox-esr` and GeckoDriver, so scheduler and status Jobs in Kubernetes use
Firefox. Set `WAKE_PDI_BROWSER=firefox` locally to reproduce the image's
behaviour. The examples below use the project virtualenv interpreter; a bare
`python` may not be on `PATH`, and the `apply-session-store.sh` pipe then
refuses the empty stream rather than writing anything.
The default paths are `data/config.json` and `data/dec_key.bin`; the latter can
be overridden with `WAKE_PDI_KEY_FILE`.

```sh
# Read-only Portal status for every configured account.
./.venv/bin/python wake.py --status

# Visible browser flow for a human-completed Portal SSO challenge. This permits
# up to 10 minutes after credential handoff; unattended runs retain a 60-second
# completion window.
./.venv/bin/python wake.py --status --auth-mode browser --not-headless

# Import a local MFA-vault passphrase from an owner-only plaintext file. This
# creates data/mfa_vault_passphrase.enc locally; do not mount or apply it to K3s.
./.venv/bin/python wake.py --import-mfa-vault-passphrase /path/to/local-mfa-vault-passphrase

# Capture renewed durable sessions through visible MFA using the local TOTP
# helper and stream the encrypted result directly to the trusted Kubernetes
# Secret applier. Do not run this command without the pipe, as stdout carries
# encrypted session material.
./.venv/bin/python wake.py --capture-sessions --capture-sessions-stdout --mfa-totp --auth-mode browser --not-headless \
  | /Users/amgad/dev_projects/homelab-k8s-baseline/workloads/wake-pdi/apply-session-store.sh

# Deliberately wake active assigned PDIs now. This is a Portal mutation.
./.venv/bin/python wake.py --wake-up

# Scheduler path: persist non-secret timing state, then wake only if due.
./.venv/bin/python wake.py --reconcile --allow-wake \
  --state-file /var/lib/wake-pdi/schedule-state.json \
  --wake-interval-hours 96
```

## Extending instances (optional, disabled by default)

An instance is reclaimed after its inactivity timer expires. `--reconcile --allow-extend`
sends the Portal's Extend-instance operation, but ONLY when the timer is genuinely low
(`remainingInactivityDays <= --extend-inactivity-threshold-days`, default 2) and the
per-account interval has elapsed. A wake resets the same timer, so extend is pointless while
the timer is near full and is deliberately skipped then.

Extend requires an operator-verified catalog-item id and has NO default:

```sh
./.venv/bin/python wake.py --reconcile --allow-extend \
  --extend-cat-item-id "$WAKE_PDI_EXTEND_CAT_ITEM_ID" \
  --state-file /var/lib/wake-pdi/schedule-state.json
```

**DANGER:** `instance.ops.execute_cat_item` is the same Portal endpoint used for destructive
operations (including reset-and-wipe); the operation is selected entirely by the id. Capture
the extend id from a real Portal Extend click (DevTools -> Network -> the `execute_cat_item`
request) and supply it via `--extend-cat-item-id` or `WAKE_PDI_EXTEND_CAT_ITEM_ID`. Without
it, `--allow-extend` refuses to start.

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
the encrypted configuration and durable-session record as a read-only Secret
and stores only schedule timestamps and hashed account identifiers on an
explicit NFS PVC.
