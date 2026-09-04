from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from cryptography.fernet import Fernet
from config import get_key
from browser_utils import setup_browser_driver
from auth_utils import wait_for_magic_link, create_session_from_cookies
from logger import setup_logger
from mfa_vault import (
    MfaVaultPassphraseError,
    load_mfa_vault_passphrase,
    temporary_mfa_vault_passphrase_file,
)
import getpass
import os
import re
import shutil
import subprocess
import time
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlparse

logger = setup_logger(__name__)
PORTAL_LOGIN_TRANSITION_SECONDS = 10
DEFAULT_LOGIN_COMPLETION_TIMEOUT_SECONDS = 60
INTERACTIVE_LOGIN_COMPLETION_TIMEOUT_SECONDS = 600
POST_AUTH_PORTAL_CONTINUATION_TIMEOUT_SECONDS = 60
MFA_CODE_COMPLETION_TIMEOUT_SECONDS = 120
DEVELOPER_PORTAL_URL = "https://developer.servicenow.com/navpage.do"
POST_AUTH_SSO_HOSTS = {"signon.service-now.com", "signon.servicenow.com"}
MFA_CODE_HOSTS = POST_AUTH_SSO_HOSTS | {"accounts.google.com"}
MFA_CODE_LOCATORS = (
    (By.NAME, "totpPin"),
    (By.ID, "totpPin"),
    (By.NAME, "idvPin"),
    (By.ID, "idvPin"),
    (By.CSS_SELECTOR, 'input[autocomplete="one-time-code"]'),
)
AUTHENTICATOR_APP_LOCATORS = (
    # This tenant renders identical generic "Select" controls for each method.
    # Bind the control to the card with the exact Authenticator App label.
    (
        By.XPATH,
        "//*[normalize-space()='Authenticator App']"
        "/ancestor::*[count(.//button[normalize-space()='Select']) = 1][1]"
        "//button[normalize-space()='Select']",
    ),
    # Compatibility with tenants that expose the method as a stable card id.
    (
        By.CSS_SELECTOR,
        "#google_otp button, #google_otp [role='button'], "
        "#google_otp input[type='button'], #google_otp input[type='submit'], "
        "#google_otp a",
    ),
    (
        By.XPATH,
        "//*[self::button or @role='button'][contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'authenticator') "
        "or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
        "'abcdefghijklmnopqrstuvwxyz'), 'authenticator')]",
    ),
)
MFA_CODE_PATTERN = re.compile(r"^[0-9]{4,12}$")
MFA_TOTP_ACCOUNT_PATTERN = re.compile(r"^[^/\s@]+@[^/\s@]+$")
MFA_TOTP_COMMAND = "mfa-vault-code"
# In-cluster path: a mounted dir of per-account ServiceNow TOTP seeds (base32),
# one file per configured email. Present only in unattended K3s; absent locally.
MFA_TOTP_SECRET_DIR_ENV = "WAKE_PDI_TOTP_SECRET_DIR"
MFA_TOTP_COMMAND_TIMEOUT_SECONDS = 10


def _safe_browser_location(driver: Any) -> str:
    """Return only an origin host and path for diagnostics, never a query value."""
    try:
        location = urlparse(driver.current_url)
        host = location.hostname or "unknown-host"
        route = location.path or "/"
        return f"{host}{route}"
    except Exception:
        return "unavailable"


def _safe_browser_form_state(driver: Any) -> str:
    """Describe only known control identifiers, never values or page text."""
    controls = (
        "username",
        "email",
        "identify-submit",
        "username_submit_button",
        "password",
        "challenge-authenticator-submit",
        "password_submit_button",
    )
    try:
        visible = []
        for control in controls:
            elements = driver.find_elements(By.ID, control)
            if any(element.is_displayed() for element in elements):
                visible.append(control)
        iframe_present = bool(driver.find_elements(By.TAG_NAME, "iframe"))
        return "controls=%s;iframe=%s" % (",".join(visible) or "none", iframe_present)
    except Exception:
        return "unavailable"


