import os
import sys

# --- GLOBAL ENCODING FIX ---
# Force Windows terminal to support UTF-8 emojis without crashing
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
# ---------------------------

import requests
import json
import time
from datetime import datetime, timezone
from PIL import Image
import socket
# Force the server to drop dead connections after 5 minutes (300 seconds)
socket.setdefaulttimeout(300)

if getattr(sys, 'frozen', False):
    install_dir = os.path.dirname(sys.executable)
else:
    install_dir = os.path.dirname(os.path.abspath(__file__))
app_data_dir = os.path.join(os.environ.get('APPDATA', ''), 'IslamicReelsStudio')

def get_meta_server_time():
    try:
        res = requests.get("https://worldtimeapi.org/api/timezone/Etc/UTC", timeout=5).json()
        utc_time_str = datetime.fromisoformat(res['datetime']).strftime('%Y-%m-%d %H:%M:%S UTC')
        return utc_time_str, int(res['unixtime'])
    except:
        return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'), int(time.time())

def check_server_status(settings):
    statuses = {
        "meta_time": get_meta_server_time()[0],
        "facebook": "❌ Disconnected / No Token",
        "youtube": "⚠️ Needs OAuth JSON"
    }
    
    if settings.get("fb_token"):
        try:
            res = requests.get(f"https://graph.facebook.com/v19.0/me?access_token={settings['fb_token']}", timeout=5).json()
            if "id" in res:
                statuses["facebook"] = f"✅ Connected as: {res.get('name', 'Valid Page')}"
            else:
                statuses["facebook"] = "⚠️ Invalid Token or Expired"
        except:
            statuses["facebook"] = "🌐 Network Error"
            
    if os.path.exists(os.path.join(install_dir, "client_secret.json")) or os.path.exists("client_secret.json"):
        statuses["youtube"] = "✅ OAuth File Found"
        
    return statuses

def build_caption(quran_data, cta_text="", reciter_name=""):
    if not isinstance(quran_data, dict):
        quran_data = {}

    verses = quran_data.get('verses', [])
    if verses and isinstance(verses, list):
        urdu = "\n".join([v.get('urdu', '') for v in verses if isinstance(v, dict) and v.get('urdu')])
        english = "\n".join([v.get('english', '') for v in verses if isinstance(v, dict) and v.get('english')])
    else:
        urdu = quran_data.get('text', 'Beautiful Quran Recitation')
        english = quran_data.get('text', 'Beautiful Quran Recitation')

    ref_raw = quran_data.get('reference', 'Quran Recitation')
    reference = ref_raw.split("| [BG:")[0].strip() if isinstance(ref_raw, str) else 'Quran Recitation'

    caption = f"✨ {english or 'Beautiful Quran Recitation'}\n\n"
    if urdu and urdu != english:
        caption += f"Urdu: {urdu} - 📖 {reference}\n\n"
    else:
        caption += f"📖 {reference}\n\n"
    
    if reciter_name:
        clean_name = reciter_name.replace(" (Safe)", "").replace(" (High Copyright Risk)", "")
        caption += f"🎙️ Reciter: {clean_name}\n\n"
    else:
        caption += "\n"
        
    if cta_text:
        caption += f"👇 {cta_text}\n\n"

    caption += "#Quran #IslamicReels #QuranRecitation #Islam #Muslim #DailyAyah #QuranQuotes #Deen #Allah #Shorts"
    return caption

import shutil
import http.server
import socketserver
import threading

# --- SELF-HOSTED EC2 MEDIA SERVER MODULE ---
SERVER_PORT = 8080
_ec2_server_instance = None
_ec2_server_thread = None
_ec2_public_ip = None

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class QuietMediaHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        output_dir = os.path.join(app_data_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        super().__init__(*args, directory=output_dir, **kwargs)
        
    def log_message(self, format, *args):
        pass

def get_ec2_public_ip():
    global _ec2_public_ip
    if _ec2_public_ip: return _ec2_public_ip
    providers = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
        "https://checkip.amazonaws.com"
    ]
    for url in providers:
        try:
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                ip = res.text.strip()
                if ip and len(ip.split('.')) == 4:
                    _ec2_public_ip = ip
                    return ip
        except Exception:
            continue
    return None

