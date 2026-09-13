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

# পার্সোনাল মেটাডেটা
DEVELOPER_INFO = {
    "developer": "MD ANAMUL HOQUE",
    "telegram": "https://t.me/ireentv",
    "website": "https://anamul.pages.dev"
}

def get_dhaka_time():
    tz = pytz.timezone('Asia/Dhaka')
    return datetime.now(tz).strftime('%Y-%m-%d %I:%M:%S %p')

def extract_logo(ch):
    if not isinstance(ch, dict):
        return ""
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
        k_lower = str(k).lower().replace("-", "_").strip()
        if any(term in k_lower for term in ["logo", "icon", "poster", "thumb", "image"]):
            if v and isinstance(v, str) and (v.startswith("http://") or v.startswith("https://")):
                return v.strip()
    return ""

def extract_name(ch):
    if not isinstance(ch, dict):
        return "Unnamed Channel"
    possible_keys = ["name", "channel_name", "title", "tvg_name", "tvg-name", "stream_name", "channelName", "channel"]
    for key in possible_keys:
        val = ch.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return "Unnamed Channel"

def extract_group(ch):
    if not isinstance(ch, dict):
        return "General"
    possible_keys = ["group", "group_title", "group-title", "category", "category_name", "genre", "groupTitle"]
    for key in possible_keys:
        val = ch.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return "General"

def extract_urls(ch):
    urls = []
    if not isinstance(ch, dict):
        return urls

    list_keys = ["streamUrls", "stream_urls", "urls", "links", "servers", "sources", "streams", "stream_links"]
    for key in list_keys:
        val = ch.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    urls.append(item.strip())
                elif isinstance(item, dict):
                    nested = extract_urls(item)
                    urls.extend(nested)
            if urls:
                return urls

    single_keys = ["link", "url", "stream_url", "stream_link", "streamUrl", "src", "mpd_url", "manifest_url", "play_url", "file"]
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
    """হেডার এবং রেফারার শুধুমাত্র নন-এম্পটি (Non-empty) হলে এক্সট্রাক্ট করবে"""
    headers = {}
    
    def scan_dict(d):
        if not isinstance(d, dict):
            return
        
        # ১. Nested Header অবজেক্ট
        for hk in ["headers", "http_headers", "request_headers", "stream_headers", "header", "httpHeaders"]:
            raw_h = d.get(hk)
            if isinstance(raw_h, dict):
                for k, v in raw_h.items():
                    if v and str(v).strip():
                        headers[str(k).strip()] = str(v).strip()
            elif isinstance(raw_h, str) and raw_h.strip():
                if raw_h.startswith("{") and raw_h.endswith("}"):
                    try:
                        parsed = json.loads(raw_h)
                        if isinstance(parsed, dict):
                            for k, v in parsed.items():
                                if v and str(v).strip():
                                    headers[str(k).strip()] = str(v).strip()
                    except Exception:
                        pass
                elif "=" in raw_h:
                    for part in raw_h.split("&"):
                        if "=" in part:
                            k_n, v_n = part.split("=", 1)
                            if v_n.strip():
                                headers[k_n.strip()] = v_n.strip()

        # ২. ফ্ল্যাট কি-ওয়ার্ড চেক
        for k, v in d.items():
            if v is None or not isinstance(v, (str, int)):
                continue
            k_clean = str(k).lower().replace("-", "_").strip()
            val_str = str(v).strip()
            if not val_str:
                continue

            if k_clean in ["user_agent", "useragent", "http_user_agent", "user_agent_string"]:
                headers["User-Agent"] = val_str
            elif k_clean in ["referer", "referrer", "http_referrer", "http_referer"]:
                headers["Referer"] = val_str
            elif k_clean in ["cookie", "http_cookie"]:
                headers["Cookie"] = val_str
            elif k_clean in ["origin", "http_origin"]:
                headers["Origin"] = val_str
            elif k_clean in ["authorization", "auth", "token"]:
                headers["Authorization"] = val_str

    if isinstance(ch, dict):
        scan_dict(ch)
        for sub_val in ch.values():
            if isinstance(sub_val, dict):
                scan_dict(sub_val)

    clean_headers = {}
    for k, v in headers.items():
        if not v or not str(v).strip():
            continue
        k_lower = k.lower().replace("-", "_").strip()
        if k_lower in ["user_agent", "useragent"]:
            clean_headers["User-Agent"] = str(v).strip()
        elif k_lower in ["referer", "referrer"]:
            clean_headers["Referer"] = str(v).strip()
        elif k_lower == "cookie":
            clean_headers["Cookie"] = str(v).strip()
        elif k_lower == "origin":
            clean_headers["Origin"] = str(v).strip()
        elif k_lower in ["authorization", "auth"]:
            clean_headers["Authorization"] = str(v).strip()
        else:
            clean_headers[k.strip()] = str(v).strip()

    return clean_headers

