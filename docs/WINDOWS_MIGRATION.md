# 从 Fedora 换到 Windows

## 云端内容与迁移边界

- PASS — 当前维护分支为自己 fork 的 `codex/windows-exe`，包含本项目源码、测试、GUI/EXE 构建文件、Fedora runner 的 `--live` 改动，以及原仓库静态说明资源。
- PASS — 不上传本机 Git 历史、个人运行报告、账号 Profile、Key、Cookie、二维码、运行日志、虚拟环境或生成产物。固定的上游说明图片与临时二维码不同，源码包仅包含逐项白名单内的静态图片。
- PASS — GitHub 构建只允许手动触发，不自动创建 Release；不会推送上游仓库。
- NOT_TESTED — Windows 原生安装、扫码、视频学习和打包，需要在新电脑实际验证。Linux 上测试通过不能代替这些结果。

## 自己使用 CLI（不受分享版日期限制）

在 Windows PowerShell 中进入项目文件夹。推荐安装 Python 3.12 x64，然后执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe main.py -h
.\.venv\Scripts\python.exe main.py -P nagi -f
```

最后一条仅扫码登录、获取课程。使用自己的知到 App 确认，登录数据会在新电脑本地生成。
不需要从旧电脑复制 Cookie、Key 或配置。学习记录存于平台服务器，重新扫码后回读。

需要在终端实时显示普通共享课/校内视频进度时：

```powershell
.\.venv\Scripts\python.exe -u main.py -P nagi --videos-only --noexam -s 1 -t 1 -l 540
```

`Ctrl+C` 停止。该方式保持终端打开，默认显示课程树与进度条，使用 1 倍速，最长每日 540 分钟。
不要同时开 GUI 或另一个相同账号的任务。`--videos-only` 保守跳过 AI/Polymas 和需要交互答题的视频；因此不能将命令退出当作所有课程完成。
Windows 上不要运行 `scripts/fedora_runner.py`：它使用 Linux 的 fcntl 和 systemd，保留仅用于原 Fedora 环境。CLI 的跨平台入口是 `main.py`。

## 分享 GUI / 编译 EXE

如需源码启动 GUI，先安装独立构建依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build-windows.txt
.\.venv\Scripts\python.exe windows_entry.py
```

编译：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

产物 `dist/fuckZHS-Windows-x64.zip` 完整解压后运行 `fuckZHS.exe`，保留 `_internal`。
分享 GUI 和其工作进程在香港时间 2026-11-06 00:00 起静默退出，不弹提示，不删除文件。
该日期限制不能防止别人修改时间或源码；自己的 CLI 不检查该日期。

初始配置关闭付费 AI。若以后需要接入，必须在自己新电脑上单独设置真实 Key，切勿提交到 Git。
不随本次迁移测试任何付费调用、正式考试或作业提交。

## 原 Fedora 后台任务

换电脑不会把原 Linux 服务迁移到 Windows，也不会自动停止它。迁移时应先在 Fedora 停止旧任务，避免两个电脑同时操作同一账号：

```bash
systemctl --user stop fuckzhs-nagi.service
```

本次云端同步仅整理并上传源码，不改变旧服务的运行状态，也不重新启用定时巡检。
