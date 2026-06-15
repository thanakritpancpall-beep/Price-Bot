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

print("🚀 เริ่มระบบ Daily Price Bot (28-Days Scan & Messaging API Edition)...")

# =================================================================
# 1. โหลดกุญแจทั้งหมด
# =================================================================
gcp_creds_json = os.environ.get("GCP_CREDENTIALS")
gemini_key = os.environ.get("GEMINI_API_KEY")
apify_token = os.environ.get("APIFY_API_TOKEN")
line_channel_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
line_user_id = os.environ.get("LINE_USER_ID")

# ตั้งค่า Google Sheets
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(gcp_creds_json), ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
client = gspread.authorize(creds)
spreadsheet = client.open_by_key("1B0jgEo8_nbuRiwYZIw_op8K7jjeA2DjKcwHQyPBxhWE")

# ตั้งค่า Gemini AI และ Apify
genai.configure(api_key=gemini_key)
model = genai.GenerativeModel('gemini-1.5-flash')
apify = ApifyClient(apify_token)

final_data = []

# =================================================================
# 2. ฟังก์ชัน AI อ่านข้อมูล
# =================================================================
def analyze_with_ai(prompt_text, image_obj=None):
    prompt = f"""
    จงสวมบทบาทเป็นผู้เชี่ยวชาญด้านข้อมูลค้าปลีก 
    วิเคราะห์ข้อมูลโปรโมชั่นต่อไปนี้ ค้นหาเฉพาะสินค้าที่อยู่ในหมวด "ทิชชู่" และ "ผ้าอนามัย" เท่านั้น
    
    🔍 คำที่เกี่ยวข้องกับ "ทิชชู่": ทิชชู่, กระดาษชำระ, กระดาษเช็ดหน้า, กระดาษอเนกประสงค์, กระดาษเปียก, คลีเน็กซ์ (Kleenex), สก๊อตต์ (Scott), เซลล็อกซ์ (Cellox), ซิลค์ (Zilk), คูแมะ (Kuma), ป๊อปอัพ, แบบม้วน, แบบแผ่น
    🔍 คำที่เกี่ยวข้องกับ "ผ้าอนามัย": ผ้าอนามัย, แผ่นอนามัย, โซฟี (Sofy), ลอรีเอะ (Laurier), เอลิส (Elis), แคร์ฟรี (Carefree), โมเดส (Modess), แบบมีปีก, กลางวัน, กลางคืน, ซึมซับ
    
    แปลงผลลัพธ์เป็น JSON Array (มี key ดังนี้):
    - cate: "ทิชชู่" หรือ "ผ้าอนามัย"
    - name: ชื่อรายการสินค้าและแบรนด์อย่างครบถ้วน
    - pack_str: รูปแบบแพ็กเกจ (เช่น แพ็ก 4, ห่อเดี่ยว, ม้วน)
    - pieces: จำนวนชิ้นหรือจำนวนม้วนทั้งหมด (ต้องเป็นตัวเลข int เท่านั้น ถ้าไม่ทราบให้คำนวณจากแพ็ก หรือใส่ 1)
    - reg_p: ราคาปกติ (เป็นตัวเลข ถ้าไม่พบใส่ "-")
    - sp_p: ราคาพิเศษ หรือราคาโปรโมชั่น (เป็นตัวเลข ถ้าไม่พบใส่ "-")
    - period: ระยะเวลาโปรโมชั่น (เช่น "1-30 Jun 26" ถ้าไม่พบให้ใส่ "-")
    
    ⚠️ ตอบกลับแค่โค้ด JSON เท่านั้น ห้ามมีข้อความอื่นอธิบาย
    ข้อมูล: {prompt_text[:10000]}
    """
    try:
        if image_obj:
            response = model.generate_content([prompt, image_obj])
        else:
            response = model.generate_content(prompt)
            
        result = response.text.strip()
        if result.startswith("```json"): 
            result = result[7:-3].strip()
        elif result.startswith("```"): 
            result = result[3:-3].strip()
        return json.loads(result)
    except Exception as e:
        print(f"❌ AI Analysis Error: {e}")
        return []

