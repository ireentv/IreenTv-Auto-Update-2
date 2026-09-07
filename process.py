import os
import json
import requests
from datetime import datetime
import pytz

# প্রোমো চ্যানেল ডেটা (M3U এর ১ নম্বরে অ্যাড হওয়ার জন্য)
PROMO_CHANNEL = {
    "name": "IreenTV Promo",
    "logo": "https://i.ibb.co.com/XkDv6gpS/ireenTV.png",
    "group": "Bangla",
    "url": "https://ireentvlive.pages.dev/promo/master.m3u8",
    "headers": {}
}

DEVELOPER_INFO = {
    "developer": "MD ANAMUL HOQUE",
    "telegram": "https://t.me/ireentv",
    "website": "https://anamul.pages.dev"
}

def get_dhaka_time():
    tz = pytz.timezone('Asia/Dhaka')
    return datetime.now(tz).strftime('%Y-%m-%d %I:%M:%S %p')

def extract_headers(ch):
    """সোর্স জেসনে থাকা আলাদা আলাদা হেডারগুলো M3U-এর জন্য ফিল্টার করা"""
    headers = {}

    # যদি অবজেক্ট হিসেবে থাকে
    raw_headers = ch.get("headers")
    if isinstance(raw_headers, dict):
        for k, v in raw_headers.items():
            if v:
                headers[k.strip()] = str(v).strip()

    # যদি আলাদা আলাদা কি (Key) আকারে থাকে
    for key, value in ch.items():
        if not value or not isinstance(value, (str, int)):
            continue
        
        k_lower = key.lower().replace("-", "_").strip()
        val_str = str(value).strip()

        if k_lower in ["user_agent", "useragent", "http_user_agent"]:
            headers["User-Agent"] = val_str
        elif k_lower in ["referer", "referrer", "http_referrer"]:
            headers["Referer"] = val_str
        elif k_lower in ["cookie", "http_cookie"]:
            headers["Cookie"] = val_str
        elif k_lower in ["origin", "http_origin"]:
            headers["Origin"] = val_str
        elif k_lower in ["authorization", "auth"]:
            headers["Authorization"] = val_str

    return headers

def clean_channel_for_m3u(ch):
    name = ch.get("name") or ch.get("channel_name") or ch.get("title") or ch.get("tvg_name") or "Unnamed Channel"
    logo = ch.get("logo") or ch.get("tvg_logo") or ch.get("image") or ""
    group = ch.get("group") or ch.get("category") or ch.get("group_title") or "General"
    url = ch.get("url") or ch.get("stream_url") or ch.get("link") or ""
    headers = extract_headers(ch)

    return {
        "name": str(name).strip(),
        "logo": str(logo).strip(),
        "group": str(group).strip(),
        "url": str(url).strip(),
        "headers": headers
    }

def generate_m3u(playlist_name, channels, last_update):
    lines = [
        f'#EXTM3U url-tvg="" name="{playlist_name}"',
        '# =====================================================',
        f'# Playlist Name   : {playlist_name}',
        f'# Developer       : {DEVELOPER_INFO["developer"]}',
        f'# Telegram Channel: {DEVELOPER_INFO["telegram"]}',
        f'# Website         : {DEVELOPER_INFO["website"]}',
        f'# Total Channels  : {len(channels)}',
        f'# Last Updated    : {last_update}',
        '# =====================================================\n'
    ]
    
    for ch in channels:
        headers = ch.get("headers", {})
        
        # EXTINF লাইন
        lines.append(f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="{ch["group"]}" tvg-name="{ch["name"]}",{ch["name"]}')
        
        # আলাদা আলাদা হেডার অপশন
        if "User-Agent" in headers:
            lines.append(f'#EXTVLCOPT:http-user-agent={headers["User-Agent"]}')
        if "Referer" in headers:
            lines.append(f'#EXTVLCOPT:http-referrer={headers["Referer"]}')
        if "Cookie" in headers:
            lines.append(f'#EXTVLCOPT:http-cookie={headers["Cookie"]}')
        if "Origin" in headers:
            lines.append(f'#EXTVLCOPT:http-origin={headers["Origin"]}')

        # অন্যান্য প্লেয়ারের সামঞ্জস্যতার জন্য
        if headers:
            kodi_headers = "&".join([f"{k}={v}" for k, v in headers.items()])
            lines.append(f'#KODIPROP:inputstream.adaptive.manifest_headers={kodi_headers}')
            lines.append(f'#KODIPROP:inputstream.adaptive.stream_headers={kodi_headers}')
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

    last_update_time = get_dhaka_time()

    for playlist_name, source_url in sources.items():
        print(f"Processing: {playlist_name}...")
        try:
            res = requests.get(source_url, timeout=30)
            res.raise_for_status()
            
            safe_name = playlist_name.lower().replace(" ", "_")

            # ১. সোর্স JSON ফাইলটি হুবহু (কোনো পরিবর্তন ছাড়া) রুট ডিরেক্টরিতে সেভ করা
            with open(f"{safe_name}.json", "w", encoding="utf-8") as f:
                f.write(res.text)

            # ২. JSON থেকে M3U বানানোর প্রক্রিয়া
            data = res.json()
            raw_channels = []
            if isinstance(data, list):
                raw_channels = data
            elif isinstance(data, dict):
                raw_channels = data.get("channels") or data.get("data") or data.get("streams") or []

            # M3U এর জন্য প্রোমো চ্যানেল শুরুতে রেখে চ্যানেল প্রসেস করা
            m3u_channels = [PROMO_CHANNEL]
            for item in raw_channels:
                clean_ch = clean_channel_for_m3u(item)
                if clean_ch["url"]:
                    m3u_channels.append(clean_ch)

            # M3U ফাইলটি পার্সোনাল ডিটেইলস ও হেডারসহ সরাসরি রুটে সেভ করা
            m3u_content = generate_m3u(playlist_name, m3u_channels, last_update_time)
            with open(f"{safe_name}.m3u", "w", encoding="utf-8") as f:
                f.write(m3u_content)

            print(f"Successfully saved original {safe_name}.json and generated {safe_name}.m3u")

        except Exception as err:
            print(f"Failed to process {playlist_name}: {err}")

if __name__ == "__main__":
    process()
