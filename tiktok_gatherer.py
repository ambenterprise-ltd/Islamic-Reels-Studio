import os
import sys
import json
import glob
import time
from datetime import datetime

# Global encoding fix for Windows console
if sys.platform.startswith('win'):
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        try: sys.stdout.reconfigure(encoding='utf-8')
        except Exception: pass
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        try: sys.stderr.reconfigure(encoding='utf-8')
        except Exception: pass

import yt_dlp

app_data_dir = os.path.join(os.environ.get('APPDATA', ''), 'IslamicReelsStudio')
os.makedirs(app_data_dir, exist_ok=True)

LEDGER_FILE = os.path.join(app_data_dir, "posted_tiktoks.json")
DEFAULT_OUTPUT_DIR = os.path.join(app_data_dir, "output", "tiktok")
os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

def _get_impersonate_target():
    """Attempts to configure Chrome TLS impersonation for yt-dlp to bypass TikTok anti-bot shields."""
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget
        return ImpersonateTarget.from_str('chrome')
    except Exception:
        return 'chrome'

# ==========================================
# --- LOCAL HISTORY LEDGER ---
# ==========================================

def load_posted_ids():
    """
    Reads posted_tiktoks.json and returns a Python set of previously posted video IDs.
    If the file does not exist, return an empty set.
    """
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {str(vid).strip() for vid in data if str(vid).strip()}
                elif isinstance(data, dict):
                    return {str(k).strip() for k in data.keys() if str(k).strip()}
        except Exception as e:
            print(f"   > ⚠️ Notice reading TikTok ledger ({e}). Starting fresh ledger.")
    return set()

# Backward compatible alias
load_posted_history = load_posted_ids
get_posted_tiktoks = load_posted_ids

def is_tiktok_posted(video_id):
    """Checks if a given video ID has already been posted."""
    if not video_id:
        return False
    return str(video_id).strip() in load_posted_ids()

def record_posted_id(video_id, metadata=None):
    """
    Appends the new video_id to posted_tiktoks.json with formatting and saves it.
    """
    if not video_id:
        return False
    str_id = str(video_id).strip()
    if not str_id:
        return False

    try:
        os.makedirs(os.path.dirname(LEDGER_FILE), exist_ok=True)
        posted_list = []
        if os.path.exists(LEDGER_FILE):
            try:
                with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        posted_list = [str(x).strip() for x in loaded if str(x).strip()]
                    elif isinstance(loaded, dict):
                        posted_list = [str(k).strip() for k in loaded.keys() if str(k).strip()]
            except Exception:
                posted_list = []

        if str_id not in posted_list:
            posted_list.append(str_id)

        with open(LEDGER_FILE, "w", encoding="utf-8") as f:
            json.dump(posted_list, f, indent=2, ensure_ascii=False)

        print(f"   > 📋 [LEDGER] Marked TikTok ID '{str_id}' as posted in history ledger.")
        return True
    except Exception as e:
        print(f"   > ❌ [LEDGER] Failed to save TikTok history ledger: {e}")
        return False

# Backward compatible alias
mark_tiktok_posted = record_posted_id

# ==========================================
# --- PROFILE RESOLUTION & SCRAPING ---
# ==========================================

def normalize_tiktok_url(target):
    """Converts a handle, username, or URL into a valid TikTok profile URL."""
    cleaned = target.strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    
    # Strip leading @ symbols if present
    username = cleaned.lstrip("@").strip()
    return f"https://www.tiktok.com/@{username}"

def ensure_vertical_for_shorts(video_path):
    """
    Verifies aspect ratio of video. If height >= width, it is already vertical/square (standard Short).
    If width > height (landscape video), converts it to 1080x1920 vertical 9:16 with black padding
    to guarantee YouTube routes it to the Shorts shelf.
    """
    if not video_path or not os.path.exists(video_path):
        return video_path
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return video_path
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        cap.release()
        
        if h >= w:
            return video_path
            
        print(f"   > 🔄 Video is horizontal ({int(w)}x{int(h)}). Converting to 9:16 vertical (1080x1920) for YouTube Shorts...")
        from moviepy.editor import VideoFileClip, CompositeVideoClip, ColorClip
        clip = VideoFileClip(video_path)
        target_w, target_h = 1080, 1920
        scale = target_w / clip.w
        scaled = clip.resize(scale)
        bg = ColorClip(size=(target_w, target_h), color=(0, 0, 0), duration=clip.duration)
        final = CompositeVideoClip([bg, scaled.set_position("center")])
        out_v = video_path.replace(".mp4", "_vert.mp4")
        final.write_videofile(out_v, codec="libx264", audio_codec="aac", fps=clip.fps or 30, verbose=False, logger=None)
        clip.close()
        final.close()
        if os.path.exists(out_v) and os.path.getsize(out_v) > 1000:
            return out_v
    except Exception as e:
        print(f"   > ⚠️ Vertical aspect check notice: {e}")
    return video_path

