import os
import json
import time
import re
import requests
from datetime import datetime
import pytz

# প্রোমো চ্যানেল ডেটা (JSON ও M3U উভয়ের ১ নম্বরে যুক্ত হবে)
PROMO_CHANNEL = {
    "name": "IreenTV Promo",
    "logo": "https://i.ibb.co.com/XkDv6gpS/ireenTV.png",
    "group": "Bangla",
    "url": "https://ireentvlive.pages.dev/promo/master.m3u8",
    "headers": {},
    "drm": {},
    "kodi_props": {}
}

# আপনার পার্সোনাল মেটাডেটা
DEVELOPER_INFO = {
    "developer": "MD ANAMUL HOQUE",
    "telegram": "https://t.me/ireentv",
    "website": "https://anamul.pages.dev"
}

def get_dhaka_time():
    tz = pytz.timezone('Asia/Dhaka')
    return datetime.now(tz).strftime('%Y-%m-%d %I:%M:%S %p')

def extract_logo(ch):
    possible_keys = [
        "tvg-logo", "tvg_logo", "tvgLogo", "logo", "logo_url", "logoUrl",
        "stream_icon", "icon", "image", "img", "poster", "thumbnail",
        "channel_logo", "tvg_image", "picture", "cover"
    ]
    for key in possible_keys:
        val = ch.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()

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
    raw_headers = ch.get("headers")
    if isinstance(raw_headers, dict):
        for k, v in raw_headers.items():
            if v:
                headers[k.strip()] = str(v).strip()

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

def extract_drm(ch):
    """DRM / ClearKey ডেটা বের করার ফাংশন"""
    drm = {}
    if isinstance(ch.get("drm"), dict):
        drm.update(ch.get("drm"))
    
    # JSON সোর্সে থাকা সম্ভাব্য Clear Key কি-ওয়ার্ড
    for k in ["clearkey", "clear_key", "license_key", "key", "key_id", "license_type"]:
        if k in ch and ch[k]:
            drm[k] = ch[k]
            
    return drm

def extract_kodi_props(ch):
    """Kodi Props ডেটা বের করার ফাংশন"""
    kodi_props = {}
    if isinstance(ch.get("kodi_props"), dict):
        kodi_props.update(ch.get("kodi_props"))
    return kodi_props

