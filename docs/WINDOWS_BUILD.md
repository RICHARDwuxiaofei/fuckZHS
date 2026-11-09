# Windows GUI 构建

- PASS — 已增加独立 GUI：内嵌二维码、课程勾选、1 倍速视频、进度回读、停止按钮和有上限的运行记录。AI 课程仅展示，不调用付费 API，不处理正式考试和作业。
- PASS — 分发入口于北京时间（UTC+8）**2026-11-21 00:00** 起静默退出，无弹窗、无到期提示，也不删除用户文件。已打开的 GUI 会停止工作进程并退出；工作进程请求前后也检查日期。自己的 `main.py` 命令行及 Fedora 服务不受此限制。
- PASS (code/test) — 使用多个 HTTPS 站点的响应 Date 头获取 UTC 时间（百度、腾讯、Cloudflare 依次尝试）；约每 30 秒复核一次，间隔只使用单调时钟估算，不信任电脑本地日期。断网或时钟获取失败立即拒绝继续执行，不使用离线放行。注意：由于程序在用户电脑运行，源码修改及逆向仍可能绕过，不是强 DRM。
- PASS — 25 项单元测试在 Windows 独立构建环境通过，包含验证码、未知随堂题停止和日期边界检查。
- PASS — 跨进程单实例锁、有效 Cookie 的真实接口验证逻辑、无密钥 GUI 工作进程、独立账号目录；课程完成统计需要服务端回读确认。
- PASS — 打包严格使用源码白名单，不携带本机 Git 历史、账户、配置、Key、Cookie、二维码、日志和 Fedora 报告。源文件检查会在内存中比对本地实际 Key，不输出其内容。
- PASS — 生成无控制台窗口的 GUI，移除旧 CMD 启动器。构建脚本执行单元测试、成品隐私审计和 GUI 启动/退出检查。
- PASS — 2026-10-28 使用 Windows 11 x64、Python 3.13.9、PyInstaller 6.22.3、PySide6-Essentials 6.11.1 完成原生编译及 GUI 启动/退出检查；CLI 图片扫码、Cookie 恢复和课程接口已实测。GUI 未登录个人账户。
- NOT_TESTED — SmartScreen、代码签名及其他电脑的兼容性；本地产物未上传或发布。

## 在自己的 Windows PC 编译

使用 Python 3.12 x64，在本分支目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

成功后得到 `dist/fuckZHS-Windows-x64.zip`。完整解压后双击 `fuckZHS.exe`。
构建使用独立虚拟环境，不复制任何本机 Profile。运行后每个人独立扫码。
构建时临时收窄 PATH，避免其他工具目录的 ICU DLL 混入；GUI 启动自检上限 30 秒。
GUI 默认使用 `shared` 档案。关闭窗口会结束其工作进程，不安装后台服务。

目标仅为用户自己的 fork `RICHARDwuxiaofei/fuckZHS`，分支 `release/expire-2026-11-20`。
限时分支推送触发 GitHub Actions，在 Windows 运行测试、构建与隐私审计，通过后上传 Windows ZIP 到带 `prerelease=true` 的 GitHub Pre-release，且不修改 master。
独立源码快照不含 Fedora 的 Git 历史及运行报告。

修改后重新执行 `scripts/prepare_windows_source.py` 生成白名单源码包和 SHA256 清单。
PyInstaller 的 Windows EXE 必须在 Windows 构建：
https://pyinstaller.org/en/stable/operating-mode.html
