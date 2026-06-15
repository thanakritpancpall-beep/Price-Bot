import os
import json
import requests
import io
from PIL import Image
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import google.generativeai as genai
from apify_client import ApifyClient

# ตั้งค่า Configuration
GCP_CREDS = json.loads(os.environ.get("GCP_CREDENTIALS"))
SHEET_ID = "1B0jgEo8_nbuRiwYZIw_op8K7jjeA2DjKcwHQyPBxhWE"
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
apify = ApifyClient(os.environ.get("APIFY_API_TOKEN"))

def send_line_notification(message):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if token and user_id:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        payload = {"to": user_id, "messages": [{"type": "text", "text": message}]}
        requests.post(url, headers=headers, json=payload)

def analyze_with_ai(data_str, img_obj=None):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = """วิเคราะห์ข้อมูลโปรโมชั่น หาเฉพาะ ทิชชู่ และ ผ้าอนามัย ส่งเป็น JSON Array 
    (keys: cate, name, pack_str, pieces, reg_p, sp_p, period). 
    ตอบแค่ JSON เท่านั้น ห้ามมีข้อความอื่น."""
    try:
        if img_obj: response = model.generate_content([prompt, img_obj])
        else: response = model.generate_content(prompt + f"\nข้อมูล: {data_str}")
        res = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(res)
    except: return []

print("🚀 เริ่มระบบดึงข้อมูลแบบ Ultimate Edition...")
final_data = []

# 1. ดึงจากเว็บ CJ
try:
    res = requests.get("https://www.cjexpress.co.th/promotion", timeout=10)
    data = BeautifulSoup(res.text, 'html.parser').get_text()
    for item in analyze_with_ai(data):
        item["source"] = "CJ Website"
        final_data.append(item)
    print(f"✅ ดึงเว็บ CJ สำเร็จ")
except Exception as e: print(f"❌ เว็บ CJ พลาด: {e}")

# 2. ดึงจาก Facebook
print("📱 เริ่มสแกน Facebook...")
try:
    run = apify.actor("apify/facebook-posts-scraper").call(run_input={
        "startUrls": [{"url": "https://www.facebook.com/CJMORETH"}, {"url": "https://www.facebook.com/7ElevenThailand"}],
        "resultsLimit": 80
    })
    for post in apify.dataset(run["defaultDatasetId"]).iterate_items():
        if (datetime.now() - datetime.strptime(post.get("time", "2020-01-01")[:10], "%Y-%m-%d")).days <= 28:
            img = None
            if post.get("media"):
                img = Image.open(io.BytesIO(requests.get(post["media"][0]["url"]).content))
            for item in analyze_with_ai(post.get("text", ""), img):
                item["source"] = post.get("pageName", "FB")
                final_data.append(item)
    print("✅ สแกน Facebook สำเร็จ")
except Exception as e: print(f"❌ Facebook พลาด: {e}")

# 3. บันทึกลง Sheets
if final_data:
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(GCP_CREDS, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))
    sheet = client.open_by_key(SHEET_ID).worksheet(datetime.now().strftime('%d-%b-%y'))
    for item in final_data:
        sheet.append_row([item.get("cate"), item.get("name"), item.get("pack_str"), item.get("pieces"), item["source"], item.get("reg_p"), item.get("sp_p"), item.get("period")])
    send_line_notification(f"✅ อัปเดตราคาคู่แข่งสำเร็จ! พบ {len(final_data)} รายการ")
else:
    print("⚠️ ไม่พบข้อมูลใหม่")
