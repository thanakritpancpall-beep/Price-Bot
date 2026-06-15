import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import google.generativeai as genai

print("⏳ กำลังเริ่มกระบวนการดึงข้อมูล...")

# =================================================================
# 1. ตั้งค่า API และการเชื่อมต่อต่างๆ
# =================================================================
# ตั้งค่า Google Sheets
gcp_creds_json = os.environ.get("GCP_CREDENTIALS")
creds_dict = json.loads(gcp_creds_json)
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
client = gspread.authorize(creds)
SHEET_ID = "1B0jgEo8_nbuRiwYZIw_op8K7jjeA2DjKcwHQyPBxhWE"
spreadsheet = client.open_by_key(SHEET_ID)

# ตั้งค่า Gemini AI
gemini_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=gemini_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# =================================================================
# 2. ดึงข้อมูลดิบจากเว็บ CJ Express
# =================================================================
print("🕸️ กำลังสแกนหน้าเว็บไซต์ CJ Express...")
url = "https://www.cjexpress.co.th/promotion"
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(url, headers=headers, timeout=15)
response.encoding = 'utf-8'

# สกัดเฉพาะข้อความออกจาก HTML
soup = BeautifulSoup(response.text, 'html.parser')
raw_text = soup.get_text(separator=" ", strip=True)

# =================================================================
# 3. ส่งให้ AI ประมวลผลและคัดกรองข้อมูล (Prompt Engineering)
# =================================================================
print("🧠 กำลังส่งข้อมูลดิบให้ AI วิเคราะห์หา ทิชชู่ และ ผ้าอนามัย...")

prompt = f"""
จากข้อมูลข้อความโปรโมชั่นบนหน้าเว็บต่อไปนี้ (อาจจะมีโค้ดปนมาบ้าง ให้วิเคราะห์เฉพาะเนื้อหาที่เกี่ยวข้อง):
---
{raw_text[:15000]} 
---
หน้าที่ของคุณคือ: ค้นหาสินค้าที่อยู่ในหมวดหมู่ "ทิชชู่" และ "ผ้าอนามัย" เท่านั้น 
และแปลงข้อมูลให้อยู่ในรูปแบบ JSON Array โดยมี Key ดังนี้:
- "cate": หมวดสินค้า (ทิชชู่ หรือ ผ้าอนามัย)
- "name": ชื่อรายการสินค้า (พร้อมยี่ห้อและขนาด)
- "pack_str": แพ็กเกจ (เช่น ห่อเดี่ยว, แพ็ก 4) หากระบุไม่ได้ให้ใส่ "-"
- "pieces": จำนวนชิ้นทั้งหมด (เป็นตัวเลข int) หากระบุไม่ได้ให้ใส่ 1
- "reg_p": ราคาปกติ (เป็นตัวเลข หรือ - หากไม่พบ)
- "sp_p": ราคาพิเศษ (เป็นตัวเลข หรือ - หากไม่พบ)
- "period": ระยะเวลาโปรโมชั่น (เช่น "1-30 Jun 26") หากระบุไม่ได้ให้ใส่ "ตรวจสอบบนเว็บ"

ตอบกลับมาเป็นแค่โค้ด JSON เท่านั้น ห้ามมีข้อความอื่นอธิบาย
"""

# รับผลลัพธ์จาก AI
response_ai = model.generate_content(prompt)
ai_result = response_ai.text.strip()

# ลบสัญลักษณ์ Markdown ของ JSON ออกเพื่อให้ Python อ่านได้
if ai_result.startswith("```json"):
    ai_result = ai_result[7:-3].strip()
elif ai_result.startswith("```"):
    ai_result = ai_result[3:-3].strip()

# แปลงข้อความ JSON จาก AI เป็น ข้อมูล (List/Dictionary) ใน Python
cj_items = []
try:
    cj_items = json.loads(ai_result)
    print(f"✅ AI ประมวลผลสำเร็จ! พบสินค้าเป้าหมายจำนวน {len(cj_items)} รายการ")
except Exception as e:
    print(f"❌ เกิดข้อผิดพลาดในการแปลง JSON จาก AI: {e}")
    print("ผลลัพธ์จาก AI:", ai_result)

# =================================================================
# 4. บันทึกข้อมูลลง Google Sheets
# =================================================================
today_str = datetime.now().strftime('%d-%b-%y')
try:
    worksheet = spreadsheet.worksheet(today_str)
    print(f"ℹ️ พบแท็บ '{today_str}' แล้ว")
except gspread.exceptions.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(title=today_str, rows="500", cols="20")
    print(f"✨ สร้างแท็บใหม่: '{today_str}'")

# จัดหัวคอลัมน์ A-M
headers_row = [
    "หมวดสินค้า", "รายการสินค้า", "แพ็ก", "จำนวนชิ้น", 
    "CJ/CJX (แหล่งที่มา)", "ราคาปกติ", "ราคาพิเศษ", "ระยะเวลา", 
    "7-11 (แหล่งที่มา)", "ราคาปกติ", "ราคาพิเศษ", "ระยะเวลา", "สถานะโปรโมชั่น"
]
worksheet.update(range_name='A1:M1', values=[headers_row])

final_rows = []
for item in cj_items:
    row = [
        item.get("cate", ""), item.get("name", ""), item.get("pack_str", ""), item.get("pieces", ""), 
        "CJ Website", item.get("reg_p", ""), item.get("sp_p", ""), item.get("period", ""), 
        "", "", "", "", "On Promotion"
    ]
    final_rows.append(row)

if final_rows:
    # เพิ่มข้อมูลต่อท้ายลงในตาราง
    worksheet.append_rows(final_rows)
    print(f"🎉 บอทและ AI อัปเดตข้อมูลเข้า Google Sheets สำเร็จเรียบร้อยแล้ว!")
else:
    print("⚠️ วันนี้ไม่พบรายการสินค้าทิชชู่/ผ้าอนามัย หรือไม่มีข้อมูลถูกเพิ่มลงในชีท")
