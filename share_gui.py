"""Windows sharing interface; the owner's CLI and Fedora service are separate."""
import json
from pathlib import Path
import sys
import tempfile
import time
from shiboken6 import delete
import uuid

from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from share_policy import access_allowed
from share_protocol import EventReader, profile_path, validate_profile


STYLE = """
QMainWindow, QWidget#page { background: #f3f6fb; }
QWidget { color: #20344d; font-size: 13px; }
QFrame#card { background: white; border: 1px solid #e2e9f2; border-radius: 14px; }
QLabel#title { font-size: 25px; font-weight: 700; color: #142b48; }
QLabel#muted { color: #718197; }
QLabel#metric { font-size: 25px; font-weight: 700; color: #1d4ed8; }
QLabel#badge { background: #e7eefc; color: #2457a7; border-radius: 12px; padding: 7px 14px; }
QLineEdit, QSpinBox { background: #f8faff; border: 1px solid #dbe3ef; border-radius: 7px; padding: 8px; }
QPushButton { background: #e9eff9; color: #24456f; border: none; border-radius: 8px; padding: 11px 16px; font-weight: 600; }
QPushButton:hover { background: #dbe7fb; }
QPushButton#primary { background: #2563eb; color: white; }
QPushButton#primary:hover { background: #1d4ed8; }
QPushButton#stop { background: #fff0f0; color: #b83246; }
QPushButton:disabled { background: #edf1f6; color: #9aa8ba; }
QTableWidget { background: white; border: none; gridline-color: #eef2f7; selection-background-color: #eff5ff; }
QHeaderView::section { background: #f7f9fd; color: #6a7c93; padding: 10px; border: none; font-weight: 600; }
QProgressBar { border: none; border-radius: 6px; background: #e8eef8; text-align: center; min-height: 17px; }
QProgressBar::chunk { background: #3b82f6; border-radius: 6px; }
QPlainTextEdit { background: #14263e; color: #d9e5f5; border: none; border-radius: 9px; padding: 10px; font-size: 12px; }
"""