def start_ec2_media_server():
    global _ec2_server_instance, _ec2_server_thread
    if _ec2_server_instance is not None:
        return SERVER_PORT

    try:
        _ec2_server_instance = ThreadingHTTPServer(("0.0.0.0", SERVER_PORT), QuietMediaHandler)
        _ec2_server_thread = threading.Thread(target=_ec2_server_instance.serve_forever, daemon=True)
        _ec2_server_thread.start()
        print(f"   > 🌐 EC2 Self-Hosted Media Server STARTED on Port {SERVER_PORT}")
        return SERVER_PORT
    except Exception as e:
        print(f"   > ⚠️ Self-hosted server notice on port {SERVER_PORT}: {e}")
        return SERVER_PORT

_ec2_tunnel_url = None

def get_cloudflare_tunnel_url(port=SERVER_PORT):
    global _ec2_tunnel_url
    if _ec2_tunnel_url:
        return _ec2_tunnel_url

    # Check if cloudflared is present or attempt download
    install_dir = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.join(install_dir, "cloudflared.exe")
    if not os.path.exists(exe_path):
        try:
            print("   > ⏬ Auto-fetching lightweight Cloudflare HTTPS Tunnel binary...")
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                with open(exe_path, "wb") as f:
                    f.write(res.content)
                print("   > ✅ Cloudflare HTTPS Tunnel binary acquired successfully!")
        except Exception as dl_err:
            pass

    if os.path.exists(exe_path):
        try:
            import subprocess
            cmd = f'"{exe_path}" tunnel --url http://127.0.0.1:{port}'
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="ignore")
            start_time = time.time()
            while time.time() - start_time < 8:
                line = proc.stdout.readline()
                if not line: break
                if "trycloudflare.com" in line:
                    for part in line.split():
                        if "trycloudflare.com" in part and part.startswith("https://"):
                            _ec2_tunnel_url = part.strip()
                            print(f"   > 🔒 Cloudflare HTTPS Tunnel ACTIVE: {_ec2_tunnel_url}")
                            return _ec2_tunnel_url
        except Exception as tunnel_err:
            print(f"   > ⚠️ Tunnel notice: {tunnel_err}")

    return None

