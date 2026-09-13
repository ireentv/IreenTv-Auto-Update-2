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

def extract_urls(ch):
    """সিঙ্গেল বা মাল্টিপল যেকোনো ফরম্যাট থেকে সব URL এক্সট্রাক্ট করবে"""
    urls = []
    
    # ১. মাল্টি-ইউআরএল লিস্ট কি চেক করা
    list_keys = ["streamUrls", "stream_urls", "urls", "links", "servers", "sources", "streams", "stream_links"]
    for key in list_keys:
        val = ch.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    urls.append(item.strip())
                elif isinstance(item, dict):
                    nested_urls = extract_urls(item)
                    urls.extend(nested_urls)
            if urls:
                return urls

    # ২. সিঙ্গেল কি চেক করা
    single_keys = ["url", "stream_url", "link", "stream_link", "streamUrl", "src", "mpd_url", "manifest_url", "play_url"]
    for key in single_keys:
        val = ch.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    urls.append(item.strip())
        elif isinstance(val, str) and val.strip():
            urls.append(val.strip())
            
        if urls:
            return urls

    return urls

def extract_headers(ch):
    """JSON সোর্সের সব ধরণের হেডার ও রেফারার সঠিকভাবে এক্সট্রাক্ট করে"""
    headers = {}
    
    # ১. Nested Header অবজেক্ট চেক করা
    header_keys = ["headers", "http_headers", "request_headers", "stream_headers", "header", "httpHeaders"]
    for hk in header_keys:
        raw_h = ch.get(hk)
        if isinstance(raw_h, dict):
            for k, v in raw_h.items():
                if v:
                    headers[str(k).strip()] = str(v).strip()
        elif isinstance(raw_h, str) and raw_h.strip():
            if raw_h.startswith("{") and raw_h.endswith("}"):
                try:
                    parsed = json.loads(raw_h)
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            if v:
                                headers[str(k).strip()] = str(v).strip()
                except Exception:
                    pass
            elif "=" in raw_h:
                for part in raw_h.split("&"):
                    if "=" in part:
                        hk_name, hv = part.split("=", 1)
                        headers[hk_name.strip()] = hv.strip()

    # ২. ফ্ল্যাট কি-ওয়ার্ড চেক করা
    for key, value in ch.items():
        if value is None or not isinstance(value, (str, int)):
            continue
        k_lower = key.lower().replace("-", "_").strip()
        val_str = str(value).strip()
        if not val_str:
            continue

        if k_lower in ["user_agent", "useragent", "http_user_agent", "user_agent_string"]:
            headers["User-Agent"] = val_str
        elif k_lower in ["referer", "referrer", "http_referrer", "http_referer"]:
            headers["Referer"] = val_str
        elif k_lower in ["cookie", "http_cookie"]:
            headers["Cookie"] = val_str
        elif k_lower in ["origin", "http_origin"]:
            headers["Origin"] = val_str
        elif k_lower in ["authorization", "auth", "token"]:
            headers["Authorization"] = val_str
        elif k_lower in ["x_forwarded_for", "x-forwarded-for"]:
            headers["X-Forwarded-For"] = val_str

    # ৩. হেডার স্ট্যান্ডার্ডাইযেশন
    clean_headers = {}
    for k, v in headers.items():
        k_lower = k.lower().replace("-", "_").strip()
        if k_lower in ["user_agent", "useragent"]:
            clean_headers["User-Agent"] = v
        elif k_lower in ["referer", "referrer"]:
            clean_headers["Referer"] = v
        elif k_lower == "cookie":
            clean_headers["Cookie"] = v
        elif k_lower == "origin":
            clean_headers["Origin"] = v
        elif k_lower in ["authorization", "auth"]:
            clean_headers["Authorization"] = v
        else:
            clean_headers[k] = v

    return clean_headers

