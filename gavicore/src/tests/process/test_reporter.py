import json
import time
import unittest
from unittest.mock import MagicMock, patch
from urllib import error

from s2gos_common.process.reporter import CallbackReporter


class CallbackReporterTest(unittest.TestCase):
    def setUp(self):
        self.url = "http://localhost/callback"

    def test_report_and_stop_success(self):
        with patch(
            "urllib.request.urlopen",
            return_value=MagicMock(__enter__=lambda s: s, __exit__=lambda s, *a: None),
        ) as mock_urlopen:
            reporter = CallbackReporter()
            reporter.report(self.url, {"status": "ok"})
            reporter.stop()
            self.assertTrue(mock_urlopen.called)

    def test_report_with_url_error(self):
        with patch(
            "urllib.request.urlopen", side_effect=error.URLError("fail")
        ) as mock_urlopen:
            reporter = CallbackReporter()
            reporter.report(self.url, {"status": "fail"})
            reporter.stop()
            self.assertEqual(mock_urlopen.call_count, 1)

    def test_report_with_http_error(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=error.HTTPError(self.url, 500, "error", hdrs=None, fp=None),
        ) as mock_urlopen:
            reporter = CallbackReporter()
            reporter.report(self.url, {"status": "server error"})
            reporter.stop()
            self.assertEqual(mock_urlopen.call_count, 1)

    def test_report_with_other_error(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=TypeError(self.url),
        ) as mock_urlopen:
            reporter = CallbackReporter()
            reporter.report(self.url, {"status": "server error"})
            reporter.stop()
            self.assertEqual(mock_urlopen.call_count, 1)

    def test_idle_thread_does_not_post(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            reporter = CallbackReporter()
            time.sleep(1)
            reporter.stop()
            self.assertFalse(mock_urlopen.called)

    def test_multiple_reports_coalesce(self):
        with patch(
            "urllib.request.urlopen",
            return_value=MagicMock(__enter__=lambda s: s, __exit__=lambda s, *a: None),
        ) as mock_urlopen:
            reporter = CallbackReporter()
            reporter.report(self.url, {"status": "pending"})
            reporter.report(self.url, {"status": "running"})
            reporter.report(self.url, {"status": "completed"})
            reporter.stop()
            args, _ = mock_urlopen.call_args
            body = json.loads(args[0].data.decode("utf-8"))
            self.assertEqual(body["status"], "completed")
