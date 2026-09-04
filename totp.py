"""Self-contained RFC 6238 TOTP for unattended (in-cluster) MFA.

Stdlib only. Used ONLY when a per-account ServiceNow TOTP seed is provisioned
(e.g. a mounted Kubernetes Secret); the local path keeps using mfa-vault-code.
This never handles any seed but the ones explicitly provisioned for ServiceNow.
"""
import base64, hashlib, hmac, struct, time

class TotpError(RuntimeError):
    pass

def _b32decode(secret: str) -> bytes:
    s = "".join(secret.split()).replace("-", "").upper()
    s += "=" * ((8 - len(s) % 8) % 8)
    try:
        raw = base64.b32decode(s, casefold=True)
    except Exception as e:
        raise TotpError("invalid base32 TOTP secret") from e
    if not raw:
        raise TotpError("empty TOTP secret")
    return raw

def generate_totp(secret: str, *, digits: int = 6, period: int = 30,
                  digest=hashlib.sha1, at: float | None = None) -> str:
    key = _b32decode(secret)
    counter = int((time.time() if at is None else at) // period)
    msg = struct.pack(">Q", counter)
    mac = hmac.new(key, msg, digest).digest()
    offset = mac[-1] & 0x0F
    binary = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10 ** digits)).zfill(digits)
