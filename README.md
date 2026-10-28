> **Windows 迁移入口（当前分支）**
>
> 下载/检出你自己的 fork 的 `codex/windows-exe` 分支。
> [Windows 迁移与 CLI 实时进度](docs/WINDOWS_MIGRATION.md) · [GUI / EXE 构建](docs/WINDOWS_BUILD.md)。
>
> 当前分支已包含 GUI、跨平台账号锁、日志脱敏/轮转和 Fedora 前台实时进度选项。
> 分享用 GUI 于香港时间 2026-11-06 00:00 静默停用；自己的 `main.py` CLI 不受影响。
> 每台电脑重新扫码，不携带旧账号、Cookie 或 API Key。学习进度以平台服务器为准。
> 下方为早期项目说明；涉及默认行为、日志和自动发布的旧描述，以当前迁移文档和代码为准。
> 当前工作流仅手动构建，不随推送发布 Release。

# fuckZHS v2.9.0

基于 [VermiIIi0n/fuckZHS](https://github.com/VermiIIi0n/fuckZHS) 的智慧树自动刷课脚本，集成本地多Profile/DeepSeek与社区最新PR改进。

## 核心特性与改进

| 功能 | 说明 |
|------|------|
| **2026 AI 智课 (Polymas) 适配** | 适配 2026 改版后大规模迁移至 polymas 平台的 AI 智课，自动拉取、树形解析与播放 |
| **反风控与自动重试机制** | 播放速度与上报间隔随机微抖动；每连看 45 分钟休息防风控；撞验证码自动退避重试（最多8次） |
| **填空题 (Type=3) AI 作答** | 填空题 Prompt 模板与答案生成，支持回顾模式提取文本与客观题自动作答 |
| **全课程每日总时限** | `-l` 改为每日跨课程共享时限，自动持久化 `daily_limit.json`，多 Profile 独立隔离 |
| **DeepSeek API 默认接入** | 默认采用 DeepSeek，性价比高；支持根目录 `key` 文件外置密钥安全分享 |
| **账户切换 (Profile)** | `-P 名字` 切换多账户，cookies、时限、日志、配置全面隔离 |
| **二维码本地暂存** | 每次生成二维码自动保存至 `images/qr.temp.jpg`，解决 Windows 终端乱码问题 |
| **日志持久化** | 日志改为追加写入 (`mode='a'`)，排查问题不丢失历史记录 |
| **考试容错与死循环修复** | 考试重试上限 5 次，修复选项少于 2 个时的解包崩溃 bug |
| **PyInstaller 打包兼容** | 完善依赖收集 (`collect_all`) 与 GitHub Actions 自动 Release 打包 |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 直接刷（自动检测知到/共享课/AI智课并防风控运行）
python main.py

# 拉取课程清单（保存至 execution.json，带 polymas: 前缀）
python main.py -f

# 多账户隔离
python main.py -P 张三
python main.py -P 李四

# AI 答题（配置 DeepSeek API Key）
# 把 key 写到程序根目录的 key 文件（或者 config.json）
echo "sk-your-deepseek-key" > key
python main.py
```

## 命令行参数

```
-c, --course     课程 ID（支持 courseId、recruitAndCourseId 或 polymas:courseId）
-v, --videos     视频 ID（支持 fileId、videoId 或 polymas resourceId）
-P, --profile    账户名（cookies / 时限存在 profiles/<名字>/）
-q, --qrlogin    二维码登录（强制推荐）
-f, --fetch      拉取课程清单并保存到 execution.json
-s, --speed      播放速度（默认 1.5，带防检测抖动）
-l, --limit      每日总时限（分钟，所有课程共享累计）
-t, --threshold  完成百分比阈值（默认 0.91）
-d, --debug      调试模式日志
--proxy          代理配置，如 http://127.0.0.1:7890
-h, --help       帮助
```

## API Key

把 DeepSeek key 写到程序根目录的 `key` 文件（一行纯文本）：

```
sk-xxxxxxxxxxxxxxxx
```

- Profile 内的 `key` 优先，其次根目录 `key`，均覆盖 config.json 的 api_key
- 删除 `key` 文件即可安全分享给他人
- 默认禁用 AI；空白/示例密钥禁止创建外部 API 客户端；答案生成失败时终止，不随机作答
- 兼容 OpenAI / DeepSeek / 其他兼容接口

## PyInstaller 打包

```bash
pip install pyinstaller
pyinstaller --onedir --name fuckZHS --add-data "meta.json;." \
  --hidden-import PIL --hidden-import PIL.Image \
  --hidden-import Crypto --hidden-import Crypto.Cipher \
  --hidden-import tiktoken --hidden-import openai \
  --hidden-import requests --clean --noconfirm main.py

# 然后把 config.json execution.json meta.json 拷到 dist/fuckZHS/ 里
```

## License

与原项目一致，MIT License。

## Fedora 安全运行

部署验收及实际账户状态见 [docs/FEDORA_RUN_REPORT.md](docs/FEDORA_RUN_REPORT.md)。
登录/清单验证使用 `.venv/bin/python main.py -P nagi -f`。
后台执行器 `scripts/fedora_runner.py` 仅处理视频及已授权的随堂互动题，跳过正式考试、作业、无效资源和已完成内容；优先采用接口明确答案，必要时有界调用 DeepSeek，无法作答即停止受影响任务；先验证服务端进度增加再持续运行。
用户级 unit 源码见 `systemd/fuckzhs-nagi.service`，代理地址为本机现有配置；无可用视频时正常退出。
