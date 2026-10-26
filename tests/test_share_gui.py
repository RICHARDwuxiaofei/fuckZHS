import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
HAS_QT = importlib.util.find_spec('PySide6') is not None


@unittest.skipUnless(HAS_QT, 'Qt is only required for the sharing GUI/build environment')
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from share_gui import ShareWindow
        self.temp = tempfile.TemporaryDirectory()
        self.window = ShareWindow(self.temp.name)

    def tearDown(self):
        self.window.close()
        self.window.timer.stop()
        from shiboken6 import delete
        delete(self.window)
        self.temp.cleanup()

    def test_course_selection_and_server_confirmed_count(self):
        w = self.window
        w._render_courses([{'id': '1', 'name': '普通视频', 'type': 'zhidao'},
                           {'id': '2', 'name': 'AI 课', 'type': 'ai'}])
        w.select_all.setChecked(True)
        self.assertTrue(w.checks[0].isChecked())
        self.assertFalse(w.checks[1].isEnabled())
        self.assertFalse(w.checks[1].isChecked())
        w._event({'event': 'progress', 'seconds': 30, 'duration': 60})
        self.assertEqual(w.progress.value(), 50)
        w._event({'event': 'video_done', 'confirmed': 1, 'verified': True, 'name': '视频'})
        self.assertEqual(w.metric_done.text(), '1')

    def test_no_selection_does_not_start_worker(self):
        self.window._start('learn')
        self.assertIsNone(self.window.process)

    def test_expiry_is_silent_and_does_not_delete_files(self):
        from PySide6.QtWidgets import QMessageBox
        sentinel = Path(self.temp.name) / 'user-data'
        sentinel.write_text('keep')
        with patch('share_gui.access_allowed', return_value=False), patch.object(QMessageBox, 'warning') as warning:
            self.window._poll()
            self.assertTrue(self.window._expiring)
            self.assertFalse(self.window.timer.isActive())
            warning.assert_not_called()
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_expiry_stops_an_active_worker_without_a_dialog(self):
        from unittest.mock import Mock
        from PySide6.QtCore import QProcess
        worker = Mock()
        worker.state.return_value = QProcess.ProcessState.Running
        self.window.process = worker
        with patch('share_gui.access_allowed', return_value=False):
            self.window._poll()
        worker.kill.assert_called_once()
        worker.waitForFinished.assert_called_once_with(1500)
        worker.state.return_value = QProcess.ProcessState.NotRunning
