# fuckZHS v2.8.0

基于 [VermiIIi0n/fuckZHS](https://github.com/VermiIIi0n/fuckZHS) 的智慧树自动刷课脚本。

## 原版改进

| 功能 | 说明 |
|------|------|
| AI 课程自动检测 | 不再需要手动 `-ai`，启动即自动识别并刷所有 AI 课程 |
| DeepSeek API 接入 | 默认使用 DeepSeek 答题，便宜好用，也可切回 OpenAI |
| 账户切换 (Profile) | `-P 名字` 切换账户，cookies 隔离，换人不重登 |
| tiktoken 容错 | 打包环境缺失编码文件时自动降级，不会闪退 |
| 死循环修复 | 考试重试上限 5 次，不再无限卡死 |
| 返回值 bug 修复 | 修复选项少于 2 个时解包崩溃 |
| PyInstaller 打包支持 | 适配路径，可打包为 exe 免装 Python 分发 |
| API Key 外置 | key 写在单独文件，删除即安全，不会随 config 泄露 |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 直接刷
python main.py

# 多账户
python main.py -P 张三
python main.py -P 李四

# AI 答题（需要 DeepSeek key）
# 把 key 写到程序根目录的 key 文件里
echo "sk-your-key" > key
python main.py
```

## 命令行参数

```
-c, --course     课程 ID
-v, --videos     视频 ID
-P, --profile    账户名（cookies 存在 profiles/<名字>/）
-q, --qrlogin    二维码登录
-f, --fetch      拉课程列表
-s, --speed      播放速度
-l, --limit      单课时限（分钟）
-d, --debug      调试模式
--proxy          代理
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