_DIAGNOSTIC_PAGE_SHAPE_ENV = "WAKE_PDI_DEBUG_PAGE_SHAPE"
_DIAGNOSTIC_EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_DIAGNOSTIC_PAGE_SHAPE_SCRIPT = """
const seen = [];
const short = (s) => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 48);
for (const el of document.querySelectorAll(
    "button, a, input, select, [role='button'], h1, h2, h3")) {
  const r = el.getBoundingClientRect();
  if (!(r.width > 0 && r.height > 0)) continue;
  const tag = el.tagName;
  const label = (tag === 'INPUT' || tag === 'SELECT')
    ? '' : short(el.innerText || el.textContent);
  seen.push([tag, el.type || '', el.id || '', el.name || '',
             short(el.getAttribute('aria-label')), label].join('|'));
  if (seen.length >= 40) break;
}
const frames = [...document.querySelectorAll('iframe')]
  .map((f) => { try { return new URL(f.src, location.href).hostname; }
                catch (e) { return 'inline'; } });
return JSON.stringify({title: short(document.title), nodes: seen, frames: frames});
"""


def _log_diagnostic_page_shape(driver: Any, stage: str) -> None:
    """Log the visible control *shape* of an identity page when explicitly enabled.

    Emits tag/type/id/name/aria-label and short label text for visible controls,
    never ``input.value``, never cookies, and never full page text. Any address
    that reaches the dump is redacted. Enabled only by
    ``WAKE_PDI_DEBUG_PAGE_SHAPE=1`` for operator-run diagnostic Jobs; unattended
    scheduler runs leave it unset and log nothing extra.
    """
    if os.environ.get(_DIAGNOSTIC_PAGE_SHAPE_ENV) != "1":
        return
    try:
        if urlparse(driver.current_url).hostname not in MFA_CODE_HOSTS:
            logger.info("PAGE-SHAPE[%s]: not on a known identity host", stage)
            return
        raw = driver.execute_script(_DIAGNOSTIC_PAGE_SHAPE_SCRIPT)
        logger.info(
            "PAGE-SHAPE[%s] at %s: %s",
            stage,
            _safe_browser_location(driver),
            _DIAGNOSTIC_EMAIL_PATTERN.sub("<redacted>", str(raw)),
        )
    except Exception as error:
        logger.info("PAGE-SHAPE[%s] unavailable (%s)", stage, type(error).__name__)


def _at_developer_portal(driver: Any) -> bool:
    """Return whether the browser reached the expected Portal host."""
    try:
        return urlparse(driver.current_url).hostname == "developer.servicenow.com"
    except Exception:
        return False


def _at_post_auth_sso_landing(driver: Any) -> bool:
    """Recognize the completed SSO landing that sometimes loses RelayState.

    The continuation is intentionally narrower than a generic SSO URL: it is
    available only after the known ``/sso`` landing has no visible credential
    controls or iframe challenge. That preserves the fail-closed behavior for
    every still-interactive or unknown sign-in state.
    """
    try:
        location = urlparse(driver.current_url)
    except Exception:
        return False
    if location.hostname not in POST_AUTH_SSO_HOSTS or location.path != "/sso":
        return False
    return _safe_browser_form_state(driver) == "controls=none;iframe=False"


def _login_return_state(driver: Any) -> str | bool:
    """Report the only two accepted states during the browser sign-in handoff."""
    if _at_developer_portal(driver):
        return "developer_portal"
    if _at_post_auth_sso_landing(driver):
        return "post_auth_sso"
    return False


def _mfa_code_field(driver: Any) -> Any | None:
    """Return only a visible one-time-code field on an expected identity host."""
    try:
        if urlparse(driver.current_url).hostname not in MFA_CODE_HOSTS:
            return None
        for by, value in MFA_CODE_LOCATORS:
            for field in driver.find_elements(by, value):
                if field.is_displayed() and field.is_enabled():
                    return field
    except Exception:
        return None
    return None


def _login_or_mfa_state(driver: Any) -> str | bool:
    """Return Portal completion or the one supported local MFA-code challenge."""
    return _login_return_state(driver) or ("mfa_code" if _mfa_code_field(driver) else False)