def extract_drm(ch):
    """
    শুধুমাত্র যদি ভ্যালিড ও নন-এম্পটি DRM Key থাকে তবেই এক্সট্রাক্ট করবে,
    ফাঁকা ("") থাকলে সম্পূর্ণ ইগনোর করবে।
    """
    drm = {}

    def scan_for_drm(obj):
        nonlocal drm
        if not isinstance(obj, (dict, list)) or drm.get("license_key"):
            return

        if isinstance(obj, list):
            for item in obj:
                scan_for_drm(item)
            return

        target_keys = [
            "drm_key", "drmKey", "drm_keys", "drmKeys",
            "license_key", "licenseKey", "lic_key", "licence_key",
            "clearkey", "clearKey", "clear_key", "clearkeys",
            "key", "keys", "license", "licence", "drm"
        ]

        for k in target_keys:
            val = obj.get(k)
            if not val:
                continue

            # স্ট্রিং ফরম্যাট (যেমন: "kid:key")
            if isinstance(val, str) and val.strip():
                v_str = val.strip()
                if v_str.startswith("{") or v_str.startswith("["):
                    try:
                        val = json.loads(v_str)
                    except Exception:
                        pass
                
                if isinstance(val, str) and val.strip():
                    drm["license_key"] = val.strip()
                    scheme = obj.get("drm_scheme") or obj.get("drm_type") or obj.get("license_type")
                    drm["license_type"] = scheme.strip().lower() if (scheme and isinstance(scheme, str) and scheme.strip()) else ("clearkey" if ":" in val else "com.widevine.alpha")
                    return

            # ডিকশনারি ফরম্যাট
            if isinstance(val, dict):
                k_id = val.get("key_id") or val.get("keyId") or val.get("kid") or val.get("id")
                k_val = val.get("key") or val.get("k") or val.get("value")
                if k_id and k_val and str(k_id).strip() and str(k_val).strip():
                    drm["license_key"] = f"{str(k_id).strip()}:{str(k_val).strip()}"
                    drm["license_type"] = "clearkey"
                    return
                elif "license_key" in val and val["license_key"] and str(val["license_key"]).strip():
                    drm["license_key"] = str(val["license_key"]).strip()
                    drm["license_type"] = "clearkey" if ":" in str(val["license_key"]) else "com.widevine.alpha"
                    return
                elif "drm_key" in val and val["drm_key"] and str(val["drm_key"]).strip():
                    drm["license_key"] = str(val["drm_key"]).strip()
                    drm["license_type"] = "clearkey"
                    return

            # লিস্ট ফরম্যাট
            if isinstance(val, list):
                keys_list = []
                for item in val:
                    if isinstance(item, dict):
                        k_id = item.get("key_id") or item.get("keyId") or item.get("kid")
                        k_val = item.get("key") or item.get("k") or item.get("value")
                        if k_id and k_val and str(k_id).strip() and str(k_val).strip():
                            keys_list.append(f"{str(k_id).strip()}:{str(k_val).strip()}")
                    elif isinstance(item, str) and ":" in item and item.strip():
                        keys_list.append(item.strip())
                if keys_list:
                    drm["license_key"] = ",".join(keys_list)
                    drm["license_type"] = "clearkey"
                    return

        # আলাদা key_id এবং key
        k_id = obj.get("key_id") or obj.get("keyId") or obj.get("kid")
        k_val = obj.get("key") or obj.get("k")
        if k_id and k_val and str(k_id).strip() and str(k_val).strip():
            drm["license_key"] = f"{str(k_id).strip()}:{str(k_val).strip()}"
            drm["license_type"] = "clearkey"
            return

        # Widevine / License URL
        lic_url = obj.get("license_url") or obj.get("licence_url") or obj.get("widevine_url") or obj.get("drm_url") or obj.get("licenseUrl")
        if lic_url and isinstance(lic_url, str) and lic_url.strip():
            drm["license_key"] = lic_url.strip()
            drm["license_type"] = "com.widevine.alpha"
            return

        for v in obj.values():
            if isinstance(v, (dict, list)):
                scan_for_drm(v)

    scan_for_drm(ch)

    # যদি license_key ফাঁকা থাকে, তবে drm সম্পূর্ণ ক্লিয়ার করা হবে
    if "license_key" in drm and not drm["license_key"].strip():
        drm = {}

    if "license_key" in drm and drm["license_key"]:
        scheme = ch.get("drm_scheme") or ch.get("drm_type") or ch.get("license_type")
        if scheme and isinstance(scheme, str) and scheme.strip():
            drm["license_type"] = scheme.strip().lower()

        lt = drm.get("license_type", "").lower()
        if lt in ["clearkey", "clear_key", "org.w3.clearkey"]:
            drm["license_type"] = "clearkey"
        elif lt in ["widevine", "com.widevine.alpha"]:
            drm["license_type"] = "com.widevine.alpha"
        elif not lt:
            drm["license_type"] = "clearkey" if ":" in str(drm["license_key"]) else "com.widevine.alpha"

    return drm