def get_self_hosted_media_url(file_path):
    if not file_path or not os.path.exists(file_path):
        return None

    output_dir = os.path.join(app_data_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    rel_path = None
    try:
        abs_file = os.path.abspath(file_path)
        abs_output = os.path.abspath(output_dir)

        # Sanitize spaces in filenames to prevent Meta Error 2207077
        dir_name, base_name = os.path.split(abs_file)
        if " " in base_name:
            clean_name = base_name.replace(" ", "_")
            new_file_path = os.path.join(dir_name, clean_name)
            try:
                if os.path.exists(new_file_path):
                    os.remove(new_file_path)
                os.rename(abs_file, new_file_path)
                abs_file = new_file_path
                file_path = new_file_path
            except Exception as ren_err:
                shutil.copy2(abs_file, new_file_path)
                abs_file = new_file_path

        if abs_file.startswith(abs_output):
            rel_path = os.path.relpath(abs_file, abs_output).replace("\\", "/")
        else:
            web_dir = os.path.join(output_dir, "web_media")
            os.makedirs(web_dir, exist_ok=True)
            clean_basename = os.path.basename(abs_file).replace(" ", "_")
            dest = os.path.join(web_dir, clean_basename)
            shutil.copy2(abs_file, dest)
            rel_path = f"web_media/{clean_basename}"
    except Exception as copy_err:
        print(f"   > ⚠️ Self-host media copy notice: {copy_err}")
        return None

    start_ec2_media_server()

    import urllib.parse
    parts = rel_path.split("/")
    encoded_parts = [urllib.parse.quote(p) for p in parts]
    encoded_rel_path = "/".join(encoded_parts)

    # 1. Primary: Direct EC2 Public IP URL (Serves 100% raw media stream without Cloudflare Interstitial Warning)
    public_ip = get_ec2_public_ip()
    if public_ip:
        self_hosted_url = f"http://{public_ip}:{SERVER_PORT}/{encoded_rel_path}"
        print(f"   > 🚀 Self-Hosted EC2 Direct URL: {self_hosted_url}")
        return self_hosted_url

    # 2. Fallback: Cloudflare HTTPS Tunnel URL
    tunnel_url = get_cloudflare_tunnel_url(SERVER_PORT)
    if tunnel_url:
        https_url = f"{tunnel_url}/{encoded_rel_path}"
        print(f"   > 🔒 Self-Hosted HTTPS Tunnel Direct URL: {https_url}")
        return https_url

    return None

def get_temp_url(file_path):
    print("   > ☁️ Generating Direct Media URL for Meta Transfer...")

    # 1. PRIMARY (PERMANENT FIX): Self-Hosted EC2 HTTP Direct Stream (Zero 3rd Party Dependency)
    try:
        ec2_url = get_self_hosted_media_url(file_path)
        if ec2_url:
            return ec2_url
    except Exception as ec2_err:
        print(f"   > ⚠️ Self-hosted EC2 Media Server Notice: {ec2_err}")

    # 2. FALLBACK 1: Catbox.moe CDN
    raw_name = os.path.basename(file_path)
    name_base, ext = os.path.splitext(raw_name)
    clean_base = "".join([c for c in name_base if c.isalnum() or c in "_-"])
    if not clean_base or len(clean_base) < 4:
        filename = f"islamic_reels_media_{clean_base or 'asset'}{ext.lower()}"
    else:
        filename = f"islamic_reels_{clean_base}{ext.lower()}"

    try:
        with open(file_path, 'rb') as f:
            res = requests.post(
                "https://catbox.moe/user/api.php",
                data={'reqtype': 'fileupload'},
                files={'fileToUpload': (filename, f)},
                timeout=30
            )
            if res.status_code == 200 and res.text.strip().startswith("http"):
                url = res.text.strip()
                print(f"   > ✅ Uploaded to Catbox CDN: {url}")
                return url
            else:
                print(f"   > ⚠️ Catbox returned HTTP {res.status_code}: {res.text[:100]}")
    except Exception as e:
        print(f"   > ⚠️ Primary Host Notice (Catbox): {e}")

    # 3. FALLBACK 2: Litterbox CDN
    try:
        with open(file_path, 'rb') as f:
            res = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={'reqtype': 'fileupload', 'time': '1h'},
                files={'fileToUpload': (filename, f)},
                timeout=30
            )
            if res.status_code == 200 and res.text.strip().startswith("http"):
                url = res.text.strip()
                print(f"   > ✅ Uploaded to Litterbox CDN: {url}")
                return url
            else:
                print(f"   > ⚠️ Litterbox returned HTTP {res.status_code}: {res.text[:100]}")
    except Exception as e:
        print(f"   > ⚠️ Litterbox Host Notice: {e}")

    # 4. FALLBACK 3: Tmpfiles.org
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        with open(file_path, 'rb') as f:
            res = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={'file': (filename, f)},
                headers=headers,
                timeout=30
            ).json()
            if isinstance(res, dict) and res.get('status') == 'success' and 'data' in res and 'url' in res['data']:
                url = res['data']['url']
                direct_url = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                print(f"   > ✅ Uploaded to Tmpfiles: {direct_url}")
                return direct_url
    except Exception as e:
        print(f"   > ⚠️ Tmpfiles Host Notice: {e}")

    print("   > ❌ Temp Server Error: All temporary hosting services failed.")
    return None

def upload_to_facebook(video_path, caption, page_id, token):
    print(f"   > 🌐 Uploading to Facebook Page: {page_id}...")
    url = f"https://graph.facebook.com/v19.0/{page_id}/videos"
    try:
        with open(video_path, 'rb') as video_file:
            payload = {'access_token': token, 'description': caption}
            files = {'source': video_file}
            res = requests.post(url, data=payload, files=files).json()
            if 'id' in res:
                print(f"   > ✅ FB Upload Success! Video ID: {res['id']}")
            else:
                print(f"   > ❌ FB Upload Error: {res}")
    except Exception as e:
        print(f"   > ❌ FB Exception: {e}")