def fetch_top_tiktok_video(username, sort_by="Most Viewed (Viral)", min_views=100000, output_dir=None, max_scan=50):
    """
    Scrapes a target TikTok profile, filters unposted videos by min_views threshold,
    sorts them according to strategy, downloads the top pick in HD without watermarks,
    and returns metadata for social publishing.
    
    Returns:
        dict: {"video_path": str, "id": str, "title": str, "caption": str} or None
    """
    if not username or not username.strip():
        print("   > ❌ TikTok Scraper Error: Target username is empty.")
        return None

    target_url = normalize_tiktok_url(username)
    clean_user = username.strip().lstrip("@")
    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    # 1. Load the posted IDs set at the very beginning
    posted_ids = load_posted_ids()

    print(f"\n========================================================")
    print(f"🎵 TIKTOK VIRAL REPURPOSER: Scanning @{clean_user}...")
    print(f"   > 🎯 Target URL: {target_url}")
    print(f"   > 📊 Strategy: {sort_by} | Min Views Threshold: {min_views:,}")
    print(f"   > 📋 Previously Posted IDs Loaded: {len(posted_ids)}")
    print(f"========================================================")

    # 2. Configure yt-dlp Profile Extractor (Scan 50 items for a deep pool of fresh videos)
    impersonate_target = _get_impersonate_target()
    scan_limit = max(int(max_scan or 50), 50)
    ydl_opts_scan = {
        'extract_flat': True,
        'playlist_items': f'1-{scan_limit}',
        'playlistend': scan_limit,
        'quiet': True,
        'no_warnings': True,
    }
    if impersonate_target:
        ydl_opts_scan['impersonate'] = impersonate_target

    try:
        with yt_dlp.YoutubeDL(ydl_opts_scan) as ydl:
            print("   > 📡 Querying TikTok user feed via TLS browser emulation (1-50 items)...")
            info = ydl.extract_info(target_url, download=False)
    except Exception as e:
        print(f"   > ❌ TikTok Profile Extraction Error: {e}")
        return None

    entries = info.get('entries', []) if info else []
    if not entries:
        print(f"   > ⚠️ No video entries found for TikTok profile @{clean_user}.")
        return None

    print(f"   > 🔍 Successfully fetched {len(entries)} candidate videos from feed.")

    # 3. Duplicate Filter: Inspect candidates and immediately skip any already posted
    unposted_entries = []
    for entry in entries:
        v_id = str(entry.get('id', '') or '').strip()
        # DUPLICATE GUARD: If v_id in posted_ids, SKIP IT immediately
        if not v_id or v_id in posted_ids:
            continue
        unposted_entries.append(entry)

    print(f"   > 📋 Filtered candidate pool: {len(unposted_entries)} unposted videos remaining.")
    if not unposted_entries:
        print("   > ⚠️ All recent videos from this creator have already been posted.")
        return None

    # 3. STRICT NATIVE DURATION FILTER (15s <= duration <= 54s) & Min Views Threshold
    eligible_entries = []
    try:
        min_views_int = int(min_views)
    except Exception:
        min_views_int = 0

    for entry in unposted_entries:
        # STRICT VERTICAL / SQUARE RATIO GUARD:
        # YouTube Shorts REQUIRE vertical (9:16) or square (1:1) aspect ratio (height >= width).
        # Discard horizontal/landscape candidates (width > height)
        w = entry.get('width')
        h = entry.get('height')
        if w is not None and h is not None:
            try:
                if float(w) > float(h):
                    print(f"   > ⏭️ Discarding candidate {entry.get('id')}: Horizontal aspect ratio ({int(w)}x{int(h)}) cannot be a YouTube Short.")
                    continue
            except Exception:
                pass

        # STRICT NATIVE DURATION FILTER: Discard any video outside 15s - 54s window
        dur = entry.get('duration')
        if dur is not None:
            try:
                dur_val = float(dur)
                if dur_val < 15.0 or dur_val > 54.0:
                    continue
            except Exception:
                pass

        views = entry.get('view_count')
        if views is not None and views < min_views_int:
            continue

        eligible_entries.append(entry)

    if not eligible_entries:
        print(f"   > ⚠️ No unposted videos qualified under both strict duration (15s-54s) and min_views ({min_views_int:,}) criteria.")
        return None

    # 4. Sort Candidates Based on Strategy
    if sort_by == "Most Liked":
        eligible_entries.sort(key=lambda x: x.get('like_count') or 0, reverse=True)
    elif sort_by == "Latest Uploads":
        eligible_entries.sort(key=lambda x: x.get('timestamp') or 0, reverse=True)
    else:
        # Default: "Most Viewed (Viral)"
        eligible_entries.sort(key=lambda x: x.get('view_count') or 0, reverse=True)

    chosen = eligible_entries[0]
    chosen_id = str(chosen.get('id'))
    chosen_url = chosen.get('url') or f"https://www.tiktok.com/@{clean_user}/video/{chosen_id}"
    chosen_views = chosen.get('view_count') or 0
    chosen_likes = chosen.get('like_count') or 0
    chosen_title = (chosen.get('title') or f"Viral Clip from @{clean_user}").strip()

    print(f"\n   > 🏆 SELECTED VIRAL CANDIDATE:")
    print(f"      • Video ID: {chosen_id}")
    print(f"      • Views: {chosen_views:,} | Likes: {chosen_likes:,}")
    print(f"      • Title: {chosen_title[:60]}...")
    print(f"      • Direct URL: {chosen_url}")

    # 5. Download Video in Highest MP4 Quality Without Watermarks (100% UNTOUCHED, ZERO TRIMMING)
    print("\n   > ⏬ Initiating clean watermark-free download (Zero Trimming Rule)...")
    target_filename = f"tiktok_{chosen_id}.mp4"
    target_filepath = os.path.join(out_dir, target_filename)

    # If already downloaded previously but not yet posted
    if os.path.exists(target_filepath) and os.path.getsize(target_filepath) > 10000:
        print(f"   > ⚡ Existing download detected at: {target_filepath}")
        target_filepath = ensure_vertical_for_shorts(target_filepath)
        short_title = f"{chosen_title[:88].strip()} #Shorts" if "#Shorts" not in chosen_title and "#shorts" not in chosen_title else chosen_title
        return {
            "video_path": target_filepath,
            "id": chosen_id,
            "title": short_title,
            "caption": f"{chosen_title}\n\n#Shorts #Quran #IslamicReels #Viral #Reels"
        }

    ydl_opts_dl = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(out_dir, f'tiktok_{chosen_id}.%(ext)s'),
        'quiet': False,
        'no_warnings': True,
        'overwrites': True,
    }
    if impersonate_target:
        ydl_opts_dl['impersonate'] = impersonate_target

    try:
        with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
            full_info = ydl.extract_info(chosen_url, download=True)
            actual_file = ydl.prepare_filename(full_info)
            
            # Post-download check: verify duration strictly <= 54s if available
            post_dur = full_info.get('duration')
            if post_dur is not None:
                try:
                    if float(post_dur) < 15.0 or float(post_dur) > 54.0:
                        print(f"   > 🛑 Post-Download Duration Guard: Video duration ({float(post_dur):.1f}s) violated 15s-54s window. Discarding.")
                        if os.path.exists(actual_file): os.remove(actual_file)
                        return None
                except Exception:
                    pass

            # Ensure file exists or check if extension changed (e.g., .mp4)
            if not os.path.exists(actual_file):
                matching = glob.glob(os.path.join(out_dir, f"*{chosen_id}*"))
                if matching:
                    actual_file = matching[0]

            if not os.path.exists(actual_file):
                print(f"   > ❌ Download completed but file was not found on disk!")
                return None

            # Ensure video is vertical 9:16 for YouTube Shorts
            actual_file = ensure_vertical_for_shorts(actual_file)

            file_size_mb = os.path.getsize(actual_file) / (1024 * 1024)
            print(f"   > ✅ Download Success! File: {os.path.basename(actual_file)} ({file_size_mb:.2f} MB)")

            short_title = f"{chosen_title[:88].strip()} #Shorts" if "#Shorts" not in chosen_title and "#shorts" not in chosen_title else chosen_title
            caption = f"{chosen_title}\n\n#Shorts #Quran #IslamicReels #Viral #Reels"

            return {
                "video_path": actual_file,
                "id": chosen_id,
                "title": short_title,
                "caption": caption
            }
    except Exception as dl_err:
        print(f"   > ❌ TikTok Download Failed: {dl_err}")
        return None

def _format_caption(raw_text, username, video_id):
    """Formats a clean, engaging social media caption retaining hashtags and giving creator credit."""
    clean_text = raw_text.strip()
    caption = f"{clean_text}\n\n"
    caption += f"👤 Creator Credit: @{username}\n"
    caption += f"📌 Original Source: TikTok (ID: {video_id})\n\n"
    
    # Add general viral hashtags if none present
    if "#" not in clean_text:
        caption += "#viral #trending #reels #shorts #tiktok\n"
        
    return caption