def extract_kodi_props(ch):
    kodi_props = {}
    if isinstance(ch, dict) and isinstance(ch.get("kodi_props"), dict):
        for k, v in ch["kodi_props"].items():
            if v and str(v).strip():
                kodi_props[str(k).strip()] = str(v).strip()
    return kodi_props

def parse_channel_instances(ch):
    """নেস্টেড streams বা সিঙ্গেল channel ভেঙে পরিষ্কার ফ্ল্যাট ডাটা তৈরি করে"""
    instances = []
    if not isinstance(ch, dict):
        return instances

    name = extract_name(ch)
    logo = extract_logo(ch)
    group = extract_group(ch)
    parent_headers = extract_headers(ch)
    parent_drm = extract_drm(ch)
    parent_kodi = extract_kodi_props(ch)

    stream_list_keys = ["streams", "servers", "sources", "streamUrls", "stream_urls", "urls", "links", "stream_links"]
    nested_found = False

    for sk in stream_list_keys:
        val = ch.get(sk)
        if isinstance(val, list) and len(val) > 0:
            for item in val:
                if isinstance(item, dict):
                    nested_found = True
                    c_url = item.get("link") or item.get("url") or item.get("stream_url") or item.get("src") or item.get("mpd_url") or ""
                    if c_url and isinstance(c_url, str) and c_url.strip():
                        c_headers = {**parent_headers, **extract_headers(item)}
                        c_drm = {**parent_drm, **extract_drm(item)}
                        c_kodi = {**parent_kodi, **extract_kodi_props(item)}
                        instances.append({
                            "name": extract_name(item) if extract_name(item) != "Unnamed Channel" else name,
                            "logo": extract_logo(item) or logo,
                            "group": item.get("group") or group,
                            "url": c_url.strip(),
                            "headers": c_headers,
                            "drm": c_drm,
                            "kodi_props": c_kodi
                        })
                elif isinstance(item, str) and item.strip():
                    nested_found = True
                    instances.append({
                        "name": name,
                        "logo": logo,
                        "group": group,
                        "url": item.strip(),
                        "headers": parent_headers,
                        "drm": parent_drm,
                        "kodi_props": parent_kodi
                    })
            if nested_found:
                break

    if not nested_found:
        urls = extract_urls(ch)
        for u in urls:
            instances.append({
                "name": name,
                "logo": logo,
                "group": group,
                "url": u.strip(),
                "headers": parent_headers,
                "drm": parent_drm,
                "kodi_props": parent_kodi
            })

    return instances

