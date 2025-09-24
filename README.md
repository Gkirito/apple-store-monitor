# Apple Store Monitor

[English Guide](README.en.md)

基于 Python + Playwright 的 Apple Store 库存监控脚本，连接真实浏览器刷新 Cookie，检测到库存时通过 Telegram 发送 Markdown 报警。

## 环境准备
- Python 3.11
- [`poetry`](https://python-poetry.org/) 管理依赖

```bash
# 1. 安装依赖
poetry install

# 2. 安装 Playwright 浏览器（会下载 Chromium）
poetry run playwright install
```

## 启动 Chromium 并获取 Cookie
1. Playwright 安装完成后，记住终端打印的 Chromium 路径，例如：
   ```
   /Users/你的用户名/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium
   ```
2. 使用远程调试端口启动 Chromium，供脚本复用：
   ```bash
   /Users/你的用户名/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium \
     --remote-debugging-port=9222
   ```
3. 在该窗口访问要监控的商品页面，例如：
   ```
   https://www.apple.com/hk-zh/shop/buy-iphone/iphone-17-pro/6.3-%E5%90%8B%E9%A1%AF%E7%A4%BA%E5%99%A8-256gb-%E9%8A%80%E8%89%B2
   ```
4. 打开开发者工具，确认 `shop/fulfillment-messages` 请求返回 `200`，说明 Cookie 生效。

## 运行监控脚本
```bash
poetry run python main.py
```
脚本会复用远程调试的 Chromium 获取 Cookie，定期查询库存，有货时向 Telegram 群/频道推送 Markdown 报警。

> 运行前请设置 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`，可选设置 `TELEGRAM_TOPIC_ID` 以发送到特定话题。

## 进一步自定义
- 需要改用系统 Chrome 或其它浏览器，可在 `main.py` 中调整 Playwright 的 `executable_path`。
- 默认使用可视模式便于调试，若想改为无头模式，可自行修改代码。

更多细节可参考 [English Guide](README.en.md)。
