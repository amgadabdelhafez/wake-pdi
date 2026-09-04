import os
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from totp import generate_totp, TotpError

# RFC 6238 Appendix B vector, SHA1, seed = ASCII "12345678901234567890"
SEED_B32 = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"

class TotpVectorTests(unittest.TestCase):
    def test_rfc6238_sha1_8digit_vectors(self):
        self.assertEqual(generate_totp(SEED_B32, digits=8, at=59), "94287082")
        self.assertEqual(generate_totp(SEED_B32, digits=8, at=1111111109), "07081804")
        self.assertEqual(generate_totp(SEED_B32, digits=8, at=1234567890), "89005924")

    def test_6digit_is_last6_of_8(self):
        self.assertEqual(generate_totp(SEED_B32, digits=6, at=59), "287082")

    def test_spaces_and_dashes_tolerated(self):
        self.assertEqual(generate_totp("GEZD GNBV-GY3T QOJQ GEZD GNBV GY3T QOJQ", digits=8, at=59), "94287082")

    def test_invalid_secret_raises(self):
        with self.assertRaises(TotpError):
            generate_totp("not!base32!", at=59)

    def test_sanitized_filename_lookup(self):
        import os, tempfile
        import auth
        with tempfile.TemporaryDirectory() as d:
            # secret key uses sanitized name (no @), lookup is by email
            open(os.path.join(d, "user_example.com"), "w").write(SEED_B32)
            os.environ["WAKE_PDI_TOTP_SECRET_DIR"] = d
            try:
                code = auth._totp_code_from_sealed_seed("user@example.com")
            finally:
                os.environ.pop("WAKE_PDI_TOTP_SECRET_DIR", None)
            self.assertRegex(code, r"^\d{6}$")

if __name__ == "__main__":
    unittest.main()


class SealedSeedPathTests(unittest.TestCase):
    def test_auth_uses_sealed_seed_when_dir_present(self):
        import os, tempfile, importlib
        import auth
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "user@example.com"), "w").write(SEED_B32)
            os.environ["WAKE_PDI_TOTP_SECRET_DIR"] = d
            try:
                code = auth._totp_code_from_sealed_seed("user@example.com")
            finally:
                os.environ.pop("WAKE_PDI_TOTP_SECRET_DIR", None)
            self.assertRegex(code, r"^\d{6}$")

    def test_no_dir_returns_none_falls_back_to_helper(self):
        import auth
        os.environ.pop("WAKE_PDI_TOTP_SECRET_DIR", None)
        self.assertIsNone(auth._totp_code_from_sealed_seed("user@example.com"))
