import os
import time
import datetime
import threading
from contextlib import suppress
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


APPLE_BASE_URL = 'https://www.apple.com'
APPLE_LOCALE = 'hk-zh'
APPLE_LOCALE_PREFIX = f'/{APPLE_LOCALE}' if APPLE_LOCALE else ''
APPLE_LOCALE_BASE = f'{APPLE_BASE_URL}{APPLE_LOCALE_PREFIX}'
APPLE_PRODUCT_PATH = 'shop/buy-iphone/iphone-17-pro/6.3-%E5%90%8B%E9%A1%AF%E7%A4%BA%E5%99%A8-256gb-%E9%8A%80%E8%89%B2'
MODEL_CODE = 'MG8G4ZA/A'
APPLE_BAG_STATUS_PATH = f'shop/fulfillment-messages?fae=true&little=false&parts.0={MODEL_CODE}&mts.0=regular&mts.1=sticky&fts=true'
LOCATION = 'Hong Kong'
CHECK_INTERVAL_SECONDS = 3
ALERT_CHECK_INTERVAL_SECONDS = 1.5
REQUEST_TIMEOUT_SECONDS = 10
ALERT_RESET_SECONDS = 5
COOKIE_REFRESH_INTERVAL_SECONDS = 1800
PAGE_TIMEOUT_MS = 20_000


class CookieManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cookie_header: str = ''
        self._last_refresh: float = 0.0

    def refresh(self) -> None:
        log('Refreshing Apple cookies...')
        cookies = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp('http://localhost:9222')
            context = browser.new_context()
            page = context.new_page()

            product_url = f'{APPLE_LOCALE_BASE}/{APPLE_PRODUCT_PATH}'
            bag_status_url_fragment = f'{APPLE_LOCALE_BASE}/{APPLE_BAG_STATUS_PATH}'

            try:
                try:
                    page.goto(product_url, wait_until='networkidle', timeout=PAGE_TIMEOUT_MS)
                    time.sleep(1)
                    page.click('#root > div.rf-bfe > div.rf-bfe-selectionarea > div.rf-bfe-step.rf-bfe-first-step.rf-bfe-focused-step.rf-bfe-tradeup-fullwidth > div.row > div.rf-bfe-tradeup-column-left > div > div > div > div:nth-child(3)', timeout=PAGE_TIMEOUT_MS)
                except PlaywrightTimeoutError:
                    page.goto(product_url, wait_until='domcontentloaded', timeout=PAGE_TIMEOUT_MS)

                # with suppress(PlaywrightTimeoutError):
                #     page.wait_for_event(
                #         'response',
                #         lambda response: bag_status_url_fragment in response.url,
                #         timeout=PAGE_TIMEOUT_MS,
                #     )

                cookies = context.cookies()
            finally:
                context.close()
                browser.close()

        cookie_pairs = [
            f"{cookie['name']}={cookie['value']}"
            for cookie in cookies
            if 'apple.com' in cookie.get('domain', '')
        ]

        if not cookie_pairs:
            raise RuntimeError('No Apple cookies captured.')

        with self._lock:
            self._cookie_header = '; '.join(cookie_pairs)
            self._last_refresh = time.monotonic()
        log('Apple cookies refreshed.')

    def get_cookie_header(self) -> Optional[str]:
        with self._lock:
            return self._cookie_header or None

    def get_last_refresh(self) -> float:
        with self._lock:
            return self._last_refresh


cookie_manager = CookieManager()


def start_cookie_refresh_scheduler() -> None:
    def _loop() -> None:
        while True:
            time.sleep(COOKIE_REFRESH_INTERVAL_SECONDS)
            try:
                cookie_manager.refresh()
            except Exception as error:  # noqa: BLE001
                log(f'Cookie refresh failed: {error}')
            
    thread = threading.Thread(target=_loop, name='CookieRefreshThread', daemon=True)
    thread.start()


def log(message: str) -> None:
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    print(f'[{timestamp}] {message}')


def escape_markdown(text: str) -> str:
    special_characters = '_*[]()'
    for char in special_characters:
        text = text.replace(char, f'\\{char}')
    return text


def format_inventory_line(store: Dict[str, str]) -> str:
    store_name = escape_markdown(store['storeName'])
    inventory = escape_markdown(store.get('inventory', 'unknown'))
    return f'- {store_name} (inventory {inventory})'


