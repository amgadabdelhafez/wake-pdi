import unittest
from unittest.mock import Mock, patch

import firefox_utils


class FirefoxRuntimeTests(unittest.TestCase):
    def test_uses_eager_page_readiness_and_a_bounded_navigation_timeout(self):
        options = Mock()
        driver = Mock()

        with (
            patch.object(
                firefox_utils,
                "_executable_from_env",
                side_effect=("/usr/bin/firefox-esr", "/usr/local/bin/geckodriver"),
            ),
            patch.object(firefox_utils.webdriver, "FirefoxOptions", return_value=options),
            patch.object(firefox_utils, "Service"),
            patch.object(firefox_utils.webdriver, "Firefox", return_value=driver),
        ):
            result = firefox_utils.setup_firefox_driver()

        self.assertIs(result, driver)
        self.assertEqual(options.binary_location, "/usr/bin/firefox-esr")
        self.assertEqual(options.page_load_strategy, "eager")
        options.add_argument.assert_called_once_with("-headless")
        driver.set_page_load_timeout.assert_called_once_with(
            firefox_utils.PAGE_LOAD_TIMEOUT_SECONDS
        )


if __name__ == "__main__":
    unittest.main()
