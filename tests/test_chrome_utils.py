import os
import unittest
from unittest.mock import Mock, patch

import chrome_utils


class ChromeRuntimeTests(unittest.TestCase):
    def test_never_disables_chrome_sandbox(self):
        options = Mock()
        driver = Mock()

        with (
            patch.dict(
                os.environ,
                {
                    "CHROME_NO_SANDBOX": "1",
                    "CI": "1",
                    "CHROME_HEADLESS": "false",
                },
                clear=False,
            ),
            patch.object(chrome_utils, "is_arm", return_value=True),
            patch.object(
                chrome_utils.webdriver, "ChromeOptions", return_value=options
            ),
            patch.object(
                chrome_utils, "get_chromedriver", return_value="/tmp/chromedriver"
            ),
            patch.object(chrome_utils, "verify_chromedriver"),
            patch.object(chrome_utils, "Service"),
            patch.object(chrome_utils.webdriver, "Chrome", return_value=driver),
        ):
            self.assertIs(chrome_utils.setup_chrome_driver(), driver)

        arguments = [call.args[0] for call in options.add_argument.call_args_list]
        self.assertNotIn("--no-sandbox", arguments)


if __name__ == "__main__":
    unittest.main()