def upload_cover_image_to_cdn(image_path):
    """
    Stages custom cover thumbnail image to direct HTTPS image CDN (FreeImageHost / Litterbox)
    for Instagram Reels payload.
    """
    if not image_path or not os.path.exists(image_path):
        return None

    # 1. Primary: FreeImageHost CDN API (Returns direct static https://iili.io/... URL)
    try:
        with open(image_path, 'rb') as f:
            res = requests.post(
                "https://freeimage.host/api/1/upload",
                data={'key': '6d207e02198a847aa98d0a2a901485a5', 'action': 'upload', 'format': 'json'},
                files={'source': f},
                timeout=15
            ).json()
            if res.get('status_code') == 200 and 'image' in res and 'url' in res['image']:
                url = res['image']['url']
                print(f"   > 🖼️ Staged custom cover thumbnail to FreeImageHost CDN: {url}")
                return url
    except Exception as e:
        print(f"   > ⚠️ FreeImageHost cover upload notice: {e}")

    # 2. Fallback: Litterbox CDN API
    try:
        raw_name = os.path.basename(image_path)
        with open(image_path, 'rb') as f:
            res = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={'reqtype': 'fileupload', 'time': '1h'},
                files={'fileToUpload': (f"quran_cover_{raw_name}", f)},
                timeout=15
            )
            if res.status_code == 200 and res.text.strip().startswith("http"):
                url = res.text.strip()
                print(f"   > 🖼️ Staged custom cover thumbnail to Litterbox CDN: {url}")
                return url
    except Exception as e:
        print(f"   > ⚠️ Litterbox cover upload notice: {e}")

    return None