def _authenticator_app_option(driver: Any) -> Any | None:
    """Return a visible Authenticator-app choice on an expected identity host only."""
    try:
        if urlparse(driver.current_url).hostname not in MFA_CODE_HOSTS:
            return None
        for by, value in AUTHENTICATOR_APP_LOCATORS:
            for option in driver.find_elements(by, value):
                if option.is_displayed() and option.is_enabled():
                    return option
    except Exception:
        return None
    return None


def _login_or_mfa_or_authenticator_app_state(driver: Any) -> str | bool:
    """Recognize the guarded Authenticator-app chooser before a code challenge."""
    return (
        _login_return_state(driver)
        or ("mfa_code" if _mfa_code_field(driver) else False)
        or ("authenticator_app" if _authenticator_app_option(driver) else False)
    )


def _select_authenticator_app(driver: Any) -> bool:
    """Choose the recognized Authenticator-app route without reading page content."""
    option = _authenticator_app_option(driver)
    if option is None:
        logger.error("Authenticator-app choice was no longer available on an expected identity host")
        return False
    try:
        option.click()
        logger.info("Selected Authenticator App verification method")
        return True
    except Exception as error:
        logger.error(
            "Authenticator-app selection failed (%s at %s)",
            type(error).__name__,
            _safe_browser_location(driver),
        )
        return False


def prompt_for_mfa_code() -> str | None:
    """Read a one-time code from the local terminal without echoing or logging it."""
    try:
        code = getpass.getpass("Enter the visible ServiceNow/Google MFA code: ").strip()
    except (EOFError, KeyboardInterrupt, OSError):
        logger.error("MFA code was not provided at the local terminal")
        return None
    if not MFA_CODE_PATTERN.fullmatch(code):
        logger.error("MFA code was rejected locally; expected 4 to 12 digits")
        return None
    return code


def _totp_code_from_sealed_seed(username: str) -> str | None:
    """Compute a TOTP code from a provisioned per-account seed, if one is mounted.

    Returns None when no seed dir/file exists, so the local mfa-vault-code path is
    used unchanged. Only ServiceNow account seeds are ever placed in the seed dir.
    """
    directory = os.environ.get(MFA_TOTP_SECRET_DIR_ENV)
    if not directory:
        return None
    # Kubernetes Secret keys cannot contain '@' or '/', so a mounted seed file is
    # named by a sanitized form of the account. Try sanitized, then the raw email.
    import re as _re
    safe = _re.sub(r"[^A-Za-z0-9._-]", "_", username)
    seed_path = None
    for candidate in (os.path.join(directory, safe), os.path.join(directory, username)):
        if os.path.isfile(candidate):
            seed_path = candidate
            break
    if seed_path is None:
        logger.error("No provisioned TOTP seed for the configured account")
        return None
    try:
        from totp import generate_totp, TotpError
        secret = open(seed_path, "r", encoding="utf-8").read().strip()
        code = generate_totp(secret)
    except (OSError, TotpError, Exception) as error:
        logger.error("Provisioned TOTP generation failed (%s)", type(error).__name__)
        return None
    if not MFA_CODE_PATTERN.fullmatch(code):
        logger.error("Provisioned TOTP produced an invalid code")
        return None
    return code


