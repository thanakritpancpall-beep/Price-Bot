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

# 1. SETUP
print("🚀 เริ่มระบบ Daily Price Bot - Ultimate Edition")
GCP_CREDS = json.loads(os.environ.get("GCP_CREDENTIALS"))
SHEET_ID = "1B0jgEo8_nbuRiwYZIw_op8K7jjeA2DjKcwHQyPBxhWE"
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
apify = ApifyClient(os.environ.get("APIFY_API_TOKEN"))

# 2. AI ANALYZER
def analyze_with_ai(content, img_obj=None):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = """คุณคือผู้เชี่ยวชาญค้าปลีก วิเคราะห์ข้อความ/รูปภาพนี้ 
    หาสินค้า ทิชชู่ และ ผ้าอนามัย เท่านั้น
    ตอบกลับเป็น JSON Array format เท่านั้น (keys: cate, name, pack_str, pieces, reg_p, sp_p, period).
    ห้ามมีข้อความอื่นนอกจาก JSON
    """
    try:
        response = model.generate_content([prompt, content] if not img_obj else [prompt, content, img_obj])
        res = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(res)
    except Exception as e:
        print(f"⚠️ AI Error: {e}")
        return []

# 3. SCRAPING
final_data = []

# ดึงเว็บ CJ
try:
    res = requests.get("https://www.cjexpress.co.th/promotion", timeout=15)
    cj_data = analyze_with_ai(BeautifulSoup(res.text, 'html.parser').get_text())
    for item in cj_data: 
        item["source"] = "CJ Website"
        final_data.append(item)
except: pass

# ดึง Facebook
try:
    run = apify.actor("apify/facebook-posts-scraper").call(run_input={
        "startUrls": [{"url": "https://www.facebook.com/CJMORETH"}, {"url": "https://www.facebook.com/7ElevenThailand"}],
        "resultsLimit": 50
    })
    for post in apify.dataset(run["defaultDatasetId"]).iterate_items():
        if (datetime.now() - datetime.strptime(post.get("time", "2020-01-01")[:10], "%Y-%m-%d")).days <= 28:
            img = None
            if post.get("media"):
                try: img = Image.open(io.BytesIO(requests.get(post["media"][0]["url"]).content))
                except: pass
            for item in analyze_with_ai(post.get("text", ""), img):
                item["source"] = post.get("pageName", "FB")
                final_data.append(item)
except Exception as e: print(f"❌ Facebook Scrape Error: {e}")

# 4. SAVE TO SHEETS
if final_data:
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(GCP_CREDS, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))
    sheet = client.open_by_key(SHEET_ID).worksheet(datetime.now().strftime('%d-%b-%y'))
    for item in final_data:
        sheet.append_row([item.get("cate"), item.get("name"), item.get("pack_str"), item.get("pieces"), item["source"], item.get("reg_p"), item.get("sp_p"), item.get("period")])
    
    # 5. LINE NOTIFY
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if token and user_id:
        requests.post("https://api.line.me/v2/bot/message/push", 
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            json={"to": user_id, "messages": [{"type": "text", "text": f"✅ อัปเดตราคาคู่แข่งแล้ว พบ {len(final_data)} รายการ"}]})
    print("✅ ทำงานสำเร็จ!")
else:
    print("⚠️ ไม่พบข้อมูลใหม่ในรอบนี้")
