import builtins
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from share_policy import HONG_KONG, access_allowed, ShareExpiredError
import windows_entry


class ExpiryTests(unittest.TestCase):
    def test_hong_kong_boundary(self):
        self.assertTrue(access_allowed(datetime(2026, 11, 5, 23, 59, 59, tzinfo=HONG_KONG)))
        self.assertFalse(access_allowed(datetime(2026, 11, 6, tzinfo=HONG_KONG)))
        self.assertFalse(access_allowed(datetime(2026, 11, 5, 16, tzinfo=timezone.utc)))
        with self.assertRaises(ValueError):
            access_allowed(datetime(2026, 11, 5))

    def test_expired_entry_never_imports_gui_or_backend(self):
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.startswith(('PySide6', 'share_gui', 'share_worker', 'fucker', 'utils')):
                self.fail('Expired entry imported a UI or account dependency')
            return original(name, *args, **kwargs)
        with patch.object(windows_entry, 'access_allowed', return_value=False), patch('builtins.__import__', side_effect=guarded):
            for args in ([], ['--worker'], ['--gui-smoke-test']):
                self.assertEqual(windows_entry.main(args), 0)

    def test_expired_worker_has_no_side_effects(self):
        import share_worker
        with patch.object(share_worker, 'require_access', side_effect=ShareExpiredError), patch.object(share_worker, 'run') as run:
            self.assertEqual(share_worker.main([]), 0)
            run.assert_not_called()