def local_totp_code_for_account(username: str) -> str | None:
    """Return one local vault-generated code for a configured email account.

    The helper is invoked only after a recognized visible MFA field appears.
    Its stdout is held only long enough to validate and submit one numeric code;
    neither the code nor the derived vault path is logged.
    """
    if not isinstance(username, str) or not MFA_TOTP_ACCOUNT_PATTERN.fullmatch(username):
        logger.error("Configured account cannot select a local MFA TOTP entry")
        return None

    seeded = _totp_code_from_sealed_seed(username)
    if seeded is not None:
        return seeded

    executable = shutil.which(MFA_TOTP_COMMAND)
    if executable is None:
        logger.error("Local MFA TOTP helper is unavailable")
        return None

    try:
        passphrase = load_mfa_vault_passphrase()
        with temporary_mfa_vault_passphrase_file(passphrase) as passphrase_file:
            environment = os.environ.copy()
            environment["MFA_VAULT_PASSPHRASE_FILE"] = str(passphrase_file)
            result = subprocess.run(
                [executable, f"servicenow/{username}"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=MFA_TOTP_COMMAND_TIMEOUT_SECONDS,
                env=environment,
            )
    except (MfaVaultPassphraseError, OSError, subprocess.SubprocessError) as error:
        logger.error("Local MFA TOTP code retrieval failed (%s)", type(error).__name__)
        return None

    code = result.stdout.strip()
    if not MFA_CODE_PATTERN.fullmatch(code):
        logger.error("Local MFA TOTP helper returned an invalid code")
        return None
    return code


def _enter_mfa_code(driver: Any, code: str) -> bool:
    """Enter one validated code into the detected challenge field and submit it."""
    if not MFA_CODE_PATTERN.fullmatch(code):
        logger.error("MFA code was rejected locally; expected 4 to 12 digits")
        return False
    field = _mfa_code_field(driver)
    if field is None:
        logger.error("MFA code challenge was no longer available on an expected identity host")
        return False
    try:
        field.click()
        field.clear()
        field.send_keys(code)
        field.send_keys(Keys.RETURN)
        return True
    except Exception as error:
        logger.error("MFA code submission failed (%s at %s)", type(error).__name__, _safe_browser_location(driver))
        return False

def handle_login_error(driver) -> str:
    """Detect a Portal login error without placing page content in logs."""
    try:
        # legacy container
        error_placeholder = driver.find_element(By.ID, "errorPlaceholder")
        if error_placeholder.is_displayed():
            return "The Portal reported a sign-in error"
    except Exception:
        pass
    try:
        # 2026 flow renders inline error/alert nodes
        for el in driver.find_elements(By.CSS_SELECTOR, "[role='alert'], [class*='error']"):
            if el.is_displayed():
                return "The Portal reported a sign-in error"
    except Exception:
        pass
    return "Unknown login error"

def _first_visible(driver: Any, wait: int, locators) -> Any:
    """Return the first locator that becomes visible; raise if none do."""
    last_error = None
    for by, value in locators:
        try:
            return WebDriverWait(driver, wait).until(
                EC.visibility_of_element_located((by, value))
            )
        except Exception as e:
            last_error = e
    raise last_error


def _click_resiliently(driver: Any, element: Any) -> None:
    """Click a control that an async widget may momentarily overlay.

    The sign-in page loads a chat widget after the form, so a native click can
    race with it (ElementClickInterceptedException). Scroll the control into
    view and retry; fall back to a scripted click on the SAME element. The
    button was enabled by real key events, so this only replaces the final tap.
    """
    from selenium.common.exceptions import ElementClickInterceptedException

    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    except Exception:
        pass
    try:
        element.click()
        return
    except ElementClickInterceptedException:
        logger.info("Submit click was intercepted; retrying on the same control")
    try:
        element.click()
        return
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", element)


def enter_credentials(driver: Any, username: str, password: str) -> bool:
    """Enter login credentials and submit.

    2026 flow (signon.servicenow.com/x_snc_sso_auth.do?pageId=login), two steps:
      step 1: #username then #identify-submit ("Next")
      step 2: #password then #challenge-authenticator-submit ("Sign in")
    The submit buttons stay disabled until real input events fire; Selenium
    send_keys produces real events, so no JS injection is needed.
    Old pre-2025 ids are kept as fallbacks.
    """
    try:
        # Step 1: identifier
        username_field = _first_visible(driver, 30, [
            (By.ID, "username"),          # 2026 flow
            (By.ID, "email"),             # legacy flow
        ])
        username_field.click()
        username_field.clear()
        username_field.send_keys(username)
        next_button = _first_visible(driver, 15, [
            (By.ID, "identify-submit"),          # 2026 flow
            (By.ID, "username_submit_button"),   # legacy flow
        ])
        WebDriverWait(driver, 15).until(lambda d: next_button.is_enabled())
        _click_resiliently(driver, next_button)
    except Exception as error:
        logger.error(
            "Portal identifier stage failed (%s at %s)",
            type(error).__name__,
            "%s; %s" % (_safe_browser_location(driver), _safe_browser_form_state(driver)),
        )
        return False

    try:
        # Step 2: password
        password_field = _first_visible(driver, 30, [
            (By.ID, "password"),
        ])
        password_field.click()
        password_field.send_keys(password)
        signin_button = _first_visible(driver, 15, [
            (By.ID, "challenge-authenticator-submit"),  # 2026 flow
            (By.ID, "password_submit_button"),          # legacy flow
        ])
        WebDriverWait(driver, 15).until(lambda d: signin_button.is_enabled())
        _click_resiliently(driver, signin_button)
        _log_diagnostic_page_shape(driver, "after-password-submit")
        return True
    except Exception as error:
        logger.error(
            "Portal password stage failed (%s at %s)",
            type(error).__name__,
            "%s; %s" % (_safe_browser_location(driver), _safe_browser_form_state(driver)),
        )
        return False

def _login_completion_timeout_seconds() -> int:
    """Choose a bounded login window without extending unattended runs."""
    configured = os.environ.get("WAKE_PDI_LOGIN_COMPLETION_TIMEOUT_SECONDS")
    if configured:
        try:
            timeout_seconds = int(configured)
        except ValueError:
            timeout_seconds = 0
        if timeout_seconds > 0:
            return timeout_seconds
        logger.warning("Ignoring invalid interactive login timeout configuration")

    if os.environ.get("CHROME_HEADLESS", "").lower() == "false":
        return INTERACTIVE_LOGIN_COMPLETION_TIMEOUT_SECONDS
    return DEFAULT_LOGIN_COMPLETION_TIMEOUT_SECONDS


def wait_for_login_completion(
    driver: Any,
    *,
    mfa_code_prompt: bool = False,
    mfa_code_provider: Callable[[], str | None] | None = None,
    select_authenticator_app: bool = False,
) -> bool:
    """Wait for Portal return and optionally enter one local MFA code on a known form."""
    if mfa_code_prompt and mfa_code_provider is not None:
        logger.error("Only one local MFA-code source may be configured")
        return False

    code_provider = prompt_for_mfa_code if mfa_code_prompt else mfa_code_provider
    if select_authenticator_app and code_provider is None:
        logger.error("Authenticator-app selection requires one local MFA-code source")
        return False
    timeout_seconds = _login_completion_timeout_seconds()
    try:
        state_condition = (
            _login_or_mfa_or_authenticator_app_state
            if select_authenticator_app
            else _login_or_mfa_state if code_provider is not None else _login_return_state
        )
        state = WebDriverWait(driver, timeout_seconds).until(state_condition)
        if state == "developer_portal":
            logger.info("signin success")
            return True

        if state == "post_auth_sso":
            logger.info(
                "ServiceNow SSO completed without Portal RelayState return; requesting Portal continuation"
            )
            driver.get(DEVELOPER_PORTAL_URL)
            WebDriverWait(driver, POST_AUTH_PORTAL_CONTINUATION_TIMEOUT_SECONDS).until(
                _at_developer_portal
            )
            logger.info("signin success after Portal continuation")
            return True

        if state == "authenticator_app" and select_authenticator_app:
            if not _select_authenticator_app(driver):
                return False
            state = WebDriverWait(driver, MFA_CODE_COMPLETION_TIMEOUT_SECONDS).until(
                _login_or_mfa_state
            )

        if state == "mfa_code" and code_provider is not None:
            code = code_provider()
            if code is None or not _enter_mfa_code(driver, code):
                return False
            state = WebDriverWait(driver, MFA_CODE_COMPLETION_TIMEOUT_SECONDS).until(
                _login_return_state
            )
            if state == "developer_portal":
                logger.info("signin success after local MFA code")
                return True
            if state == "post_auth_sso":
                logger.info(
                    "Local MFA completed without Portal RelayState return; requesting Portal continuation"
                )
                driver.get(DEVELOPER_PORTAL_URL)
                WebDriverWait(driver, POST_AUTH_PORTAL_CONTINUATION_TIMEOUT_SECONDS).until(
                    _at_developer_portal
                )
                logger.info("signin success after local MFA code and Portal continuation")
                return True
            logger.error("MFA code submission returned an unrecognized completion state")
            return False

        logger.error("Portal sign-in returned an unrecognized completion state")
        return False
    except Exception as error:
        logger.error(
            "Portal sign-in did not return to Developer Portal (%s at %s)",
            type(error).__name__,
            "%s; %s" % (_safe_browser_location(driver), _safe_browser_form_state(driver)),
        )
        _log_diagnostic_page_shape(driver, "login-completion-timeout")
        return False

def do_sign_in(
    config: Dict[str, str], *, mfa_code_prompt: bool = False, mfa_totp: bool = False
) -> Optional[Any]:
    """
    Handle ServiceNow Developer Portal sign-in process
    
    Args:
        config: Dictionary containing login configuration
        
    Returns:
        Optional[Session]: Authenticated session if successful, None otherwise
    """
    if mfa_code_prompt and mfa_totp:
        logger.error("Only one local MFA-code source may be configured")
        return None

    # Decrypt credentials
    sn_dev_username = config["sn_dev_username"]
    encpwdbyt = bytes(config['sn_dev_password'].replace("b'", "").replace("'", ""), 'utf-8')
    refKeybyt = get_key()
    sn_dev_password = (Fernet(refKeybyt).decrypt(encpwdbyt)).decode("utf-8")

    logger.info("Starting Developer Portal sign-in")

    driver = None
    try:
        # Initialize the selected local browser driver.
        driver = setup_browser_driver()
        # Navigate to login page
        signon_url = "https://signon.servicenow.com/x_snc_sso_auth.do?pageId=login&RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fnavpage.do&redirectUri=&email="
        driver.get(signon_url)
        # Firefox returns at DOM readiness while ServiceNow continues its
        # browser-side handoff to the sign-in form. The current route settles
        # into the username controls within this bounded interval.
        time.sleep(PORTAL_LOGIN_TRANSITION_SECONDS)
        logger.info("signin in progress...")

        # Handle login process
        if not enter_credentials(driver, sn_dev_username, sn_dev_password):
            return None

        mfa_code_provider = (
            (lambda: local_totp_code_for_account(sn_dev_username)) if mfa_totp else None
        )
        if not wait_for_login_completion(
            driver,
            mfa_code_prompt=mfa_code_prompt,
            mfa_code_provider=mfa_code_provider,
            select_authenticator_app=mfa_totp,
        ):
            logger.error(handle_login_error(driver))
            return None

        # Wait for requests to complete
        time.sleep(2)

        # Capture magic link
        magic_link = wait_for_magic_link(driver)
        if magic_link:
            logger.info("Successfully captured magic link")
        else:
            logger.warning("Could not capture magic link after multiple attempts")

        # Get cookies and create session. Also capture the dev-portal user token
        # (window.g_ck), which is a JS variable rather than a cookie and is required
        # for devportal.do provisioning calls (they 401 without X-UserToken).
        cookies = driver.get_cookies()
        g_ck = None
        try:
            g_ck = driver.execute_script(
                "return window.g_ck "
                "|| (window.NOW && window.NOW.g_ck) "
                "|| (typeof g_ck !== 'undefined' ? g_ck : '') "
                "|| '';"
            )
        except Exception as error:
            logger.warning("Developer Portal session token was unavailable (%s)", type(error).__name__)
        logger.info("Developer Portal session token captured: %s", "yes" if g_ck else "no")
        return create_session_from_cookies(cookies, magic_link, g_ck)

    except Exception as error:
        logger.error("Unexpected browser sign-in failure (%s)", type(error).__name__)
        return None

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception as error:
                logger.warning("Unable to close the Portal browser (%s)", type(error).__name__)