# ========================================================
# M3U প্লেলিস্ট পার্সার (OTT Headers & ClearKey DRM সহ)
# ========================================================
def parse_m3u_content(text):
    channels = []
    lines = text.strip().splitlines()
    
    current_channel = {}
    temp_headers = {}
    temp_kodi_props = {}
    temp_drm = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # ১. EXTINF লাইন থেকে চ্যানেলের মেটাডেটা নেওয়া
        if line.startswith("#EXTINF:"):
            current_channel = {}
            temp_headers = {}
            temp_kodi_props = {}
            temp_drm = {}

            name_match = re.search(r'tvg-name="([^"]*)"', line, re.IGNORECASE)
            logo_match = re.search(r'tvg-logo="([^"]*)"', line, re.IGNORECASE)
            group_match = re.search(r'group-title="([^"]*)"', line, re.IGNORECASE)
            tvg_id_match = re.search(r'tvg-id="([^"]*)"', line, re.IGNORECASE)

            title = line.split(",")[-1].strip() if "," in line else ""
            ch_name = name_match.group(1) if name_match else (title if title else "Unnamed Channel")
            
            current_channel["name"] = ch_name
            current_channel["tvg_id"] = tvg_id_match.group(1) if tvg_id_match else ""
            current_channel["logo"] = logo_match.group(1) if logo_match else ""
            current_channel["group"] = group_match.group(1) if group_match else "General"

        # ২. Kodi Props / DRM / ClearKey রিড করা
        elif line.startswith("#KODIPROP:"):
            prop_data = line.replace("#KODIPROP:", "").strip()
            if "=" in prop_data:
                k, v = prop_data.split("=", 1)
                k = k.strip()
                v = v.strip()
                temp_kodi_props[k] = v
                
                # ClearKey ও DRM ফিল্টার করে DRM অবজেক্টে সেভ
                if "license_key" in k.lower() or "clearkey" in k.lower():
                    temp_drm["license_key"] = v
                elif "license_type" in k.lower():
                    temp_drm["license_type"] = v
                elif "manifest_type" in k.lower():
                    temp_drm["manifest_type"] = v

        # ৩. EXTVLCOPT হেডারস
        elif line.startswith("#EXTVLCOPT:"):
            vlc_opt = line.replace("#EXTVLCOPT:", "").strip()
            if "=" in vlc_opt:
                k, v = vlc_opt.split("=", 1)
                k_lower = k.lower().strip()
                if k_lower in ["http-user-agent", "user-agent"]:
                    temp_headers["User-Agent"] = v.strip()
                elif k_lower in ["http-referrer", "referrer", "referer"]:
                    temp_headers["Referer"] = v.strip()
                elif k_lower in ["http-cookie", "cookie"]:
                    temp_headers["Cookie"] = v.strip()

        # ৪. EXTHTTP (JSON হেডার্স যেমন: Origin, Authorization ইত্যাদি)
        elif line.startswith("#EXTHTTP:"):
            raw_exthttp = line.replace("#EXTHTTP:", "").strip()
            try:
                http_dict = json.loads(raw_exthttp)
                if isinstance(http_dict, dict):
                    temp_headers.update(http_dict)
            except Exception:
                pass

        # ৫. স্ট্রিম URL (Pipe হেডার থাকলে তা সহ আলাদা করা)
        elif not line.startswith("#"):
            url_part = line
            if "|" in line:
                parts = line.split("|", 1)
                url_part = parts[0].strip()
                pipe_params = parts[1].split("&")
                for param in pipe_params:
                    if "=" in param:
                        hk, hv = param.split("=", 1)
                        temp_headers[hk.strip()] = hv.strip()

            if current_channel:
                current_channel["url"] = url_part
                current_channel["headers"] = temp_headers
                if temp_drm:
                    current_channel["drm"] = temp_drm
                if temp_kodi_props:
                    current_channel["kodi_props"] = temp_kodi_props
                
                channels.append(current_channel)
                
                # রিসেট
                current_channel = {}
                temp_headers = {}
                temp_kodi_props = {}
                temp_drm = {}
            else:
                channels.append({
                    "name": "Unnamed Channel",
                    "logo": "",
                    "group": "General",
                    "url": url_part,
                    "headers": temp_headers,
                    "drm": temp_drm,
                    "kodi_props": temp_kodi_props
                })
                temp_headers = {}
                temp_kodi_props = {}
                temp_drm = {}

    return channels

