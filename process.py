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

DEVELOPER_INFO = {
    "developer": "MD ANAMUL HOQUE",
    "telegram": "https://t.me/ireentv",
    "website": "https://anamul.pages.dev"
}

def get_dhaka_time():
    tz = pytz.timezone('Asia/Dhaka')
    return datetime.now(tz).strftime('%Y-%m-%d %I:%M:%S %p')

def extract_headers(ch):
    """
    সোর্স থেকে User-Agent, Referer, Cookie সহ সব হেডার 
    আলাদা আলাদা থাকলে বা অবজেক্টে থাকলে তা নিখুঁতভাবে সংগ্রহ করা
    """
    headers = {}

    # যদি সোর্সে আগে থেকেই 'headers' অবজেক্ট থাকে
    raw_headers = ch.get("headers")
    if isinstance(raw_headers, dict):
        for k, v in raw_headers.items():
            if v:
                headers[k.strip()] = str(v).strip()

    # সোর্সে আলাদা ফিল্ড হিসেবে থাকলে তা খুঁজে বের করা (Case-insensitive)
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

def clean_channel_data(ch):
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
    # M3U ফাইলের শুরুতে আপনার পার্সোনাল ডিটেইলস
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
        
        # আলাদা আলাদা হেডারের জন্য নির্দিষ্ট M3U অপশন
        if "User-Agent" in headers:
            lines.append(f'#EXTVLCOPT:http-user-agent={headers["User-Agent"]}')
        if "Referer" in headers:
            lines.append(f'#EXTVLCOPT:http-referrer={headers["Referer"]}')
        if "Cookie" in headers:
            lines.append(f'#EXTVLCOPT:http-cookie={headers["Cookie"]}')
        if "Origin" in headers:
            lines.append(f'#EXTVLCOPT:http-origin={headers["Origin"]}')

        # অন্যান্য সমস্ত প্লেয়ার (যেমন TiviMate, OTT Navigator, Kodi)-এর জন্য সাপোর্ট
        if headers:
            # Kodi / OTT Navigator হেডার প্রপস
            kodi_headers = "&".join([f"{k}={v}" for k, v in headers.items()])
            lines.append(f'#KODIPROP:inputstream.adaptive.manifest_headers={kodi_headers}')
            lines.append(f'#KODIPROP:inputstream.adaptive.stream_headers={kodi_headers}')
            # জেসন আকারে হেডার ট্যাগ
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
            data = res.json()
            
            raw_channels = []
            if isinstance(data, list):
                raw_channels = data
            elif isinstance(data, dict):
                raw_channels = data.get("channels") or data.get("data") or data.get("streams") or []

            # সোর্স থেকে ক্রিয়েটর ডিটেইলস বাদ দিয়ে শুধু চ্যানেল প্রসেস করা
            processed_channels = [PROMO_CHANNEL]  # শুরুতে ১ নম্বরে প্রোমো চ্যানেল
            for item in raw_channels:
                clean_ch = clean_channel_data(item)
                if clean_ch["url"]:  # যদি স্ট্রীম URL থাকে
                    processed_channels.append(clean_ch)

            # ১. আপনার কাস্টম JSON ফরম্যাট
            custom_json = {
                "playlist_name": playlist_name,
                "developer": DEVELOPER_INFO["developer"],
                "telegram": DEVELOPER_INFO["telegram"],
                "website": DEVELOPER_INFO["website"],
                "channels_amount": len(processed_channels),
                "last_update": last_update_time,
                "channels": processed_channels
            }

            safe_name = playlist_name.lower().replace(" ", "_")

            # সরাসরি রুটে JSON সেভ
            with open(f"{safe_name}.json", "w", encoding="utf-8") as f:
                json.dump(custom_json, f, indent=4, ensure_ascii=False)

            # ২. পার্সোনাল ডিটেইলস ও হেডারসহ সরাসরি রুটে M3U সেভ
            m3u_content = generate_m3u(playlist_name, processed_channels, last_update_time)
            with open(f"{safe_name}.m3u", "w", encoding="utf-8") as f:
                f.write(m3u_content)

            print(f"Successfully generated: {safe_name}.json & {safe_name}.m3u directly in root.")

        except Exception as err:
            print(f"Failed to process {playlist_name}: {err}")

if __name__ == "__main__":
    process()