# ========================================================
# M3U পার্সার (টেক্সট M3U সোর্সের জন্য)
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
            lic_key_match = re.search(r'license_key="([^"]*)"', line, re.IGNORECASE)
            lic_type_match = re.search(r'license_type="([^"]*)"', line, re.IGNORECASE)

            title = line.split(",")[-1].strip() if "," in line else ""
            ch_name = name_match.group(1) if name_match else (title if title else "Unnamed Channel")
            
            current_channel["name"] = ch_name
            current_channel["tvg_id"] = tvg_id_match.group(1) if tvg_id_match else ""
            current_channel["logo"] = logo_match.group(1) if logo_match else ""
            current_channel["group"] = group_match.group(1) if group_match else "General"

            if lic_key_match and lic_key_match.group(1).strip():
                temp_drm["license_key"] = lic_key_match.group(1).strip()
            if lic_type_match and lic_type_match.group(1).strip():
                temp_drm["license_type"] = lic_type_match.group(1).strip()

        elif line.startswith("#KODIPROP:"):
            prop_data = line.replace("#KODIPROP:", "").strip()
            if "=" in prop_data:
                k, v = prop_data.split("=", 1)
                k, v = k.strip(), v.strip()
                if v:
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
                k_lower, v_val = k.lower().strip(), v.strip()
                if v_val:
                    if k_lower in ["http-user-agent", "user-agent"]:
                        temp_headers["User-Agent"] = v_val
                    elif k_lower in ["http-referrer", "referrer", "referer"]:
                        temp_headers["Referer"] = v_val
                    elif k_lower in ["http-cookie", "cookie"]:
                        temp_headers["Cookie"] = v_val

        elif line.startswith("#EXTHTTP:"):
            raw_exthttp = line.replace("#EXTHTTP:", "").strip()
            try:
                http_dict = json.loads(raw_exthttp)
                if isinstance(http_dict, dict):
                    temp_headers.update({k: str(v).strip() for k, v in http_dict.items() if v and str(v).strip()})
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
                        if hv.strip():
                            temp_headers[hk.strip()] = hv.strip()

            if current_channel:
                current_channel["url"] = url_part
                current_channel["headers"] = temp_headers
                if temp_drm and temp_drm.get("license_key"):
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
                    "drm": temp_drm if temp_drm.get("license_key") else {},
                    "kodi_props": temp_kodi_props
                })
                temp_headers = {}
                temp_kodi_props = {}
                temp_drm = {}

    return channels

