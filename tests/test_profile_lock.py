import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from profile_lock import acquire_profile_lock


class ProfileLockTests(unittest.TestCase):
    def test_other_process_is_blocked_and_can_retry_after_release(self):
        child = (
            "import sys\nfrom profile_lock import acquire_profile_lock\n"
            "try:\n lock = acquire_profile_lock(sys.argv[1])\n"
            "except BlockingIOError:\n sys.exit(23)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "run.lock")
            lock = acquire_profile_lock(path)
            try:
                result = subprocess.run([sys.executable, "-c", child, path], cwd=ROOT)
                self.assertEqual(result.returncode, 23)
            finally:
                lock.close()
            result = subprocess.run([sys.executable, "-c", child, path], cwd=ROOT)
            self.assertEqual(result.returncode, 0)
