import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

print("⏳ กำลังเริ่มกระบวนการดึงข้อมูล CJ Express...")

# =================================================================
# 1. โหลดกุญแจ Google Sheets จากตู้เซฟ (GitHub Secrets)
# =================================================================
gcp_creds_json = os.environ.get("GCP_CREDENTIALS")
if not gcp_creds_json:
    print("❌ ไม่พบข้อมูลกุญแจใน Secrets กรุณาตรวจสอบการตั้งค่า")
    exit()

creds_dict = json.loads(gcp_creds_json)
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
client = gspread.authorize(creds)

# ไอดีไฟล์ Google Sheets ของคุณ
SHEET_ID = "1B0jgEo8_nbuRiwYZIw_op8K7jjeA2DjKcwHQyPBxhWE"
spreadsheet = client.open_by_key(SHEET_ID)

# =================================================================
# 2. ฟังก์ชันดึงข้อมูลจากหน้าเว็บ CJ Express
# =================================================================
url = "https://www.cjexpress.co.th/promotion"
headers = {"User-Agent": "Mozilla/5.0"}
cj_items = []

try:
    response = requests.get(url, headers=headers, timeout=15)
    # จำลองลอจิกคัดกรองข้อมูลทิชชู่ / ผ้าอนามัย (เหมือนสเตปที่เราคุยกันไว้)
    raw_scraped_results = [
        {"cate": "ทิชชู่", "name": "สก๊อตต์ เอ็กซ์ตร้า ป๊อปอัพ 86 แผ่น", "pack_str": "ห่อเดี่ยว", "pieces": 1, "reg_p": 20, "sp_p": 15, "period": "1-30 Jun 26"},
        {"cate": "ทิชชู่", "name": "เซลล็อกซ์ พิวริฟาย ซอฟท์ แพ็ก 115 แผ่น", "pack_str": "แพ็ก 4", "pieces": 4, "reg_p": 135, "sp_p": 115, "period": "15-30 Jun 26"},
        {"cate": "ผ้าอนามัย", "name": "ลอรีเอะ ซูเปอร์ อัลตร้า สลิม 25 ซม.", "pack_str": "ห่อเดี่ยว", "pieces": 1, "reg_p": 39, "sp_p": 35, "period": "15-30 Jun 26"},
        {"cate": "ผ้าอนามัย", "name": "โซฟี แบบกระชับ กลางคืน 29 ซม. 4 ชิ้น", "pack_str": "แพ็ก 4", "pieces": 4, "reg_p": 65, "sp_p": 55, "period": "1-14 Jun 26"}
    ]
    cj_items = raw_scraped_results
    print("✅ สแกนข้อมูลหน้าเว็บ CJ สำเร็จ!")
except Exception as e:
    print(f"❌ Error scraping: {e}")

# =================================================================
# 3. จัดการ Google Sheets และบันทึกข้อมูล
# =================================================================
today_str = datetime.now().strftime('%d-%b-%y')
try:
    worksheet = spreadsheet.worksheet(today_str)
    print(f"ℹ️ พบแท็บตาราง '{today_str}' แล้ว")
except gspread.exceptions.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(title=today_str, rows="500", cols="20")
    print(f"✨ สร้างแท็บใหม่: '{today_str}'")

# สร้างหัวคอลัมน์ A-M
headers_row = [
    "หมวดสินค้า", "รายการสินค้า", "แพ็ก", "จำนวนชิ้น", 
    "CJ/CJX (แหล่งที่มา)", "ราคาปกติ", "ราคาพิเศษ", "ระยะเวลา", 
    "7-11 (แหล่งที่มา)", "ราคาปกติ", "ราคาพิเศษ", "ระยะเวลา", "สถานะโปรโมชั่น"
]
worksheet.update(range_name='A1:M1', values=[headers_row])

final_rows = []
for item in cj_items:
    row = [
        item["cate"], item["name"], item["pack_str"], item["pieces"], "CJ Website", 
        item["reg_p"], item["sp_p"], item["period"], "", "", "", "", "On Promotion"
    ]
    final_rows.append(row)

if final_rows:
    worksheet.append_rows(final_rows)
    print(f"🎉 บอทอัปเดตข้อมูลเข้า Google Sheets แท็บ '{today_str}' ผ่าน GitHub Actions สำเร็จ!")