def build_telegram_message(available_stores: Iterable[Dict[str, str]]) -> str:
    timestamp = escape_markdown(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    store_lines = [format_inventory_line(store) for store in available_stores]
    stores_block = '\n'.join(store_lines) if store_lines else '- No store data available'
    lines = [
        '*Apple Store Inventory Alert*',
        f'*Model*: {escape_markdown(MODEL_CODE)}',
        f'*Updated At*: {timestamp}',
        '*Available Stores:*',
        stores_block,
    ]
    return '\n'.join(lines)


def build_error_message(error: Exception) -> str:
    timestamp = escape_markdown(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    error_type = escape_markdown(type(error).__name__)
    error_text = escape_markdown(str(error) or 'Unknown error')
    lines = [
        '*Apple Store Monitor Error*',
        f'*Timestamp*: {timestamp}',
        f'*Exception Type*: {error_type}',
        f'*Error Details*: {error_text}',
    ]
    return '\n'.join(lines)


def send_telegram_alert(message: str) -> None:
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    topic_raw = os.getenv('TELEGRAM_TOPIC_ID')

    if not token or not chat_id:
        log('Telegram bot token or chat id not set; skipping notification.')
        return

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True,
    }

    if topic_raw:
        try:
            payload['message_thread_id'] = int(topic_raw)
        except ValueError:
            log(f'Invalid Telegram topic id: {topic_raw}; skipping notification.')
            return

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        target = f'chat_id={chat_id}'
        if topic_raw:
            target += f', topic_id={payload["message_thread_id"]}'
        log(f'Telegram notification sent -> {target}')
    except requests.RequestException as error:
        log(f'Telegram notification failed -> chat_id={chat_id}: {error}')


def fetch_store_status() -> List[Dict[str, str]]:
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-US,en;q=0.9',
        'Priority': 'u=1, i',
        'Referer': f'{APPLE_LOCALE_BASE}/{APPLE_PRODUCT_PATH}',
        'Sec-Ch-Ua': '"Not=A?Brand";v="24", "Chromium";v="140"',
        'Sec-Ch-Ua-Platform': '"macOS"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
        'X-Skip-Redirect': 'true',
        'x-aos-ui-fetch-call-1': 'hou24vudo1-mfwvzm0p',
    }

    cookie_header = cookie_manager.get_cookie_header()
    if cookie_header:
        headers['Cookie'] = cookie_header

    location_query = quote(LOCATION)
    url = (
        f'{APPLE_LOCALE_BASE}/shop/fulfillment-messages'
        f'?fae=true&pl=true&mts.0=regular&parts.0={MODEL_CODE}&location={location_query}'
    )

    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()

    return data['body']['content']['pickupMessage']['stores']


def monitor_inventory() -> None:
    log('Starting Apple Store inventory monitor...')
    attempt = 0
    alert_sent = False
    last_alert_time = 0.0

    try:
        cookie_manager.refresh()
    except Exception as error:  # noqa: BLE001
        log(f'Initial cookie refresh failed; continuing without cookies: {error}')

    start_cookie_refresh_scheduler()

    while True:
        try:
            if alert_sent and last_alert_time:
                elapsed = time.monotonic() - last_alert_time
                if elapsed >= ALERT_RESET_SECONDS:
                    alert_sent = False
                    last_alert_time = 0.0

            attempt += 1
            stores = fetch_store_status()
            available: List[Dict[str, str]] = []

            for store in stores:
                parts = store.get('partsAvailability', {}).get(MODEL_CODE, {})
                buyability = parts.get('buyability', {})
                raw_inventory = buyability.get('inventory')
                inventory = str(raw_inventory) if raw_inventory is not None else 'unknown'
                is_buyable = buyability.get('isBuyable', False)

                log(f"{store['storeName']} - inventory {inventory}")

                if is_buyable:
                    available.append({'storeName': store['storeName'], 'inventory': inventory})

            if available:
                if not alert_sent:
                    alert_sent = True
                    last_alert_time = time.monotonic()
                    message = build_telegram_message(available)
                    store_names = ', '.join(store['storeName'] for store in available)
                    log('In stock! ' + store_names)
                    send_telegram_alert(message)
            else:
                alert_sent = False
                last_alert_time = 0.0

        except Exception as error:  # noqa: BLE001
            log(f'Request error: {error}')
            try:
                send_telegram_alert(build_error_message(error))
            except Exception as notify_error:  # noqa: BLE001
                log(f'Failed to send error notification: {notify_error}')

        if alert_sent:
            time.sleep(ALERT_CHECK_INTERVAL_SECONDS)
        else:
            log(f'Retrying in {CHECK_INTERVAL_SECONDS} seconds (attempt {attempt + 1})...')
            time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == '__main__':
    monitor_inventory()
