# Apple Store Monitor (English Guide)

[中文指南](README.md)

Python + Playwright script that attaches to a real Chromium browser, refreshes Apple Store cookies, and sends Markdown-formatted Telegram alerts whenever pickup inventory appears.

## Prerequisites
- Python 3.11
- [`poetry`](https://python-poetry.org/) for dependency management

```bash
# Install dependencies
poetry install

# Install Playwright browsers (downloads Chromium)
poetry run playwright install
```

## Start Chromium and Capture Cookies
1. After the Playwright install finishes, note the Chromium path printed to the console, e.g.
   ```
   /Users/yourname/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium
   ```
2. Launch Chromium with a remote debugging port so the script can attach via CDP:
   ```bash
   /Users/yourname/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium \
     --remote-debugging-port=9222
   ```
3. In that browser window, manually open the product page you want to watch, for example:
   ```
   https://www.apple.com/hk-zh/shop/buy-iphone/iphone-17-pro/6.3-%E5%90%8B%E9%A1%AF%E7%A4%BA%E5%99%A8-256gb-%E9%8A%80%E8%89%B2
   ```
4. Check the Network tab and verify the `shop/fulfillment-messages` request returns `200`; this confirms valid session cookies for the monitor.

## Run the Monitor
```bash
poetry run python main.py
```
The script reuses the remote-debugging Chromium to refresh cookies, polls Apple Store inventory, and pushes Telegram alerts when stock is available.

> Before running, export `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and optionally `TELEGRAM_TOPIC_ID` so alerts reach your chat or topic.

## Customization
- To use a different Chrome/Chromium binary, edit the Playwright launch configuration in `main.py`.
- Chromium currently runs in headed mode for easier debugging. Feel free to switch to headless if desired.

See the [中文指南](README.md) for the Chinese version.
