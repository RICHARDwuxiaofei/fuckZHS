import builtins
from datetime import datetime, timezone
from email.utils import format_datetime
import unittest
from unittest.mock import patch

import share_policy
from share_policy import HONG_KONG, access_allowed, ShareExpiredError
import windows_entry


class FakeResponse:
    def __init__(self, date, status=200):
        self.status_code = status
        self.headers = {"Date": date}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class ExpiryTests(unittest.TestCase):
    def setUp(self):
        share_policy._anchor = None
        share_policy._failed_at = None

    def tearDown(self):
        share_policy._anchor = None
        share_policy._failed_at = None

    def test_hong_kong_boundary(self):
        self.assertTrue(access_allowed(datetime(2026, 11, 20, 23, 59, 59, tzinfo=HONG_KONG)))
        self.assertFalse(access_allowed(datetime(2026, 11, 21, tzinfo=HONG_KONG)))
        self.assertFalse(access_allowed(datetime(2026, 11, 20, 16, tzinfo=timezone.utc)))
        with self.assertRaises(ValueError):
            access_allowed(datetime(2026, 11, 20))

    def test_server_time_and_monotonic_clock(self):
        stamp = format_datetime(datetime(2026, 11, 20, 15, 59, 58, tzinfo=timezone.utc), usegmt=True)
        with patch('share_policy.requests.get', return_value=FakeResponse(stamp)) as fetch, \
             patch('share_policy.time.monotonic', side_effect=[100, 100, 101, 103]):
            self.assertTrue(access_allowed())
            self.assertTrue(access_allowed())
            self.assertFalse(access_allowed())
        fetch.assert_called_once()

    def test_network_error_denies_access_without_os_clock_fallback(self):
        with patch('share_policy.requests.get', side_effect=share_policy.requests.ConnectionError()) as fetch, \
             patch('share_policy.time.monotonic', return_value=42.0):
            self.assertFalse(access_allowed())
            with self.assertRaises(ShareExpiredError):
                share_policy.require_access()
        self.assertEqual(fetch.call_count, len(share_policy.TIME_ENDPOINTS))

    def test_refresh_fails_closed(self):
        stamp = format_datetime(datetime(2026, 11, 20, 13, 0, tzinfo=timezone.utc), usegmt=True)
        failures = [share_policy.requests.ConnectionError()] * len(share_policy.TIME_ENDPOINTS)
        with patch('share_policy.requests.get', side_effect=[FakeResponse(stamp)] + failures), \
             patch('share_policy.time.monotonic', side_effect=[0, 0, 31, 31]):
            self.assertTrue(access_allowed())
            self.assertFalse(access_allowed())

    def test_bad_date_and_error_status_denied(self):
        with patch('share_policy.requests.get', return_value=FakeResponse('invalid')):
            self.assertFalse(access_allowed())
        share_policy._failed_at = None
        with patch('share_policy.requests.get', return_value=FakeResponse('Fri, 20 Nov 2026 15:59:59 GMT', status=503)):
            self.assertFalse(access_allowed())

    def test_expired_entry_never_imports_gui_or_backend(self):
        original = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name.startswith(('PySide6', 'share_gui', 'share_worker', 'fucker', 'utils')):
                self.fail('Expired entry imported a UI or account dependency')
            return original(name, *args, **kwargs)

        with patch.object(windows_entry, 'access_allowed', return_value=False), \
             patch('builtins.__import__', side_effect=guarded):
            for args in ([], ['--worker'], ['--gui-smoke-test']):
                self.assertEqual(windows_entry.main(args), 0)

    def test_expired_worker_has_no_side_effects(self):
        import share_worker
        with patch.object(share_worker, 'require_access', side_effect=ShareExpiredError), \
             patch.object(share_worker, 'run') as run:
            self.assertEqual(share_worker.main([]), 0)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