def upload_to_instagram(video_url, caption, ig_id=None, token=None, cover_url=None, thumbnail_path=None, local_raw_path=None):
    """
    Direct Meta Binary Resumable Upload Engine (rupload.facebook.com)
    - Zero public URL dependency!
    - Zero 3rd party host dependency!
    - Zero open inbound port dependency!
    - 100% Direct binary stream to Meta Graph API!
    """
    actual_file_path = None
    if local_raw_path and os.path.exists(local_raw_path):
        actual_file_path = local_raw_path
    elif video_url and os.path.exists(video_url):
        actual_file_path = video_url

    # Support client.clip_upload-like calls with positional/keyword parameters
    if ig_id and isinstance(ig_id, str) and (ig_id.endswith(".jpg") or ig_id.endswith(".png") or os.path.exists(ig_id)):
        thumbnail_path = ig_id
        ig_id = None

    # Load credentials if missing
    if not ig_id or not token:
        import json
        settings_path = os.path.join(app_data_dir, "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings_data = json.load(f)
                    for profile_settings in settings_data.values():
                        if not ig_id and profile_settings.get("ig_account_id"):
                            ig_id = profile_settings.get("ig_account_id")
                        if not token and profile_settings.get("fb_token"):
                            token = profile_settings.get("fb_token")
            except Exception as e:
                print(f"   > ⚠️ Failed to load settings.json to resolve IG credentials: {e}")

    if not ig_id or not token:
        print("   > ❌ Instagram upload failed: Missing ig_account_id or fb_token credentials.")
        return False

    if not actual_file_path or not os.path.exists(actual_file_path):
        print(f"   > ❌ Instagram upload error: Local video file not found at: {actual_file_path or video_url}")
        return False

    # Auto-discover matching custom cover photo if thumbnail_path is not explicitly provided
    if not thumbnail_path and actual_file_path:
        base_no_ext, _ = os.path.splitext(actual_file_path)
        possible_thumbs = [
            f"{base_no_ext}.jpg",
            f"{base_no_ext}.png",
            f"{base_no_ext}_cover.jpg",
            f"{base_no_ext}_cover.png",
        ]
        parent_dir = os.path.dirname(actual_file_path)
        if os.path.exists(parent_dir):
            img_files = [os.path.join(parent_dir, f) for f in os.listdir(parent_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if img_files:
                img_files.sort(key=os.path.getmtime, reverse=True)
                possible_thumbs.append(img_files[0])

        for p in possible_thumbs:
            if os.path.exists(p):
                thumbnail_path = p
                print(f"   > 🔍 Auto-discovered custom cover photo image: {os.path.basename(p)}")
                break

    # Stage custom cover thumbnail if provided
    if not cover_url and thumbnail_path and os.path.exists(thumbnail_path):
        cover_url = upload_cover_image_to_cdn(thumbnail_path)

    file_size = os.path.getsize(actual_file_path)
    print(f"   > 🌐 Connecting to Meta Direct Resumable Server (rupload.facebook.com)...")
    print(f"   > 📦 Direct Binary Payload: {os.path.basename(actual_file_path)} ({file_size} bytes)")

    try:
        # Step 1: Create Direct Resumable Media Container
        url = f"https://graph.facebook.com/v19.0/{ig_id}/media"
        payload = {
            'access_token': token,
            'media_type': 'REELS',
            'upload_type': 'resumable',
            'caption': caption
        }

        # Attach custom cover thumbnail URL if available
        if cover_url:
            payload['cover_url'] = cover_url
            print(f"   > 🖼️ Attached custom cover thumbnail URL to IG Container payload: {cover_url}")

        res = requests.post(url, data=payload).json()

        if 'id' in res and 'uri' in res:
            container_id = res['id']
            upload_uri = res['uri']
            print(f"   > ✅ IG Resumable Container Created! ID: {container_id}")
            print(f"   > 🚀 Streaming Raw Video Bytes directly to Meta's Upload Endpoint...")

            headers = {
                'Authorization': f'OAuth {token}',
                'offset': '0',
                'file_size': str(file_size),
                'Content-Type': 'application/octet-stream'
            }

            with open(actual_file_path, 'rb') as f:
                up_res = requests.post(upload_uri, headers=headers, data=f).json()

            if up_res.get('success'):
                print(f"   > ✅ Direct Binary Stream Complete! Processing reel with Meta...")
            else:
                print(f"   > ⚠️ Direct Upload Stream Response: {up_res}")

            # Step 2: Poll IG Processing Status
            is_ready = False
            status_url = f"https://graph.facebook.com/v19.0/{container_id}?fields=status_code,status&access_token={token}"

            for attempt in range(15):
                time.sleep(5)
                status_res = requests.get(status_url).json()
                status_code = status_res.get('status_code', '')
                if status_code == 'FINISHED':
                    print("   > 🟢 IG Video Processing Complete! Publishing now...")
                    is_ready = True
                    break
                elif status_code == 'ERROR':
                    err_details = status_res.get('status', status_res)
                    print(f"   > ❌ IG Processing Failed. Meta Status: {err_details}")
                    if os.path.exists(actual_file_path):
                        try:
                            print(f"   > 🧹 Auto-cleaning failed render file: {os.path.basename(actual_file_path)}")
                            os.remove(actual_file_path)
                        except Exception: pass
                    return False

            if not is_ready:
                print("   > ⏱️ IG Processing Timed Out after 15 attempts.")
                return False

            # Step 3: Publish Reel with Cover URL
            publish_url = f"https://graph.facebook.com/v19.0/{ig_id}/media_publish"
            publish_payload = {'creation_id': container_id, 'access_token': token}
            if cover_url:
                publish_payload['cover_url'] = cover_url
                print(f"   > 🖼️ Attached custom cover thumbnail URL to IG Publish payload.")
            pub_res = requests.post(publish_url, data=publish_payload).json()
            if 'id' in pub_res:
                print(f"   > 🎉 IG Reel Published Successfully! Reel Post ID: {pub_res['id']}")
                return True
            else:
                print(f"   > ❌ IG Publish Error: {pub_res}")
                return False
        else:
            print(f"   > ❌ IG Resumable Container Creation Error: {res}")
            return False
    except Exception as e:
        print(f"   > ❌ IG Direct Resumable Upload Exception: {e}")
        return False

def get_authenticated_youtube_service(token_path):
    if not token_path:
        print("   > ❌ YT Error: No token path provided!")
        return None

    try:
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        print("   > ❌ YT Error: Missing required Google Libraries!")
        return None

    SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']
    creds = None

    if os.path.exists(token_path):
        print("   > ✅ Existing token found. Attempting login...")
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            pass
    else:
        print("   > ⚠️ No token found in this vault. A browser window will open to authenticate.")
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token: 
            try:
                print("   > 🔄 Token expired. Refreshing automatically...")
                creds.refresh(Request())
            except Exception:
                creds = None
        
        if not creds:
            profile_dir = os.path.dirname(token_path) if token_path else ""
            client_secret_path = os.path.join(profile_dir, 'client_secret.json') if profile_dir else 'client_secret.json'
            
            if not os.path.exists(client_secret_path):
                main_secret_path = os.path.join(install_dir, 'client_secret.json')
                if os.path.exists(main_secret_path):
                    client_secret_path = main_secret_path
                elif os.path.exists('client_secret.json'):
                    client_secret_path = 'client_secret.json'
                else:
                    print(f"   > ❌ YT Error: Missing client_secret.json in profile vault ({client_secret_path}) or main directory ({main_secret_path})!")
                    return None
            print("[⚠️] ACTION REQUIRED: If the browser does not open automatically, copy the URL below and paste it into a browser INSIDE THIS RDP SESSION. The server will wait 24 hours (86400 seconds) for you to complete this.")
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0, prompt='select_account consent', timeout_seconds=86400)
            
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(os.path.abspath(token_path)), exist_ok=True)
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())
        print("   > 💾 New OAuth Token saved securely to profile vault.")

    try:
        youtube = build('youtube', 'v3', credentials=creds)
        return youtube
    except Exception as e:
        print(f"   > ❌ YT build service exception: {e}")
        return None

