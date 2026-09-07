import os
import json
import requests
from datetime import datetime
import pytz

# প্রোমো চ্যানেল ডেটা
PROMO_CHANNEL = {
    "name": "IreenTV Promo",
    "logo": "https://i.ibb.co.com/XkDv6gpS/ireenTV.png",
    "group": "Bangla",
    "url": "https://ireentvlive.pages.dev/promo/master.m3u8",
    "headers": {}
}

def get_dhaka_time():
    tz = pytz.timezone('Asia/Dhaka')
    return datetime.now(tz).strftime('%Y-%m-%d %I:%M:%S %p')

def clean_channel_data(ch):
    """বিভিন্ন সোর্স কী (Key) ফরম্যাট থেকে চ্যানেল ডেটা স্ট্যান্ডার্ডাইজ করা"""
    name = ch.get("name") or ch.get("channel_name") or ch.get("title") or "Unnamed Channel"
    logo = ch.get("logo") or ch.get("tvg_logo") or ch.get("image") or ""
    group = ch.get("group") or ch.get("category") or ch.get("group_title") or "Uncategorized"
    url = ch.get("url") or ch.get("stream_url") or ch.get("link") or ""
    
    # হেডার এক্সট্রাক্ট করা (User-Agent, Referer, Cookie ইত্যাদি)
    headers = ch.get("headers") or {}
    if "user_agent" in ch and "User-Agent" not in headers:
        headers["User-Agent"] = ch["user_agent"]
    if "referer" in ch and "Referer" not in headers:
        headers["Referer"] = ch["referer"]
    if "cookie" in ch and "Cookie" not in headers:
        headers["Cookie"] = ch["cookie"]

    return {
        "name": name,
        "logo": logo,
        "group": group,
        "url": url,
        "headers": headers
    }

def generate_m3u(playlist_name, channels):
    lines = [f"#EXTM3U name=\"{playlist_name}\""]
    
    for ch in channels:
        headers = ch.get("headers", {})
        
        # M3U এক্সটেন্ডেড ট্যাগ
        extinf_line = f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}'
        lines.append(extinf_line)
        
        # প্লেয়ার সাপোর্টের জন্য বিভিন্ন ফরম্যাটে হেডার যোগ
        for key, value in headers.items():
            lines.append(f'#EXTVLCOPT:http-{key.lower()}={value}')
            lines.append(f'#KODIPROP:inputstream.adaptive.manifest_headers={key}={value}')
            
        if headers:
            lines.append(f'#EXTHTTP:{json.dumps(headers)}')
            
        lines.append(ch["url"])
        
    return "\n".join(lines)

def process():
    sources_env = os.getenv("SOURCE_PLAYLISTS")
    if not sources_env:
        print("Error: SOURCE_PLAYLISTS secret is not set!")
        return

    try:
        sources = json.loads(sources_env)
    except Exception as e:
        print(f"Error parsing SOURCE_PLAYLISTS JSON: {e}")
        return

    for playlist_name, source_url in sources.items():
        print(f"Processing: {playlist_name}...")
        try:
            res = requests.get(source_url, timeout=30)
            res.raise_for_status()
            data = res.json()
            
            raw_channels = []
            if isinstance(data, list):
                raw_channels = data
            elif isinstance(data, dict):
                raw_channels = data.get("channels") or data.get("data") or []

            # ক্রিয়েটর ডিটেইলস রিসেট করে প্রোমো চ্যানেল একদম শুরুতে (Index 0) বসানো
            processed_channels = [PROMO_CHANNEL]
            for item in raw_channels:
                processed_channels.append(clean_channel_data(item))

            # ১. আপনার কাস্টম JSON ফরম্যাট
            custom_json = {
                "playlist_name": playlist_name,
                "developer": "MD ANAMUL HOQUE",
                "telegram": "https://t.me/ireentv",
                "website": "https://anamul.pages.dev",
                "channels_amount": len(processed_channels),
                "last_update": get_dhaka_time(),
                "channels": processed_channels
            }

            # ফাইলের নাম ঠিক করা (যেমন: Sports Live -> sports_live)
            safe_name = playlist_name.lower().replace(" ", "_")

            # সরাসরি রুটে JSON সেভ
            with open(f"{safe_name}.json", "w", encoding="utf-8") as f:
                json.dump(custom_json, f, indent=4, ensure_ascii=False)

            # সরাসরি রুটে M3U সেভ
            m3u_content = generate_m3u(playlist_name, processed_channels)
            with open(f"{safe_name}.m3u", "w", encoding="utf-8") as f:
                f.write(m3u_content)

            print(f"Generated directly to root: {safe_name}.json & {safe_name}.m3u")

        except Exception as err:
            print(f"Failed to process {playlist_name}: {err}")

if __name__ == "__main__":
    process()
