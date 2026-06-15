import os
import json
import requests
import io
from PIL import Image
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import google.generativeai as genai
from apify_client import ApifyClient

print("🚀 เริ่มระบบ Daily Price Bot (Web & Facebook Edition)...")

# =================================================================
# 1. โหลดกุญแจทั้งหมด
# =================================================================
gcp_creds_json = os.environ.get("GCP_CREDENTIALS")
gemini_key = os.environ.get("GEMINI_API_KEY")
apify_token = os.environ.get("APIFY_API_TOKEN")

# ตั้งค่า Google Sheets
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(gcp_creds_json), ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
client = gspread.authorize(creds)
spreadsheet = client.open_by_key("1B0jgEo8_nbuRiwYZIw_op8K7jjeA2DjKcwHQyPBxhWE")

# ตั้งค่า Gemini AI และ Apify
genai.configure(api_key=gemini_key)
model = genai.GenerativeModel('gemini-1.5-flash')
apify = ApifyClient(apify_token)

final_data = [] # ตะกร้าเก็บข้อมูลทั้งหมด

# =================================================================
# 2. ฟังก์ชัน AI อ่านข้อมูล (ใช้ได้ทั้งข้อความและรูปภาพ)
# =================================================================
def analyze_with_ai(prompt_text, image_obj=None):
    prompt = f"""
    วิเคราะห์ข้อมูลโปรโมชั่นต่อไปนี้ หาเฉพาะสินค้าหมวด "ทิชชู่" และ "ผ้าอนามัย" 
    แปลงเป็น JSON Array (มี key: cate, name, pack_str, pieces, reg_p, sp_p, period)
    - pieces ต้องเป็นตัวเลข
    - ถ้าไม่เจอราคาปกติให้ใส่ "-"
    - ตอบกลับแค่โค้ด JSON เท่านั้น ห้ามมีข้อความอื่น
    ข้อมูล: {prompt_text[:10000]}
    """
    try:
        if image_obj:
            response = model.generate_content([prompt, image_obj])
        else:
            response = model.generate_content(prompt)
            
        result = response.text.strip()
        if result.startswith("
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1
3. กด **Commit changes...** 2 ครั้ง เพื่อเซฟครับ

---

### 🚀 ถึงเวลากดปุ่มรันดูผลงานระดับ Masterpiece!

เข้าไปที่แท็บ **Actions** ทางด้านบน > เลือก **Daily Price Bot** > กดปุ่ม **Run workflow** ได้เลยครับ!

*(หมายเหตุ: รอบนี้อาจจะใช้เวลาหมุนโหลดนานกว่าปกติประมาณ 1-2 นาทีนะครับ เพราะบอทต้องส่งลูกน้อง Apify วิ่งไปเปิดเพจ Facebook ดูดรูป แล้วส่งรูปกลับมาให้ AI นั่งเพ่งอ่านราคาครับ)*

เมื่อขึ้น Success แล้ว ลองเข้าไปดูใน Google Sheets ได้เลยครับ คุณจะเห็นว่าระบบได้ทำการแยกราคาของ CJ ไว้ฝั่งซ้าย และราคาของ 7-11 ไว้ฝั่งขวาให้อัตโนมัติตามแหล่งที่มาเลยครับ 

หากระบบทำงานผ่านฉลุย ยินดีต้อนรับสู่โลกของ Automation แบบเต็มตัวครับ! 🥳 ผลลัพธ์ออกมาเป็นยังไง หรือมีตรงไหนอยากให้ผมปรับแต่งฟอร์แมตเพิ่ม แจ้งมาได้เสมอเลยนะครับ