def upload_to_youtube(video_path, title, description, token_path, thumbnail_path=None):
    print(f"   > 🌐 Initiating YouTube Upload Module...")
    print(f"   > 🔐 Target Token Vault: {token_path}")
    
    youtube = get_authenticated_youtube_service(token_path)
    if not youtube:
        return

    try:
        try:
            channel_res = youtube.channels().list(part='snippet', mine=True).execute()
            if channel_res.get('items'):
                channel_name = channel_res['items'][0]['snippet']['title']
                print(f"   > 📺 VERIFIED CHANNEL LOGIN: Logged in as '{channel_name}'")
            else:
                print("   > 📺 VERIFIED CHANNEL LOGIN: Unknown Channel")
                
        except Exception as e:
            print(f"   > 🛑 FATAL AUTHENTICATION ERROR: Old or corrupted token detected!")
            print(f"   > 🗑️ Auto-deleting the bad token from: {token_path}")
            if os.path.exists(token_path):
                os.remove(token_path)
            print("   > ❌ UPLOAD ABORTED to prevent posting to the wrong channel.")
            print("   > 🔄 ACTION REQUIRED: Please click 'Manual Upload' again. The browser WILL open this time!")
            return 

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': ['Quran', 'IslamicReels', 'Shorts', 'Allah', 'Deen'],
                'categoryId': '22'
            },
            'status': {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False}
        }
        from googleapiclient.http import MediaFileUpload
        import socket
        import time
        
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        print("   > 🚀 Pushing video file to YouTube Servers...")
        request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
        
        response = None
        retries = 0
        max_retries = 3
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    print(f"      [+] YouTube Upload Progress: {int(status.progress() * 100)}%")
            except (ConnectionResetError, socket.error, Exception) as e:
                retries += 1
                if retries > max_retries:
                    print(f"      [!] YouTube Upload timed out or failed {max_retries} times. Aborting retry loop to prevent hang.")
                    raise RuntimeError(f"YouTube upload failed after {max_retries} retries: {e}")
                print(f"      [!] Network connection reset detected ({e}). Re-establishing connection in 30 seconds (Retry {retries}/{max_retries})...")
                time.sleep(30)
                continue
                
        if response and 'id' in response:
            video_id = response['id']
            print(f"   > ✅ YT Upload Success! Video ID: {video_id}")
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    print(f"   > 🖼️ Uploading custom thumbnail to YouTube video ({video_id})...")
                    thumb_media = MediaFileUpload(thumbnail_path)
                    youtube.thumbnails().set(videoId=video_id, media_body=thumb_media).execute()
                    print(f"   > ✅ YouTube Custom Thumbnail set successfully!")
                except Exception as thumb_err:
                    print(f"   > ⚠️ YouTube Thumbnail Notice: {thumb_err}")
        else:
            print("   > ❌ YT Upload Failed: No response ID received.")
        
    except Exception as e:
        print(f"   > ❌ YT Upload Exception: {e}")