# =================================================================
# 3. สแกนเว็บไซต์ CJ Express
# =================================================================
print("\n🌐 [1/2] กำลังสแกนหน้าเว็บไซต์ CJ Express...")
try:
    res = requests.get("https://www.cjexpress.co.th/promotion", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    res.encoding = 'utf-8'
    text_data = BeautifulSoup(res.text, 'html.parser').get_text(separator=" ", strip=True)
    
    cj_web_items = analyze_with_ai(text_data)
    for item in cj_web_items:
        item["source"] = "CJ Website"
        final_data.append(item)
    print(f"✅ ดึงจาก CJ Web สำเร็จ พบ {len(cj_web_items)} รายการ")
except Exception as e:
    print(f"❌ CJ Web Error: {e}")

# =================================================================
# 4. สแกน Facebook (ดึงย้อนหลัง 28 วัน)
# =================================================================
print("\n📱 [2/2] กำลังสูบข้อมูล Facebook ย้อนหลัง 28 วัน (อาจใช้เวลา 3-5 นาที)...")
run_input = {
    "startUrls": [{"url": "https://www.facebook.com/CJMORETH"}, {"url": "https://www.facebook.com/7ElevenThailand"}],
    "resultsLimit": 80
}

try:
    run = apify.actor("apify/facebook-posts-scraper").call(run_input=run_input)
    dataset = apify.dataset(run["defaultDatasetId"]).iterate_items()
    
    fb_count = 0
    current_time = datetime.now()
    
    for post in dataset:
        post_time_str = post.get("time")
        if post_time_str:
            try:
                post_date = datetime.strptime(post_time_str[:10], "%Y-%m-%d")
                if (current_time - post_date).days > 28:
                    continue
            except Exception:
                pass
                
        page_name = post.get("pageName", "Unknown FB")
        caption = post.get("text", "")
        img_url = post.get("media", [{}])[0].get("url", "") if post.get("media") else ""
        
        keywords_check = ["โปร", "ลด", "ทิชชู่", "ผ้าอนามัย", "กระดาษ", "เซลล็อกซ์", "คลีเน็กซ์", "สก๊อตต์", "โซฟี", "ลอรีเอะ", "เอลิส", "1แถม1", "บาท"]
        has_keyword = any(k in caption for k in keywords_check)
        
        if img_url or has_keyword:
            source_tag = "CJ MORE FB" if "CJ" in page_name.upper() else "7-11 FB"
            
            img_obj = None
            if img_url:
                img_res = requests.get(img_url)
                img_obj = Image.open(io.BytesIO(img_res.content))
                
            fb_items = analyze_with_ai(caption, img_obj)
            for item in fb_items:
                item["source"] = source_tag
                final_data.append(item)
                fb_count += 1
                
    print(f"✅ สแกน Facebook สำเร็จ พบเป้าหมายเพิ่มเติม {fb_count} รายการ")
except Exception as e:
    print(f"❌ Facebook Scrape Error: {e}")

# =================================================================
# 5. จัดเรียงข้อมูลลง Google Sheets
# =================================================================
print(f"\n📊 กำลังนำข้อมูลทั้งหมด {len(final_data)} รายการ ลงตาราง...")
today_str = datetime.now().strftime('%d-%b-%y')

try:
    worksheet = spreadsheet.worksheet(today_str)
except gspread.exceptions.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(title=today_str, rows="500", cols="20")
    headers = ["หมวดสินค้า", "รายการสินค้า", "แพ็ก", "จำนวนชิ้น", "CJ/CJX (แหล่งที่มา)", "ราคาปกติ", "ราคาพิเศษ", "ระยะเวลา", "7-11 (แหล่งที่มา)", "ราคาปกติ", "ราคาพิเศษ", "ระยะเวลา", "สถานะโปรโมชั่น"]
    worksheet.update(range_name='A1:M1', values=[headers])

rows_to_insert = []
cj_count = 0
cp_count = 0

for item in final_data:
    if not isinstance(item, dict): continue
    
    source = item.get("source", "")
    is_cj = "CJ" in source
    is_cp = "7-11" in source
    
    if is_cj: cj_count += 1
    if is_cp: cp_count += 1

    row = [
        item.get("cate", ""), item.get("name", ""), item.get("pack_str", ""), item.get("pieces", ""),
        source if is_cj else "", item.get("reg_p", "") if is_cj else "", item.get("sp_p", "") if is_cj else "", item.get("period", "") if is_cj else "",
        source if is_cp else "", item.get("reg_p", "") if is_cp else "", item.get("sp_p", "") if is_cp else "", item.get("period", "") if is_cp else "",
        "On Promotion"
    ]
    rows_to_insert.append(row)

if rows_to_insert:
    worksheet.append_rows(rows_to_insert)
    print("🎉 อัปเดตข้อมูลลง Google Sheets สำเร็จ!")

# =================================================================
# 6. ส่งแจ้งเตือนรายงานเข้า LINE (ผ่าน Messaging API โฉมใหม่)
# =================================================================
if line_channel_token and line_user_id:
    print("📲 กำลังส่งรายงานสรุปเข้า LINE Messaging API...")
    message = f"📊 สรุปรายงานราคาสินค้าคู่แข่ง\nสแกนย้อนหลัง 28 วันล่าสุด\nประจำวันที่ {today_str}\n\n"
    message += f"พบโปรโมชั่น ทิชชู่/ผ้าอนามัย ทั้งหมด {len(final_data)} รายการ\n"
    message += f"🏪 จาก CJ Express: {cj_count} รายการ\n"
    message += f"🏪 จาก 7-Eleven: {cp_count} รายการ\n\n"
    message += f"🔗 ดูตารางฉบับเต็มคลิก:\nhttps://docs.google.com/spreadsheets/d/1B0jgEo8_nbuRiwYZIw_op8K7jjeA2DjKcwHQyPBxhWE"
    
    line_url = "https://api.line.me/v2/bot/message/push"
    line_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_channel_token}"
    }
    line_payload = {
        "to": line_user_id,
        "messages": [{"type": "text", "text": message}]
    }
    
    try:
        res = requests.post(line_url, headers=line_headers, json=line_payload)
        if res.status_code == 200:
            print("✅ ส่งแจ้งเตือน LINE ทะลุเข้ามือถือเรียบร้อยแล้ว!")
        else:
            print(f"❌ ส่งแจ้งเตือน LINE พลาด: {res.text}")
    except Exception as e:
        print(f"❌ Error ส่ง LINE: {e}")