def extract_drm(ch):
    """JSON সোর্সের drm_key, clearkey, keys, widevine সহ সব DRM এক্সট্রাক্ট করবে"""
    drm = {}

    # ১. drm অবজেক্ট যদি থাকে
    raw_drm = ch.get("drm")
    if isinstance(raw_drm, dict):
        drm.update(raw_drm)
    elif isinstance(raw_drm, str) and raw_drm.strip():
        drm["license_key"] = raw_drm.strip()

    # ২. সরাসরি drm_key, clearkey, keys ইত্যাদি কী চেক করা
    drm_keys_to_check = [
        "drm_key", "drmKey", "drm_keys", "drmKeys",
        "license_key", "licenseKey", "lic_key", "licence_key",
        "clearkey", "clearKey", "clear_key", "clearkeys",
        "key", "keys", "license", "licence"
    ]

    for k in drm_keys_to_check:
        val = ch.get(k)
        if not val:
            continue

        # স্ট্রিং ফরম্যাট (যেমন "0b59ce...:48e4ba...")
        if isinstance(val, str) and val.strip():
            v_str = val.strip()
            if v_str.startswith("{") or v_str.startswith("["):
                try:
                    parsed = json.loads(v_str)
                    val = parsed
                except Exception:
                    pass

            if isinstance(val, str):
                drm["license_key"] = v_str
                if "license_type" not in drm:
                    drm["license_type"] = "clearkey"
                break

        # ডিকশনারি ফরম্যাট
        if isinstance(val, dict):
            k_id = val.get("key_id") or val.get("keyId") or val.get("kid") or val.get("id")
            k_val = val.get("key") or val.get("k") or val.get("value")
            if k_id and k_val:
                drm["license_key"] = f"{str(k_id).strip()}:{str(k_val).strip()}"
                drm["license_type"] = "clearkey"
                break
            elif "license_key" in val:
                drm["license_key"] = str(val["license_key"]).strip()
                break
            elif "drm_key" in val:
                drm["license_key"] = str(val["drm_key"]).strip()
                break

        # লিস্ট ফরম্যাট ([{"kid": "...", "k": "..."}, ...])
        if isinstance(val, list):
            keys_list = []
            for item in val:
                if isinstance(item, dict):
                    k_id = item.get("key_id") or item.get("keyId") or item.get("kid")
                    k_val = item.get("key") or item.get("k") or item.get("value")
                    if k_id and k_val:
                        keys_list.append(f"{str(k_id).strip()}:{str(k_val).strip()}")
                elif isinstance(item, str) and ":" in item:
                    keys_list.append(item.strip())
            if keys_list:
                drm["license_key"] = ",".join(keys_list)
                drm["license_type"] = "clearkey"
                break

    # ৩. আলাদা key_id এবং key থাকলে
    k_id = ch.get("key_id") or ch.get("keyId") or ch.get("kid")
    k_val = ch.get("key") or ch.get("k")
    if k_id and k_val and "license_key" not in drm:
        drm["license_key"] = f"{str(k_id).strip()}:{str(k_val).strip()}"
        drm["license_type"] = "clearkey"

    # ৪. Widevine / License URL
    lic_url = ch.get("license_url") or ch.get("licence_url") or ch.get("widevine_url") or ch.get("drm_url") or ch.get("licenseUrl")
    if lic_url and isinstance(lic_url, str) and lic_url.strip():
        drm["license_key"] = lic_url.strip()
        if "license_type" not in drm:
            drm["license_type"] = "com.widevine.alpha"

    # ৫. DRM Type সেট ও নরমালাইজেশন
    if "drm_type" in ch and isinstance(ch["drm_type"], str) and ch["drm_type"].strip():
        drm["license_type"] = ch["drm_type"].strip()
    elif "license_type" in ch and isinstance(ch["license_type"], str) and ch["license_type"].strip():
        drm["license_type"] = ch["license_type"].strip()

    if "license_key" in drm:
        if "license_type" not in drm or not drm["license_type"]:
            drm["license_type"] = "clearkey" if ":" in str(drm["license_key"]) else "com.widevine.alpha"
        
        lt = drm["license_type"].lower()
        if lt in ["clearkey", "clear_key", "org.w3.clearkey"]:
            drm["license_type"] = "clearkey"
        elif lt in ["widevine", "com.widevine.alpha"]:
            drm["license_type"] = "com.widevine.alpha"

    return drm

def extract_kodi_props(ch):
    kodi_props = {}
    if isinstance(ch.get("kodi_props"), dict):
        kodi_props.update(ch.get("kodi_props"))
    return kodi_props

