import os
import pandas as pd
from datetime import datetime
import asyncio
import json
import telegram
import gspread
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright

# --- 爬蟲邏輯 ---
async def scrape_tdm_with_playwright(pages=3):
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for i in range(1, pages + 1):
            url = f"https://www.tdm.com.mo/zh-hant/news-list?type=image&category=27&page={i}"
            await page.goto(url)
            await page.wait_for_timeout(2000)

            items = await page.query_selector_all('div.function-bar.px-0.py-3')
            for item in items:
                title_el = await item.query_selector('h4.overflow-text-3')
                date_el = await item.query_selector('div.date')
                if title_el and date_el:
                    title = await title_el.inner_text()
                    date = await date_el.inner_text()
                    results.append({
                        '標題': title.strip(),
                        '日期時間': date.strip()
                    })

        await browser.close()
    return pd.DataFrame(results)

# --- 主程式 ---
async def main():
    df = await scrape_tdm_with_playwright(pages=3)
    today = datetime.today().strftime('%Y-%m-%d')
    filename = f'tdm_image_news_{today}.csv'
    df.to_csv(filename, index=False, encoding='utf-8-sig')

    # --- Google Drive 上傳 ---
    credentials_dict = json.loads(os.environ["GDRIVE_CREDENTIAL_JSON"])
    creds = Credentials.from_service_account_info(credentials_dict, scopes=[
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets',
    ])
    gc = gspread.authorize(creds)
    sh = gc.create(f"TDM報告 {today}")
    worksheet = sh.get_worksheet(0) or sh.sheet1
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

    # --- Telegram 通知 ---
    bot = telegram.Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    bot.send_message(chat_id=os.environ["TELEGRAM_CHAT_ID"],
                     text=f"📢 TDM 報告 {today} 已完成，並上傳 Google Drive。")

asyncio.run(main())