# ========================================================
# M3U জেনারেটর (DRM/Headers থাকলে শুধুমাত্র তখনই ট্যাগ বসবে)
# ========================================================
def generate_m3u(playlist_name, channels, last_update):
    channel_entries = []
    
    for raw_ch in channels:
        instances = parse_channel_instances(raw_ch)
        
        for item in instances:
            url = item.get("url", "").strip()
            if not url:
                continue

            name = item.get("name", "Unnamed Channel")
            logo = item.get("logo", "")
            group = item.get("group", "General")
            headers = item.get("headers", {})
            drm = item.get("drm", {})
            kodi_props = item.get("kodi_props", {})

            clean_url = url.split("|")[0].strip() if "|" in url else url
            lines = []
            
            is_mpd = ".mpd" in clean_url.lower()
            # DRM তখনই সত্য হবে যখন license_key ফাঁকা নয়
            has_drm = bool(drm.get("license_key") and str(drm.get("license_key")).strip())
            lic_type = drm.get("license_type", "clearkey") if has_drm else ""
            lic_key = drm.get("license_key", "").strip() if has_drm else ""

            # ১. EXTINF লাইন
            extinf_parts = [f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}"']
            if has_drm:
                extinf_parts.append(f'license_type="{lic_type}" license_key="{lic_key}"')
            extinf_parts.append(f',{name}')
            lines.append(" ".join(extinf_parts))
            
            # ২. Kodi Props (শুধুমাত্র MPD বা DRM থাকলে বা kodi_props থাকলে)
            if is_mpd or has_drm:
                lines.append('#KODIPROP:inputstream=inputstream.adaptive')
                manifest_type = "mpd" if is_mpd else ("hls" if ".m3u8" in clean_url.lower() else "mpd")
                lines.append(f'#KODIPROP:inputstream.adaptive.manifest_type={manifest_type}')

            if kodi_props:
                for kp_k, kp_v in kodi_props.items():
                    if kp_k not in ["inputstream", "inputstream.adaptive.manifest_type"] and str(kp_v).strip():
                        lines.append(f'#KODIPROP:{kp_k}={kp_v}')

            # ৩. DRM ট্যাগ ইনসার্ট (যদি ভ্যালিড DRM থাকে)
            if has_drm:
                if "inputstream.adaptive.license_type" not in kodi_props:
                    lines.append(f'#KODIPROP:inputstream.adaptive.license_type={lic_type}')
                if "inputstream.adaptive.license_key" not in kodi_props:
                    lines.append(f'#KODIPROP:inputstream.adaptive.license_key={lic_key}')

            # ৪. হেডার অপশন (#EXTVLCOPT)
            if "User-Agent" in headers and headers["User-Agent"]:
                lines.append(f'#EXTVLCOPT:http-user-agent={headers["User-Agent"]}')
            if "Referer" in headers and headers["Referer"]:
                lines.append(f'#EXTVLCOPT:http-referrer={headers["Referer"]}')
            if "Cookie" in headers and headers["Cookie"]:
                lines.append(f'#EXTVLCOPT:http-cookie={headers["Cookie"]}')

            # ৫. কাস্টম হেডার ডিকশনারি (#EXTHTTP)
            if headers:
                lines.append(f'#EXTHTTP:{json.dumps(headers)}')
                if is_mpd or has_drm:
                    stream_header_str = "&".join([f"{k}={v}" for k, v in headers.items() if v])
                    if stream_header_str:
                        lines.append(f'#KODIPROP:inputstream.adaptive.stream_headers={stream_header_str}')

            # ৬. স্ট্রিম URL
            lines.append(clean_url)
            channel_entries.append("\n".join(lines))

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

            # অটো-ডিটেকশন
            is_json = False
            try:
                data = json.loads(content_text)
                is_json = True
            except Exception:
                is_json = False

            if is_json:
                print(f"-> Detected Valid JSON Source. Preserving OTT DRM/Headers...")
                if isinstance(data, list):
                    raw_channels = data
                elif isinstance(data, dict):
                    raw_channels = data.get("channels") or data.get("data") or data.get("streams") or data.get("result") or [data]
            else:
                print(f"-> Detected M3U Source. Converting to JSON & M3U...")
                raw_channels = parse_m3u_content(content_text)

            all_channels = [PROMO_CHANNEL] + raw_channels

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

            with open(f"{safe_name}.json", "w", encoding="utf-8") as f:
                json.dump(final_json, f, indent=4, ensure_ascii=False)

            m3u_content = generate_m3u(playlist_name, all_channels, last_update_time)
            with open(f"{safe_name}.m3u", "w", encoding="utf-8") as f:
                f.write(m3u_content)

            print(f"✓ Successfully Processed & Saved: {safe_name}.json and {safe_name}.m3u")

        except Exception as err:
            print(f"Failed to process {playlist_name}: {err}")

if __name__ == "__main__":
    process()
