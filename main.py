import os  # 用來讀取環境變數（例如 GitHub Secrets）
import pandas as pd  # 資料表處理工具（DataFrame）
from datetime import datetime  # 取得今天日期（用於報告檔名）
import asyncio  # Python 非同步支援（Playwright 需要）
import json  # 用來讀取 service account JSON 字串
import telegram  # 發送 Telegram 訊息
import yagmail  # 發送 Email
import gspread  # 操作 Google Sheets
from google.oauth2.service_account import Credentials  # 用來登入 Google API
from playwright.async_api import async_playwright  # 非同步網頁爬蟲工具

async def scrape_tdm_with_playwright(pages=3):  # 定義一個非同步函式，預設爬3頁
    results = []  # 存放所有爬到的結果（清單）
    async with async_playwright() as p:  # 啟動 Playwright
        browser = await p.chromium.launch(headless=True)  # 開啟無頭瀏覽器（不顯示畫面）
        page = await browser.new_page()  # 新增一個網頁分頁

        for i in range(1, pages + 1):  # 迴圈跑第1至第3頁
            url = f"https://www.tdm.com.mo/zh-hant/news-list?type=image&category=27&page={i}"
            await page.goto(url)  # 開啟目標頁面
            await page.wait_for_timeout(2000)  # 等2秒確保載入完畢

            items = await page.query_selector_all('div.function-bar.px-0.py-3')  # 找出所有新聞區塊
            for item in items:
                title_el = await item.query_selector('h4.overflow-text-3')  # 抓標題元素
                date_el = await item.query_selector('div.date')  # 抓時間元素
                if title_el and date_el:  # 如果都抓得到
                    title = await title_el.inner_text()  # 讀取文字
                    date = await date_el.inner_text()
                    results.append({  # 加入結果
                        '標題': title.strip(),
                        '日期時間': date.strip()
                    })

        await browser.close()  # 關掉瀏覽器
    return pd.DataFrame(results)  # 回傳 DataFrame 結果表


async def main():
    df = await scrape_tdm_with_playwright(pages=3)  # 執行爬蟲
    today = datetime.today().strftime('%Y-%m-%d')  # 取得今天日期（YYYY-MM-DD）
    filename = f'tdm_image_news_{today}.csv'  # 設定報告檔名
    df.to_csv(filename, index=False, encoding='utf-8-sig')  # 儲存 CSV（含 BOM，避免 Excel 亂碼）



    credentials_dict = json.loads(os.environ["GDRIVE_CREDENTIAL_JSON"])  # 從環境變數讀 service account 資訊
    creds = Credentials.from_service_account_info(credentials_dict, scopes=[
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets',
    ])  # 設定權限
    gc = gspread.authorize(creds)  # 登入 gspread
    sh = gc.create(f"TDM報告 {today}")  # 建立新 Google 試算表
    worksheet = sh.get_worksheet(0) or sh.sheet1  # 取得第一個工作表
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())  # 貼上欄位與資料內容


    bot = telegram.Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])  # 建立 Telegram bot
    bot.send_message(chat_id=os.environ["TELEGRAM_CHAT_ID"],
                     text=f"📢 TDM 報告 {today} 已完成，並上傳 Google Drive。")  # 傳送訊息


    if os.environ.get("EMAIL_SENDER") and os.environ.get("EMAIL_RECIPIENT"):  # 有設 email 才執行
        yag = yagmail.SMTP(user=os.environ["EMAIL_SENDER"])  # 登入郵件寄件者
        yag.send(to=os.environ["EMAIL_RECIPIENT"],
                 subject=f"TDM 每日報告 {today}",
                 contents="報告已附上。",
                 attachments=filename)  # 寄送 email（含附件）


asyncio.run(main())  # 執行上面定義的 main() 程式
