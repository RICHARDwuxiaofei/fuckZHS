# Windows 构建状态

- PASS — 已修复 main.py 无条件导入 Linux fcntl 的兼容性问题，改用 Windows msvcrt / Unix flock 的单实例锁。
- PASS — 本地跨进程锁冲突与释放测试、既有安全测试共 11 项通过；Windows 入口的帮助命令通过。
- PASS — 默认双击 EXE 仅扫码登录并获取课程。提供 Login.cmd / Learn.cmd，默认关闭 AI 和正式考试，学习启动器使用 1 倍速并跳过互动答题视频。
- PASS — PyInstaller 仅收集程序依赖及 meta.json；构建脚本只另外复制干净的 Windows 启动器、说明与许可证，审计禁止出现 profiles、key、config、cookies、日志与二维码。
- PASS — 源码构建包严格包含 25 个白名单文件及 SHA256 清单；本地 Key 的实际内容未出现在任何打包文件中，检查过程不输出 Key。
- PARTIAL — 已准备 Windows x64 构建脚本和 GitHub Actions 工作流。Fedora 当前没有 Windows Python / Wine 环境，不能将本地 Linux 打包结果当作 Windows EXE。
- NOT_TESTED — 真正的 Windows 构建、Windows 原生锁测试、生成 EXE 的启动与扫码。Windows CI 配置为执行单元测试、打包和 EXE 帮助命令检查；扫码仍需用户本人在实际 Windows 桌面验证。
- NOT_TESTED — Windows Authenticode 签名和 SmartScreen 信誉。

## 构建

在 Windows x64 上使用 Python 3.12，执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

构建使用项目独立虚拟环境，成功产物为 dist/fuckZHS-Windows-x64.zip。完整解压后可直接运行，无需在目标电脑安装 Python。

已准备的构建工作流只上传下载产物，不发布 Release。尚未推送本地分支，也没有触发远端构建。

用于远端构建的独立源码快照不包含本机 Git 历史、Fedora 运行报告、账户数据或已有日志。

Windows 版本包含命令行程序及其依赖文件夹；Fedora 的 systemd 后台服务和巡检不会移植或打包进去。

官方依据：https://pyinstaller.org/en/stable/operating-mode.html