class ShareWindow(QMainWindow):
    def __init__(self, data_root=None):
        super().__init__()
        if data_root is None:
            from utils import getDir
            data_root = getDir()
        self.data_root = Path(data_root)
        self.setWindowTitle("学习助手")
        self.resize(1060, 800)
        self.setMinimumSize(900, 710)
        self.process = None
        self.reader = None
        self.active_directory = None
        self.action = None
        self.run_deadline = None
        self.stopping = False
        self._expiring = False
        self.terminal_event = False
        self.courses = []
        self.checks = []
        self.row_ids = {}
        self._build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(250)
        self._load_courses()

    def _card(self):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        return frame, layout

    def _build(self):
        page = QWidget()
        page.setObjectName("page")
        self.setCentralWidget(page)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(17)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("学习助手")
        title.setObjectName("title")
        titles.addWidget(title)
        sub = QLabel("扫码登录，选择课程，一键开始。")
        sub.setObjectName("muted")
        titles.addWidget(sub)
        header.addLayout(titles)
        header.addStretch()
        self.badge = QLabel("准备就绪")
        self.badge.setObjectName("badge")
        header.addWidget(self.badge)
        outer.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(17)
        account, account_layout = self._card()
        account.setFixedWidth(270)
        account_layout.addWidget(QLabel("01  登录账号"))
        profile_label = QLabel("本机账号档案")
        profile_label.setObjectName("muted")
        account_layout.addWidget(profile_label)
        self.profile = QLineEdit("shared")
        self.profile.setMaxLength(40)
        self.profile.editingFinished.connect(self._load_courses)
        account_layout.addWidget(self.profile)
        self.login = QPushButton("扫码登录 / 刷新课程")
        self.login.setObjectName("primary")
        self.login.clicked.connect(lambda: self._start("fetch"))
        account_layout.addWidget(self.login)
        self.qr = QLabel("二维码将在这里显示\n请使用知到 App 扫码确认")
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setWordWrap(True)
        self.qr.setFixedSize(180, 180)
        self.qr.setStyleSheet("background:#f4f7fd; border:1px dashed #c9d5e6; border-radius:12px; color:#73849c;")
        account_layout.addWidget(self.qr, alignment=Qt.AlignmentFlag.AlignCenter)
        self.account_status = QLabel("无需输入密码。登录数据仅保存在本机。")
        self.account_status.setObjectName("muted")
        self.account_status.setWordWrap(True)
        account_layout.addWidget(self.account_status)
        account_layout.addStretch()
        self.minutes = QSpinBox()
        self.minutes.setRange(10, 240)
        self.minutes.setValue(120)
        self.minutes.setSuffix(" 分钟")
        body.addWidget(account)

        right = QVBoxLayout()
        metrics, metrics_layout = self._card()
        metrics_row = QHBoxLayout()
        self.metric_courses = self._metric(metrics_row, "已读取课程", "0")
        self.metric_done = self._metric(metrics_row, "本次确认完成", "0")
        self._metric(metrics_row, "播放速度", "1.0×")
        metrics_layout.addLayout(metrics_row)
        right.addWidget(metrics)
        courses_card, courses_layout = self._card()
        table_header = QHBoxLayout()
        table_header.addWidget(QLabel("02  选择课程"))
        table_header.addStretch()
        self.select_all = QCheckBox("全选可学习课程")
        self.select_all.toggled.connect(self._toggle_all)
        table_header.addWidget(self.select_all)
        courses_layout.addLayout(table_header)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["选择", "课程", "类型", "状态"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 48)
        self.table.setColumnWidth(2, 95)
        self.table.setColumnWidth(3, 140)
        self.table.setMinimumHeight(180)
        courses_layout.addWidget(self.table)
        self.current_video = QLabel("先登录并获取课程，再勾选要学习的课程。")
        self.current_video.setWordWrap(True)
        self.current_video.setTextFormat(Qt.TextFormat.PlainText)
        courses_layout.addWidget(self.current_video)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        courses_layout.addWidget(self.progress)
        actions = QHBoxLayout()
        self.start = QPushButton("开始所选课程")
        self.start.setObjectName("primary")
        self.start.clicked.connect(lambda: self._start("learn"))
        self.start.setEnabled(False)
        self.stop = QPushButton("停止")
        self.stop.setObjectName("stop")
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self._stop)
        actions.addWidget(self.start)
        actions.addWidget(self.stop)
        courses_layout.addLayout(actions)
        right.addWidget(courses_card, 1)
        body.addLayout(right, 1)
        outer.addLayout(body, 1)
        log_card, log_layout = self._card()
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("运行记录"))
        log_header.addStretch()
        log_header.addWidget(QLabel("本次最长运行"))
        log_header.addWidget(self.minutes)
        log_layout.addLayout(log_header)
        note = QLabel("普通视频 · 1.0 倍速 · 正式考试、作业和付费 AI 不在此界面运行。")
        note.setObjectName("muted")
        log_layout.addWidget(note)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(800)
        self.log.setMaximumHeight(95)
        log_layout.addWidget(self.log)
        outer.addWidget(log_card)
        self._message("准备就绪。点击左侧按钮扫码登录。")

    def _metric(self, row, title, value):
        column = QVBoxLayout()
        label = QLabel(title)
        label.setObjectName("muted")
        number = QLabel(value)
        number.setObjectName("metric")
        column.addWidget(label)
        column.addWidget(number)
        row.addLayout(column, 1)
        return number

    def _message(self, text):
        from datetime import datetime
        self.log.appendPlainText(datetime.now().strftime("%H:%M:%S") + "  " + text)

    def _load_courses(self):
        try:
            path = profile_path(self.data_root, self.profile.text().strip()) / "execution.json"
            courses = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            self._render_courses(courses)
        except (ValueError, OSError):
            self._render_courses([])

    def _render_courses(self, courses):
        self.courses = courses
        self.table.setRowCount(len(courses))
        self.checks = []
        self.row_ids = {}
        self.select_all.setChecked(False)
        kinds = {"zhidao": "共享课", "hike": "校内课", "ai": "AI 课程", "polymas": "Polymas 视频"}
        for row, course in enumerate(courses):
            check = QCheckBox()
            check.setEnabled(course.get("type") != "ai")
            self.table.setCellWidget(row, 0, check)
            self.checks.append(check)
            self.row_ids[course["id"]] = row
            self.table.setItem(row, 1, QTableWidgetItem(course["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(kinds.get(course.get("type"), "课程")))
            self.table.setItem(row, 3, QTableWidgetItem("仅展示" if course.get("type") == "ai" else "待选择"))
        self.metric_courses.setText(str(len(courses)))
        self.start.setEnabled(bool(courses) and not self._busy())

    def _toggle_all(self, checked):
        for check in self.checks:
            if check.isEnabled():
                check.setChecked(checked)

    def _busy(self):
        return self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning

    def _controls(self, busy):
        for widget in (self.login, self.profile, self.minutes, self.select_all, self.table):
            widget.setEnabled(not busy)
        self.start.setEnabled(not busy and bool(self.courses))
        self.stop.setEnabled(busy)

    def _start(self, action):
        if not access_allowed():
            self._expire()
            return
        if self._busy():
            return
        try:
            name = validate_profile(self.profile.text().strip())
        except ValueError as error:
            self._message(str(error))
            return
        selected = [c["id"] for c, check in zip(self.courses, self.checks) if check.isChecked() and check.isEnabled()]
        if action == "learn" and not selected:
            self._message("请先勾选至少一门可学习课程。")
            return
        self.active_directory = profile_path(self.data_root, name)
        filename = "gui-" + uuid.uuid4().hex + ".jsonl"
        self.reader = EventReader(self.active_directory / "gui-events" / filename)
        args = ["--worker", "--action", action, "--profile", name, "--events", filename,
                "--minutes", str(self.minutes.value())]
        for cid in selected:
            args.extend(["--course", cid])
        self.process = QProcess(self)
        if getattr(sys, "frozen", False):
            program = sys.executable
        else:
            program = sys.executable
            args.insert(0, str(Path(__file__).with_name("windows_entry.py")))
        self.process.setProgram(program)
        self.process.setArguments(args)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)
        self.action = action
        self.run_deadline = time.monotonic() + self.minutes.value() * 60 if action == "learn" else None
        self.stopping = False
        self.terminal_event = False
        self._controls(True)
        self.badge.setText("正在登录" if action == "fetch" else "正在学习")
        self._message("正在读取课程与登录状态…" if action == "fetch" else "任务已开始，保持窗口打开即可。")
        self.process.start()

    def _poll(self):
        if not access_allowed():
            self._expire()
            return
        if self._busy() and self.run_deadline is not None and time.monotonic() >= self.run_deadline:
            self.run_deadline = None
            self._message("已达到本次最长运行时间，正在停止。")
            self._stop()
        if self.reader is not None:
            for event in self.reader.read():
                self._event(event)

    def _event(self, event):
        kind = event.get("event")
        if kind == "qr":
            path = self.active_directory / "qr-login.png"
            image = QPixmap(str(path))
            self.qr.setPixmap(image.scaled(170, 170, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))
            self.account_status.setText("请用知到 App 扫码，并在手机确认登录。")
            self._message("二维码已准备好，请在手机确认。")
        elif kind == "authenticated":
            self.qr.setPixmap(QPixmap())
            self.qr.setText("✓\n已登录")
            self.account_status.setText("登录成功，正在读取课程。")
            self._message(event["message"])
        elif kind == "courses":
            self._render_courses(event["courses"])
        elif kind == "course":
            row = self.row_ids.get(event["id"])
            if row is not None:
                self.table.item(row, 3).setText(event["status"])
        elif kind == "video":
            self.current_video.setText(f"{event['course']} · {event['index']}/{event['total']}\n{event['name']}")
            self.progress.setValue(0)
            self._message("开始：" + event["name"])
        elif kind == "progress":
            duration = event.get("duration", 0)
            if duration > 0:
                self.progress.setValue(min(100, int(event["seconds"] * 100 / duration)))
                self.progress.setFormat(f"已上报 {event['seconds']} / {duration} 秒 · %p%")
        elif kind == "video_done":
            self.metric_done.setText(str(event["confirmed"]))
            self._message(("服务端确认完成：" if event["verified"] else "视频已处理，完成状态待回读：") + event["name"])
        elif kind in ("error", "done"):
            self.terminal_event = True
            self.badge.setText("需要处理" if kind == "error" else "本次已结束")
            self.account_status.setText(event["message"])
            self._message(event["message"])
        elif "message" in event:
            self._message(event["message"])

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.terminal_event = True
            self.badge.setText("启动失败")
            self._message("无法启动学习进程，请完整解压程序后再试。")
            self._controls(False)

    def _finished(self, code, _status):
        self._poll()
        if not access_allowed():
            return
        self._controls(False)
        if self.stopping:
            self.badge.setText("已停止")
            self._message("已停止。已上报的进度保留，下次会重新读取。")
        elif not self.terminal_event:
            self.badge.setText("任务已停止")
            self._message(f"任务已停止（退出码 {code}）。请刷新课程或重新登录后重试。")

    def _stop(self):
        self.stopping = True
        if self._busy():
            self.process.kill()

    def _expire(self):
        # Expiry is silent. No dialog, console, deletion or damage to user files.
        if self._expiring:
            return
        self._expiring = True
        self.timer.stop()
        if self._busy():
            self.process.kill()
            self.process.waitForFinished(1500)
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self._busy():
            self.process.kill()
            self.process.waitForFinished(1500)
        event.accept()


def main(smoke_test=False):
    if not access_allowed():
        return 0
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI" if sys.platform == "win32" else "Noto Sans CJK SC", 10))
    app.setStyleSheet(STYLE)
    if smoke_test:
        with tempfile.TemporaryDirectory() as directory:
            window = ShareWindow(directory)
            window.show()
            app.processEvents()
            window.timer.stop()
            window.close()
            delete(window)
        return 0
    window = ShareWindow()
    window.show()
    try:
        return app.exec()
    finally:
        window.timer.stop()
        window.close()
        delete(window)
