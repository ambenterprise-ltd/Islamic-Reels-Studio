import os
import sys

# --- GLOBAL ENCODING FIX ---
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
# ---------------------------

import glob
import shutil
import socket
import requests

def run_environment_precheck(verbose=True):
    """
    Performs a rapid diagnostic precheck on system libraries, assets, browser renderers,
    network connectivity, and credentials before initiating video composition.
    """
    if verbose:
        print("\n======================================================================")
        print("🔍 RUNNING ENVIRONMENT & ASSETS PRECHECK...")
        print("======================================================================")

    warnings = []
    errors = []
    passed_items = []

    # 1. Check Python Libraries
    required_libraries = [
        ("customtkinter", "CustomTkinter GUI Library"),
        ("PIL", "Pillow Image Processing"),
        ("moviepy", "MoviePy Video Editing"),
        ("html2image", "Html2Image Subtitle Renderer"),
        ("edge_tts", "Edge TTS Audio Engine"),
        ("faster_whisper", "Faster Whisper AI Alignment"),
        ("pedalboard", "Pedalboard Audio FX"),
        ("googleapiclient", "Google API Client (YouTube)"),
        ("gspread", "GSpread Google Sheets Logger"),
        ("requests", "Requests HTTP Client")
    ]

    for mod_name, label in required_libraries:
        try:
            __import__(mod_name)
            passed_items.append(f"Library: {label}")
        except ImportError:
            errors.append(f"Missing Required Library '{mod_name}' ({label}). Install via: pip install {mod_name}")

    # 2. Check Browser Executable for HTML Subtitle Rendering
    chrome_path_1 = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    chrome_path_2 = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    browser_found = False
    for b_path in [chrome_path_1, chrome_path_2, edge_path]:
        if os.path.exists(b_path):
            browser_found = True
            passed_items.append(f"Browser Renderer: {os.path.basename(b_path)}")
            break

    if not browser_found:
        warnings.append("No Google Chrome or Microsoft Edge executable found in standard Windows locations. Html2Image subtitle rendering may fail.")

    # 3. Check Folders and Assets
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    bg_candidates = [os.path.join(base_dir, "bg"), os.path.join(base_dir, "backgrounds")]
    bg_files = []
    for b_dir in bg_candidates:
        if os.path.exists(b_dir):
            for ext in ["*.mp4", "*.MP4", "*.mov", "*.MOV", "*.mkv", "*.MKV"]:
                bg_files.extend(glob.glob(os.path.join(b_dir, ext)))
                bg_files.extend(glob.glob(os.path.join(b_dir, "**", ext), recursive=True))

    bg_files = list(set(os.path.normpath(f) for f in bg_files))
    if bg_files:
        passed_items.append(f"Background Assets: Found {len(bg_files)} video clip(s)")
    else:
        warnings.append("Background directory ('bg' or 'backgrounds') contains no video clips. Dark failsafe background will be used if needed.")

    reciter_dir = os.path.join(base_dir, "reciter_clips")
    if os.path.exists(reciter_dir):
        rec_files = []
        for ext in ["*.mp4", "*.MP4", "*.mov", "*.MOV"]:
            rec_files.extend(glob.glob(os.path.join(reciter_dir, ext)))
        if rec_files:
            passed_items.append(f"Reciter Hook Clips: Found {len(rec_files)} clip(s)")

    creds_dir = os.path.join(base_dir, "credentials")
    if os.path.exists(creds_dir):
        profiles = [d for d in os.listdir(creds_dir) if os.path.isdir(os.path.join(creds_dir, d))]
        passed_items.append(f"Credentials Vault: Found {len(profiles)} profile folder(s) ({', '.join(profiles) if profiles else 'None'})")
        for prof in profiles:
            token_file = os.path.join(creds_dir, prof, "token.json")
            if os.path.exists(token_file):
                passed_items.append(f"YouTube Token [{prof}]: token.json file present")
            else:
                warnings.append(f"YouTube Token [{prof}]: token.json missing (browser auth will trigger before compiling)")
    else:
        warnings.append(f"Credentials directory '{creds_dir}' does not exist yet.")

    # 4. Rapid Network Check
    try:
        res = requests.get("https://api.alquran.cloud/v1/quran/quran-uthmani", timeout=4)
        if res.status_code == 200:
            passed_items.append("Network API: Quran Cloud API connection verified")
        else:
            warnings.append(f"Network API: Quran API returned HTTP {res.status_code}")
    except Exception as net_err:
        warnings.append(f"Network API: Could not reach Quran Cloud API ({net_err}). Ensure internet connection is active.")

    # 5. Cloud Media Hosting Precheck (Catbox / Litterbox CDN Upload Test)
    try:
        from social_engine import get_temp_url
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00")
            tmp_path = tmp.name

        test_url = get_temp_url(tmp_path)
        if os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except: pass

        if test_url and test_url.startswith("http"):
            passed_items.append(f"Cloud Hosting API: Verified live media upload transfer ({test_url})")
        else:
            warnings.append("Cloud Hosting API: Temporary media upload test failed. Instagram upload may be affected.")
    except Exception as host_err:
        warnings.append(f"Cloud Hosting API: Temp host test notice: {host_err}")

    # 6. Output Summary Report
    if verbose:
        print(f"✅ PASSED CHECKS: {len(passed_items)} item(s) verified.")
        for item in passed_items:
            print(f"   > [OK] {item}")
        
        if warnings:
            print(f"\n⚠️ WARNINGS: {len(warnings)} potential non-fatal notice(s):")
            for w in warnings:
                print(f"   > [WARN] {w}")

        if errors:
            print(f"\n❌ CRITICAL ERRORS: {len(errors)} missing requirement(s):")
            for e in errors:
                print(f"   > [FAIL] {e}")
            print("======================================================================\n")
            return False
        else:
            print("======================================================================\n")
            return True

    return len(errors) == 0

if __name__ == "__main__":
    success = run_environment_precheck(verbose=True)
    if not success:
        sys.exit(1)
