import time
import requests
import random
import os
import re
import json
import websocket
from bs4 import BeautifulSoup

# =========================
# TELEGRAM AYARLARI
# =========================
TOKEN = "8034819966:AAFOdxxf0gHYkI6z_4fapDzMWjto_DKkiJk"
CHAT_ID = "-1002525404192"

# =========================
# 1. room_id ÇEKME
# =========================
def get_room_id(username):
    url = f"https://www.tiktok.com/@{username}/live"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        html = response.text
        match = re.search(r'"roomId":"(\d+)"', html)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        print(f"❌ room_id hatası: {e}")
        return None

# =========================
# 2. HTML YÖNTEMİ (sever1-b5fd)
# =========================
def get_live_data_html(room_id):
    url = f"https://sever1-b5fd.onrender.com/?time_id={room_id}"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tiktok_id = soup.find(id="tikTokName").text if soup.find(id="tikTokName") else "Bilinmiyor"
        view_count = soup.find(id="viewCount").text if soup.find(id="viewCount") else "0"
        diamond_people = soup.find(id="diamondPeople").text if soup.find(id="diamondPeople") else "0/0"
        country_flag = soup.find(id="countryFlag").text if soup.find(id="countryFlag") else "XX"
        
        try:
            people_count = int(diamond_people.split('/')[1])
        except:
            people_count = 0
            
        return {
            'tiktok_id': tiktok_id,
            'view': view_count,
            'diamond_count': diamond_people,
            'country_code': country_flag,
            'people_count': people_count,
            'source': 'HTML'
        }
    except Exception as e:
        print(f"❌ HTML hatası: {e}")
        return None

# =========================
# 3. WEBSOCKET YÖNTEMİ (realtime-67lx)
# =========================
def get_live_data_websocket(room_id):
    ws_url = f"wss://realtime-67lx.onrender.com/?time_id={room_id}"
    try:
        ws = websocket.create_connection(ws_url, timeout=5)
        result = ws.recv()
        ws.close()
        data = json.loads(result)
        # WebSocket verisinde people_count yok, view var
        data['people_count'] = int(data.get('view', 0))
        data['source'] = 'WebSocket'
        return data
    except Exception as e:
        print(f"❌ WebSocket hatası: {e}")
        return None

# =========================
# 4. BİRLEŞTİRİLMİŞ YÖNTEM (ÖNCE HTML, OLMAZSA WEBSOCKET)
# =========================
def get_live_data_fallback(room_id):
    # Önce HTML dene
    data = get_live_data_html(room_id)
    if data and data.get('people_count', 0) > 0:
        print(f"✅ HTML yöntemi başarılı (kişi: {data['people_count']})")
        return data
    
    # HTML çalışmazsa veya kişi sayısı 0 ise WebSocket dene
    print("🔄 HTML yöntemi başarısız, WebSocket deneniyor...")
    data = get_live_data_websocket(room_id)
    if data and data.get('people_count', 0) > 0:
        print(f"✅ WebSocket yöntemi başarılı (kişi: {data['people_count']})")
        return data
    
    print("❌ Her iki yöntem de başarısız veya yayın kapalı.")
    return None

# =========================
# 5. MESAJ GÖNDER
# =========================
def send_real_message(username, data):
    if not data:
        return

    # Gerçekten canlı yayın mı? (people_count > 0)
    if data.get('people_count', 0) == 0:
        print("⏭️ Yayın kapalı (0 kişi), atlanıyor.")
        return

    tiktok_id = data.get('tiktok_id', username)
    view_count = data.get('view', '0')
    diamond_count = data.get('diamond_count', '0/0')
    country_code = data.get('country_code', 'XX')
    source = data.get('source', 'Bilinmiyor')

    message = (
        f"<b>🔥 CANLI YAYIN BULUNDU</b>\n"
        f"─────────────────\n"
        f"<b>👤 TT-ID:</b> @{tiktok_id}\n"
        f"<b>📦 BOX:</b> {diamond_count} 🎁\n"
        f"<b>👀 İZLEYİCİ:</b> {view_count} Kişi\n"
        f"<b>🌍 ÜLKE:</b> {country_code}\n"
        f"<b>📡 KAYNAK:</b> {source}\n"
        f"─────────────────\n"
        f"<b>🔗 LİNK:</b> "
        f"<a href='https://www.tiktok.com/@{tiktok_id}/live'>YAYINA KATIL</a>\n"
        f"─────────────────"
    )

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        res = requests.post(url, data=data, timeout=15)
        if res.ok:
            print(f"✅ Gönderildi: @{tiktok_id} (İzleyici: {view_count})")
        else:
            print(f"❌ Telegram hatası: {res.text}")
    except Exception as e:
        print(f"❌ Gönderim hatası: {e}")

# =========================
# 6. ANA DÖNGÜ
# =========================
def run_bot():
    print("🔥 Çift yöntemli bot başlatıldı (HTML + WebSocket)...")
    while True:
        if not os.path.exists("tiktok_usernames.txt"):
            print("❌ 'tiktok_usernames.txt' bulunamadı!")
            break

        with open("tiktok_usernames.txt", "r", encoding="utf-8") as f:
            usernames = [line.strip().replace("@", "") for line in f.readlines() if line.strip()]

        for user in usernames:
            if user.isdigit() or len(user) < 3:
                continue

            print(f"🔎 @{user} taranıyor...")
            room_id = get_room_id(user)

            if not room_id:
                print(f"⏭️ @{user} canlı yayın yapmıyor.")
                continue

            print(f"✅ room_id: {room_id}")
            live_data = get_live_data_fallback(room_id)

            if live_data:
                send_real_message(user, live_data)
                bekleme = random.randint(5, 10)
                print(f"🕒 {bekleme} saniye bekleniyor...")
                time.sleep(bekleme)
            else:
                print(f"⚠️ Veri alınamadı, atlanıyor.")

        print("🔄 Liste bitti, yeniden başlıyor...")
        time.sleep(5)

# =========================
# 7. BAŞLAT
# =========================
if __name__ == "__main__":
    run_bot()
