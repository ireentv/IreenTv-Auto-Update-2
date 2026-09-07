import os
import json
import requests
from datetime import datetime
import pytz

# প্রোমো চ্যানেল ডেটা (M3U এর একদম শুরুতে ১ নম্বরে থাকবে)
PROMO_CHANNEL = {
    "name": "IreenTV Promo",
    "logo": "https://i.ibb.co.com/XkDv6gpS/ireenTV.png",
    "group": "Bangla",
    "url": "https://ireentvlive.pages.dev/promo/master.m3u8",
    "headers": {}
}

# আপনার পার্সোনাল ডিটেইলস
DEVELOPER_INFO = {
    "developer": "MD ANAMUL HOQUE",
    "telegram": "https://t.me/ireentv",
    "website": "https://anamul.pages.dev"
}

def get_dhaka_time():
    tz = pytz.timezone('Asia/Dhaka')
    return datetime.now(tz).strftime('%Y-%m-%d %I:%M:%S %p')

def extract_logo(ch):
    """
    জেসনে লোগো যে নামেই থাকুক না কেন (logo, tvg-logo, stream_icon, icon ইত্যাদি), 
    তা সঠিকভাবে খুঁজে বের করা
    """
    # ১. সাধারণ কী-গুলোর লিস্ট
    possible_keys = [
        "tvg-logo", "tvg_logo", "tvgLogo", "logo", "logo_url", "logoUrl",
        "stream_icon", "icon", "image", "img", "poster", "thumbnail",
        "channel_logo", "tvg_image", "picture", "cover"
    ]
    for key in possible_keys:
        val = ch.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()

    # ২. কেস-ইনসেনসিটিভ চেক (যদি কী-এর নাম ছোট-বড় হাতের অক্ষরের হয়)
    for k, v in ch.items():
        k_lower = k.lower().replace("-", "_").strip()
        if any(term in k_lower for term in ["logo", "icon", "poster", "thumb", "image"]):
            if v and isinstance(v, str) and (v.startswith("http://") or v.startswith("https://")):
                return v.strip()
                
    return ""

def extract_name(ch):
    possible_keys = ["name", "channel_name", "title", "tvg_name", "tvg-name", "stream_name", "channelName"]
    for key in possible_keys:
        val = ch.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return "Unnamed Channel"

def extract_group(ch):
    possible_keys = ["group", "group_title", "group-title", "category", "category_name", "genre", "groupTitle"]
    for key in possible_keys:
        val = ch.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return "General"

def extract_url(ch):
    possible_keys = ["url", "stream_url", "link", "stream_link", "streamUrl", "src"]
    for key in possible_keys:
        val = ch.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return ""

def extract_headers(ch):
    headers = {}

    # যদি অবজেক্ট আকারে থাকে
    raw_headers = ch.get("headers")
    if isinstance(raw_headers, dict):
        for k, v in raw_headers.items():
            if v:
                headers[k.strip()] = str(v).strip()

    # যদি আলাদা আলাদা ফিল্ড আকারে থাকে
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
    return {
        "name": extract_name(ch),
        "logo": extract_logo(ch),
        "group": extract_group(ch),
        "url": extract_url(ch),
        "headers": extract_headers(ch)
    }

def generate_m3u(playlist_name, channels, last_update):
    lines = [
        f'#EXTM3U name="{playlist_name}"',
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
        
        # ১. EXTINF লাইন (টিভি লোগো নিখুঁতভাবে বসানো হয়েছে)
        lines.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}')
        
        # ২. User-Agent
        if "User-Agent" in headers and headers["User-Agent"]:
            lines.append(f'#EXTVLCOPT:http-user-agent={headers["User-Agent"]}')
            
        # ৩. Referer
        if "Referer" in headers and headers["Referer"]:
            lines.append(f'#EXTVLCOPT:http-referrer={headers["Referer"]}')
            
        # ৪. Cookie
        if "Cookie" in headers and headers["Cookie"]:
            lines.append(f'#EXTVLCOPT:http-cookie={headers["Cookie"]}')
            
        # ৫. EXTHTTP (Origin ও অন্যান্য কাস্টম হেডার)
        exthttp_data = {}
        if "Origin" in headers and headers["Origin"]:
            exthttp_data["Origin"] = headers["Origin"]
        
        for k, v in headers.items():
            if k not in ["User-Agent", "Referer", "Cookie", "Origin"] and v:
                exthttp_data[k] = v
                
        if exthttp_data:
            lines.append(f'#EXTHTTP:{json.dumps(exthttp_data)}')
            
        # ৬. স্ট্রিম URL
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

            # ১. অরিজিনাল সোর্স জেসন সরাসরি রুটে সেভ
            with open(f"{safe_name}.json", "w", encoding="utf-8") as f:
                f.write(res.text)

            # ২. JSON ডেটা পার্স করা
            data = res.json()
            raw_channels = []
            if isinstance(data, list):
                raw_channels = data
            elif isinstance(data, dict):
                raw_channels = data.get("channels") or data.get("data") or data.get("streams") or []

            # প্রমো চ্যানেল প্রথমে যুক্ত করা
            m3u_channels = [PROMO_CHANNEL]
            for item in raw_channels:
                clean_ch = clean_channel_for_m3u(item)
                if clean_ch["url"]:
                    m3u_channels.append(clean_ch)

            # ৩. লোগোসহ M3U ফাইল রুটে সেভ
            m3u_content = generate_m3u(playlist_name, m3u_channels, last_update_time)
            with open(f"{safe_name}.m3u", "w", encoding="utf-8") as f:
                f.write(m3u_content)

            print(f"Done: {safe_name}.json & {safe_name}.m3u saved with TV Logo.")

        except Exception as err:
            print(f"Failed to process {playlist_name}: {err}")

if __name__ == "__main__":
    process()
