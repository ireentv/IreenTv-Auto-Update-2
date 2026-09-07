import os
import json
import re
from datetime import datetime, timezone
import requests
from playwright.sync_api import sync_playwright

# ==========================================
# 1. CONFIGURATION (READ FROM SECRETS)
# ==========================================
SOURCE_JSON_URL = os.environ.get("SOURCE_JSON_URL")
SPOOF_IP = os.environ.get("SPOOF_IP", "")
STREAM_ORIGIN = os.environ.get("STREAM_ORIGIN", "")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"

# Fixed Metadata Info
DEVELOPER = "MD ANAMUL HOQUE"
TELEGRAM = "https://t.me/ireentv"
WEBSITE = "https://anamul.pages.dev"

if not SOURCE_JSON_URL:
    raise ValueError("Error: SOURCE_JSON_URL secret is not set!")

HEADERS = {
    "Accept": "application/json",
    "Origin": STREAM_ORIGIN,
    "Referer": f"{STREAM_ORIGIN}/" if STREAM_ORIGIN else "",
    "User-Agent": USER_AGENT
}

# ==========================================
# 2. PLAYLIST & JSON GENERATOR
# ==========================================
def build_channel_playlist():
    print("[*] Fetching Source JSON Playlist...")
    try:
        resp = requests.get(SOURCE_JSON_URL, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"[-] Failed to fetch JSON. HTTP Status: {resp.status_code}")
            return
        
        data = resp.json()
        
        # সোর্স JSON থেকে ডাইনামিকভাবে প্লেলিস্টের নাম নেওয়া
        if isinstance(data, dict):
            playlist_name = data.get("playlist_name", data.get("name", "Custom_Playlist"))
            channels = data.get("channels", data.get("data", []))
        elif isinstance(data, list):
            playlist_name = "Custom_Playlist"
            channels = data
        else:
            print("[-] Invalid JSON structure.")
            return

        print(f"[+] Loaded Playlist: '{playlist_name}' with {len(channels)} channels.")
    except Exception as e:
        print(f"[-] Error fetching source JSON: {e}")
        return

    # ফাইলের নামের জন্য নিরাপদ স্ট্রিং তৈরি (উদা: 'BD Sports HD' -> 'BD_Sports_HD')
    safe_filename = re.sub(r'[^a-zA-Z0-9_-]', '_', playlist_name.strip()).strip('_')
    if not safe_filename:
        safe_filename = "Live_Channels"

    print("[*] Starting Playwright Browser (Blitz Mode)...")
    
    collected_channels = []
    channel_id = 1
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, 
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-web-security']
        )
        
        context = browser.new_context(
            user_agent=USER_AGENT,
            extra_http_headers={
                "Referer": f"{STREAM_ORIGIN}/" if STREAM_ORIGIN else "",
                "Origin": STREAM_ORIGIN
            }
        )
        
        page = context.new_page()
        
        # ব্লক অপ্রয়োজনীয় মিডিয়া / ফন্ট / ইমেজ দ্রুত লোডের জন্য
        page.route("**/*", lambda route: 
            route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] 
            else route.continue_()
        )
        
        for ch in channels:
            if "status" in ch and ch.get("status") != "online":
                continue
                
            ch_name = ch.get("name", "Unknown Channel")
            country_code = str(ch.get("code", "xx")).upper()
            logo = ch.get("image", ch.get("logo", ""))
            player_url = ch.get("url", ch.get("link", ""))
            group_title = ch.get("group", f"Live TV - {country_code}")
            
            if not player_url:
                continue
                
            print(f"-> Blitzing: [{country_code}] {ch_name}")
            
            try:
                # m3u8 লিংক ধরা
                with page.expect_request(re.compile(r"\.m3u8"), timeout=3500) as m3u8_req:
                    page.goto(player_url)
                
                final_url = m3u8_req.value.url
                stream_url_with_header = f"{final_url}|x-forwarded-for:{SPOOF_IP}" if SPOOF_IP else final_url
                
                collected_channels.append({
                    "id": channel_id,
                    "name": ch_name,
                    "tvg_id": f'{ch_name.replace(" ", "")}.{country_code}',
                    "logo": logo,
                    "group": group_title,
                    "stream_url": stream_url_with_header,
                    "raw_stream_url": final_url,
                    "referer": player_url,
                    "user_agent": USER_AGENT
                })
                
                channel_id += 1
                print(f"  [+] Snagged m3u8 stream successfully.")
                
            except Exception:
                print(f"  [-] Missed / Timeout. Moving on.")
                    
        browser.close()

    total_amount = len(collected_channels)
    last_update_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # ফাইলগুলোর ডাইনামিক নাম নির্ধারণ
    m3u_filename = f"{safe_filename}.m3u"
    json_filename = f"{safe_filename}.json"

    # ==========================================
    # 3. WRITE TO DYNAMIC .m3u
    # ==========================================
    print(f"[*] Writing {m3u_filename}...")
    with open(m3u_filename, "w", encoding="utf-8") as f_m3u:
        f_m3u.write("#EXTM3U\n")
        f_m3u.write(f"# Playlist Name: {playlist_name}\n")
        f_m3u.write(f"# Developer: {DEVELOPER}\n")
        f_m3u.write(f"# Telegram: {TELEGRAM}\n")
        f_m3u.write(f"# Website: {WEBSITE}\n")
        f_m3u.write(f"# Channels Amount: {total_amount}\n")
        f_m3u.write(f"# Last Update: {last_update_time}\n")
        f_m3u.write("# ==========================================\n\n")
        
        for item in collected_channels:
            f_m3u.write(f'#EXTINF:-1 tvg-chno="{item["id"]}" tvg-id="{item["tvg_id"]}" tvg-name="{item["name"]}" tvg-logo="{item["logo"]}" group-title="{item["group"]}",{item["name"]}\n')
            f_m3u.write(f'#EXTVLCOPT:http-referrer={item["referer"]}\n')
            f_m3u.write(f'#EXTVLCOPT:http-origin={item["referer"]}\n')
            f_m3u.write(f'#EXTVLCOPT:http-user-agent={item["user_agent"]}\n')
            f_m3u.write(f'{item["stream_url"]}\n\n')

    # ==========================================
    # 4. WRITE TO DYNAMIC .json
    # ==========================================
    print(f"[*] Writing {json_filename}...")
    final_json_data = {
        "info": {
            "playlist_name": playlist_name,
            "developer": DEVELOPER,
            "telegram": TELEGRAM,
            "website": WEBSITE,
            "channels_amount": total_amount,
            "last_update": last_update_time
        },
        "channels": collected_channels
    }

    with open(json_filename, "w", encoding="utf-8") as f_json:
        json.dump(final_json_data, f_json, indent=2, ensure_ascii=False)

    print(f"\n[+] Finished! Output Files: [{m3u_filename}, {json_filename}] | Channels: {total_amount}")

if __name__ == "__main__":
    build_channel_playlist()
