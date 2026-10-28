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
        w._event({'event': 'playback', 'seconds': 30, 'duration': 60})
        self.assertEqual(w.progress.value(), 500)
        w._event({'event': 'progress', 'seconds': 25, 'duration': 60})
        self.assertEqual(w.progress.value(), 500)
        self.assertIn('00:25', w.server_progress.text())
        w._event({'event': 'video_done', 'confirmed': 1, 'verified': True, 'name': '视频'})
        self.assertEqual(w.metric_done.text(), '1')

    def test_no_selection_does_not_start_worker(self):
        self.window._start('learn')
        self.assertIsNone(self.window.process)

    def test_overview_keeps_platform_percent_separate_and_unknown_excluded(self):
        w = self.window
        w._render_courses([{'id':'one','name':'课程一','type':'zhidao','platform_percent':32.3},
                           {'id':'two','name':'课程二','type':'zhidao'}])
        w._event({'event':'course_progress','id':'one', 'progress':{
            'status':'ok','completed':31,'total':80,'percent':38.75}})
        self.assertEqual(w.metric_videos.text(), '31 / 80')
        self.assertEqual(w.semester_progress.value(), 388)
        self.assertEqual(w.table.item(0,3).text(), '32.3%')
        self.assertIn('1 / 2', w.coverage.text())
        w._event({'event':'course_progress','id':'two','progress':{'status':'error','message':'读取失败'}})
        self.assertEqual(w.metric_videos.text(), '31 / 80')

    def test_selection_preserved_and_only_selected_courses_enable_start(self):
        w = self.window
        courses = [{'id': '1', 'name': '普通视频', 'type': 'zhidao'}]
        w._render_courses(courses)
        self.assertFalse(w.start.isEnabled())
        w.checks[0].setChecked(True)
        self.assertTrue(w.start.isEnabled())
        w._render_courses(courses)
        self.assertTrue(w.checks[0].isChecked())

    def test_owner_source_window_has_no_sharing_expiry(self):
        from share_gui import ShareWindow
        from shiboken6 import delete
        w = ShareWindow(self.temp.name, owner_mode=True)
        try:
            with patch('share_gui.access_allowed', return_value=False):
                w._poll()
            self.assertFalse(w._expiring)
            self.assertEqual(w.profile.text(), 'nagi')
        finally:
            w.timer.stop()
            w.close()
            delete(w)

    def test_qr_is_embedded_and_cleared_after_authentication(self):
        from PySide6.QtGui import QImage
        from PySide6.QtCore import Qt
        w = self.window
        w.active_directory = Path(self.temp.name)
        image = QImage(200, 200, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        image.save(str(w.active_directory / 'qr-login.png'))
        w._event({'event':'qr'})
        self.assertFalse(w.qr.pixmap().isNull())
        w._event({'event':'authenticated', 'message':'登录成功'})
        self.assertTrue(w.qr.pixmap().isNull())
        self.assertIn('已登录', w.qr.text())

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