# ========================================================
# M3U পার্সার
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

        elif line.startswith("#KODIPROP:"):
            prop_data = line.replace("#KODIPROP:", "").strip()
            if "=" in prop_data:
                k, v = prop_data.split("=", 1)
                k = k.strip()
                v = v.strip()
                temp_kodi_props[k] = v
                
                if "license_key" in k.lower() or "clearkey" in k.lower():
                    temp_drm["license_key"] = v
                elif "license_type" in k.lower():
                    temp_drm["license_type"] = v
                elif "manifest_type" in k.lower():
                    temp_drm["manifest_type"] = v

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

        elif line.startswith("#EXTHTTP:"):
            raw_exthttp = line.replace("#EXTHTTP:", "").strip()
            try:
                http_dict = json.loads(raw_exthttp)
                if isinstance(http_dict, dict):
                    temp_headers.update(http_dict)
            except Exception:
                pass

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
# M3U জেনারেটর
# ========================================================
def generate_m3u(playlist_name, channels, last_update):
    channel_entries = []
    
    for ch in channels:
        urls = extract_urls(ch)
        if not urls:
            continue

        headers = extract_headers(ch)
        drm = extract_drm(ch)
        kodi_props = extract_kodi_props(ch)
        name = extract_name(ch)
        logo = extract_logo(ch)
        group = extract_group(ch)

        for url in urls:
            clean_url = url.split("|")[0].strip() if "|" in url else url.strip()
            lines = []
            
            # ১. EXTINF লাইন
            lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}')
            
            # ২. Kodi Props & DRM হ্যান্ডলিং
            is_mpd = ".mpd" in clean_url.lower()
            has_drm = bool(drm.get("license_key"))

            if is_mpd or has_drm or kodi_props:
                lines.append('#KODIPROP:inputstream=inputstream.adaptive')
                manifest_type = "mpd" if is_mpd else ("hls" if ".m3u8" in clean_url.lower() else "mpd")
                lines.append(f'#KODIPROP:inputstream.adaptive.manifest_type={manifest_type}')

            if kodi_props:
                for kp_k, kp_v in kodi_props.items():
                    if kp_k not in ["inputstream", "inputstream.adaptive.manifest_type"]:
                        lines.append(f'#KODIPROP:{kp_k}={kp_v}')

            if has_drm:
                lic_type = drm.get("license_type", "clearkey")
                lic_key = drm.get("license_key")
                if "inputstream.adaptive.license_type" not in kodi_props:
                    lines.append(f'#KODIPROP:inputstream.adaptive.license_type={lic_type}')
                if "inputstream.adaptive.license_key" not in kodi_props and lic_key:
                    lines.append(f'#KODIPROP:inputstream.adaptive.license_key={lic_key}')

            # ৩. হেডার হ্যান্ডলিং (#EXTVLCOPT)
            if "User-Agent" in headers and headers["User-Agent"]:
                lines.append(f'#EXTVLCOPT:http-user-agent={headers["User-Agent"]}')
            if "Referer" in headers and headers["Referer"]:
                lines.append(f'#EXTVLCOPT:http-referrer={headers["Referer"]}')
            if "Cookie" in headers and headers["Cookie"]:
                lines.append(f'#EXTVLCOPT:http-cookie={headers["Cookie"]}')

            # ৪. সম্পূর্ণ হেডার ডিকশনারি (#EXTHTTP)
            if headers:
                lines.append(f'#EXTHTTP:{json.dumps(headers)}')
                
                # Kodi adaptive stream headers
                stream_header_str = "&".join([f"{k}={v}" for k, v in headers.items()])
                if is_mpd or has_drm:
                    lines.append(f'#KODIPROP:inputstream.adaptive.stream_headers={stream_header_str}')

            # ৫. স্ট্রিম URL
            lines.append(clean_url)
            channel_entries.append("\n".join(lines))

    # প্লেলিস্ট হেডার
    header_lines = [
        f'#EXTM3U name="{playlist_name}"',
        '# =====================================================',
        f'# Playlist Name   : {playlist_name}',
        f'# Developer       : {DEVELOPER_INFO["developer"]}',
        f'# Telegram Channel: {DEVELOPER_INFO["telegram"]}',
        f'# Website         : {DEVELOPER_INFO["website"]}',
        f'# Total Channels  : {len(channel_entries)}',
        f'# Last Updated    : {last_update}',
        '# =====================================================\n'
    ]
    
    return "\n".join(header_lines) + "\n" + "\n".join(channel_entries)

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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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

            # সোর্স ডিটেকশন (M3U বনাম JSON)
            if content_text.startswith("#EXTM3U") or content_text.startswith("#EXTINF") or ".m3u" in source_url.lower():
                print(f"-> Detected M3U Source. Converting to JSON & M3U...")
                raw_channels = parse_m3u_content(content_text)
            else:
                try:
                    data = res.json()
                    print(f"-> Detected JSON Source. Preserving OTT DRM/Headers & Converting to M3U...")
                    if isinstance(data, list):
                        raw_channels = data
                    elif isinstance(data, dict):
                        raw_channels = data.get("channels") or data.get("data") or data.get("streams") or []
                except Exception:
                    print(f"-> Fallback to M3U Parser...")
                    raw_channels = parse_m3u_content(content_text)

            # প্রোমো চ্যানেলসহ যুক্ত করা
            all_channels = [PROMO_CHANNEL] + raw_channels

            # JSON ফাইল তৈরি
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

            # ১. JSON ফাইল সেভ
            with open(f"{safe_name}.json", "w", encoding="utf-8") as f:
                json.dump(final_json, f, indent=4, ensure_ascii=False)

            # ২. M3U ফাইল সেভ
            m3u_content = generate_m3u(playlist_name, all_channels, last_update_time)
            with open(f"{safe_name}.m3u", "w", encoding="utf-8") as f:
                f.write(m3u_content)

            print(f"✓ Successfully Saved: {safe_name}.json and {safe_name}.m3u")

        except Exception as err:
            print(f"Failed to process {playlist_name}: {err}")

if __name__ == "__main__":
    process()
