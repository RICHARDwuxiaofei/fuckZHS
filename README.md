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

- 存在则覆盖 config.json 的 api_key
- 删除 `key` 文件即可安全分享给他人
- 没有 key 时考试随机蒙答案
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