def run_all_uploads(video_path, quran_data, settings, abort_check=None, thumbnail_path=None):
    if not os.path.exists(video_path): return
        
    reciter_name = settings.get("reciter_name", "Unknown Reciter")
    caption = build_caption(quran_data, settings.get("cta_text", ""), reciter_name)
    
    print("\n========================================")
    print(f"🚀 INITIATING SOCIAL MEDIA UPLOADS...")
    print(f"📡 Meta Server Time: {get_meta_server_time()[0]}")
    print("========================================")

    # Load global settings for logging comparison
    global_enable_ig = settings.get("enable_ig", True)
    global_enable_fb = settings.get("enable_fb", True)
    global_enable_yt = settings.get("enable_yt", True)
    
    current_profile = settings.get("current_profile_name")
    if current_profile:
        settings_path = os.path.join(app_data_dir, "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    s_data = json.load(f)
                    prof_data = s_data.get(current_profile)
                    if prof_data:
                        global_enable_ig = prof_data.get("enable_ig", True)
                        global_enable_fb = prof_data.get("enable_fb", True)
                        global_enable_yt = prof_data.get("enable_yt", True)
            except:
                pass

    # Staging Engine for Cover Photo / Thumbnail
    local_thumb_file = None
    if thumbnail_path and os.path.exists(thumbnail_path):
        local_thumb_file = thumbnail_path
    else:
        thumb_folder = os.path.join(install_dir, "reciter_photos")
        if os.path.exists(thumb_folder):
            import glob, random
            photos = glob.glob(os.path.join(thumb_folder, "*.jpg")) + glob.glob(os.path.join(thumb_folder, "*.png"))
            if photos:
                local_thumb_file = random.choice(photos)
                print(f"   > 🖼️ Auto-selected cover photo from reciter_photos: {os.path.basename(local_thumb_file)}")

    thumb_url = None
    if local_thumb_file and os.path.exists(local_thumb_file):
        thumb_url = upload_cover_image_to_cdn(local_thumb_file)

    # 1. Facebook
    if abort_check and not abort_check(): return
    if settings.get("enable_fb", True):
        if settings.get("fb_page_id") and settings.get("fb_token"):
            upload_to_facebook(video_path, caption, settings["fb_page_id"], settings["fb_token"])
        else:
            print("   > ⏭️ Skipping Facebook (Missing Token or Page ID)")
    else:
        if not global_enable_fb:
            print("   > ⏭️ Skipping Facebook (Turned off in settings)")

    # 2. Instagram (Direct Meta Binary Stream)
    if abort_check and not abort_check(): return
    if settings.get("enable_ig", True):
        if settings.get("ig_account_id") and settings.get("fb_token"):
            upload_to_instagram(video_path, caption, settings["ig_account_id"], settings["fb_token"], cover_url=thumb_url, thumbnail_path=thumbnail_path, local_raw_path=video_path)
        else:
            print("   > ⏭️ Skipping Instagram (Missing Token or IG ID)")
    else:
        if not global_enable_ig:
            print("   > ⏭️ Skipping Instagram (Turned off in settings)")

    # 3. YouTube
    if abort_check and not abort_check(): return
    if settings.get("enable_yt", True):
        clean_yt_ref = quran_data['reference'].split("| [BG:")[0].strip()
        yt_title = f"Beautiful Quran Recitation - {clean_yt_ref} ✨"
        
        current_profile = settings.get("current_profile_name", "Main Page")
        profile_yt_token = os.path.join(install_dir, "credentials", current_profile, "token.json")
        
        upload_to_youtube(video_path, yt_title, caption, profile_yt_token, thumbnail_path=local_thumb_file)
    else:
        if not global_enable_yt:
            print("   > ⏭️ Skipping YouTube (Turned off in settings)")

    print("========================================")