# ========================================================
# M3U জেনারেটর (DRM/ClearKey ও সমস্ত হেডার সহ)
# ========================================================
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
        headers = extract_headers(ch)
        drm = extract_drm(ch)
        kodi_props = extract_kodi_props(ch)
        name = extract_name(ch)
        logo = extract_logo(ch)
        group = extract_group(ch)
        url = extract_url(ch)

        if not url:
            continue

        # ১. EXTINF লাইন
        lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}')
        
        # ২. Kodi Props / ClearKey DRM যুক্ত করা
        if kodi_props:
            for kp_k, kp_v in kodi_props.items():
                lines.append(f'#KODIPROP:{kp_k}={kp_v}')
        elif drm:
            # DRM ডিকশনারি থাকলে Kodi ফরম্যাটে আউটপুট দেওয়া
            if "license_type" in drm:
                lines.append(f'#KODIPROP:inputstream.adaptive.license_type={drm["license_type"]}')
            if "license_key" in drm:
                lines.append(f'#KODIPROP:inputstream.adaptive.license_key={drm["license_key"]}')
            elif "key" in drm and "key_id" in drm:
                lines.append(f'#KODIPROP:inputstream.adaptive.license_type=clearkey')
                lines.append(f'#KODIPROP:inputstream.adaptive.license_key={drm["key_id"]}:{drm["key"]}')

        # ৩. User-Agent
        if "User-Agent" in headers and headers["User-Agent"]:
            lines.append(f'#EXTVLCOPT:http-user-agent={headers["User-Agent"]}')
            
        # ৪. Referer
        if "Referer" in headers and headers["Referer"]:
            lines.append(f'#EXTVLCOPT:http-referrer={headers["Referer"]}')
            
        # ৫. Cookie
        if "Cookie" in headers and headers["Cookie"]:
            lines.append(f'#EXTVLCOPT:http-cookie={headers["Cookie"]}')
            
        # ৬. EXTHTTP (Origin, Auth ও অন্যান্য কাস্টম হেডার)
        exthttp_data = {}
        if "Origin" in headers and headers["Origin"]:
            exthttp_data["Origin"] = headers["Origin"]
        
        for k, v in headers.items():
            if k not in ["User-Agent", "Referer", "Cookie", "Origin"] and v:
                exthttp_data[k] = v
                
        if exthttp_data:
            lines.append(f'#EXTHTTP:{json.dumps(exthttp_data)}')
            
        # ৭. স্ট্রিম URL
        lines.append(url)
        
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

    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    for playlist_name, source_url in sources.items():
        print(f"Processing: {playlist_name}...")
        try:
            url_sep = "&" if "?" in source_url else "?"
            fetch_url = f"{source_url}{url_sep}_t={int(time.time())}"

            res = requests.get(fetch_url, headers=req_headers, timeout=30)
            res.raise_for_status()
            content_text = res.text.strip()
            
            raw_channels = []

            # সোর্সটি M3U নাকি JSON তা শনাক্ত করা
            if content_text.startswith("#EXTM3U") or content_text.startswith("#EXTINF") or ".m3u" in source_url.lower():
                print(f"-> Detected M3U Playlist. Parsing OTT Headers & ClearKeys...")
                raw_channels = parse_m3u_content(content_text)
            else:
                try:
                    data = res.json()
                    print(f"-> Detected JSON Playlist.")
                    if isinstance(data, list):
                        raw_channels = data
                    elif isinstance(data, dict):
                        raw_channels = data.get("channels") or data.get("data") or data.get("streams") or []
                except Exception:
                    print(f"-> Fallback to M3U Parser...")
                    raw_channels = parse_m3u_content(content_text)

            # ১ নম্বরে প্রোমো চ্যানেল যোগ
            all_channels = [PROMO_CHANNEL] + raw_channels

            # কাস্টম ডিটেইলস ও হেডারসহ JSON প্লেলিস্ট তৈরি
            final_json = {
                "playlist_name": playlist_name,
                "developer": DEVELOPER_INFO["developer"],
                "telegram": DEVELOPER_INFO["telegram"],
                "website": DEVELOPER_INFO["website"],
                "channels_amount": len(all_channels),
                "last_update": last_update_time,
                "channels": all_channels
            }

            safe_name = playlist_name.lower().replace(" ", "_")

            # ১. রুট ডিরেক্টরিতে JSON ফাইল সেভ
            with open(f"{safe_name}.json", "w", encoding="utf-8") as f:
                json.dump(final_json, f, indent=4, ensure_ascii=False)

            # ২. রুট ডিরেক্টরিতে M3U ফাইল সেভ
            m3u_content = generate_m3u(playlist_name, all_channels, last_update_time)
            with open(f"{safe_name}.m3u", "w", encoding="utf-8") as f:
                f.write(m3u_content)

            print(f"✓ Saved: {safe_name}.json and {safe_name}.m3u (Total: {len(all_channels)} Channels)")

        except Exception as err:
            print(f"Failed to process {playlist_name}: {err}")

if __name__ == "__main__":
    process()
