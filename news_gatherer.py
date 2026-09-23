import requests
import random
import os
import glob
import sys
import json
# MoviePy VideoFileClip is imported lazily inside get_video_and_duration only if needed

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

app_data_dir = os.path.join(os.environ.get('APPDATA', ''), 'IslamicReelsStudio')
RECENT_BGS_FILE = os.path.join(app_data_dir, "recent_bgs.json")

def get_recent_bgs():
    if os.path.exists(RECENT_BGS_FILE):
        try:
            with open(RECENT_BGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def record_used_bg(video_path):
    if not video_path:
        return
    try:
        os.makedirs(app_data_dir, exist_ok=True)
        history = get_recent_bgs()
        norm_path = os.path.normpath(video_path)
        if norm_path in history:
            history.remove(norm_path)
        history.append(norm_path)
        if len(history) > 6:
            history = history[-6:]
        with open(RECENT_BGS_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f)
    except Exception:
        pass

def get_semantic_video(english_text, groq_keys=None):
    if not groq_keys:
        print("   > ⚠️ No Groq API keys provided. Falling back to 'asthatic'.")
        return "asthatic"

    clean_keys = [k.strip() for k in groq_keys if isinstance(k, str) and k.strip()]
    if not clean_keys:
        print("   > ⚠️ Groq key list is empty. Falling back to 'asthatic'.")
        return "asthatic"

    selected_key = random.choice(clean_keys)
    masked_key = selected_key[:8] + "..." + selected_key[-4:] if len(selected_key) > 12 else "***"
    print(f"   > [AI] Querying Groq LLM Router (groq/compound-mini) via key [{masked_key}]...")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {selected_key}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "You are a routing agent for a Quran video generator. I will give you the English translation of a verse. "
        "You must categorize it into ONE of these exact categories based on its meaning. \n"
        "EXACT FILES (Tier 1 - Highest Priority for specific themes): 'hell.mp4', 'grave.mp4', 'death.mp4', 'wealth.mp4', 'sajda.mp4', 'prayer.mp4', 'dua.mp4', 'manners.mp4'. \n"
        "BROAD FOLDERS (Tier 2 - General themes): 'nature' (for creation, weather, sky), 'Emotional' (for sadness, fear, mercy), 'asthatic' (for peace, faith, heaven, or if nothing else fits). \n"
        "Rule: Reply with ONLY the exact filename or folder name. Do not include any other words, punctuation, or explanations."
    )

    payload = {
        "model": "groq/compound-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": english_text}
        ],
        "temperature": 0.1,
        "max_tokens": 15
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        if res.status_code == 200:
            result = res.json()["choices"][0]["message"]["content"].strip().strip("'\"").strip()
            if result:
                return result
            else:
                print("   > ⚠️ Groq API returned empty string. Falling back to 'asthatic'.")
                return "asthatic"
        else:
            print(f"   > ⚠️ Groq API Error ({res.status_code}): {res.text[:120]}. Falling back to 'asthatic'.")
            return "asthatic"
    except Exception as e:
        print(f"   > ⚠️ Groq Router request failed ({e}). Falling back to 'asthatic'.")
        return "asthatic"

# 🌟 Curated Verse Bank for Specific Topics (Verified Authentic Quranic Ayahs)
TOPIC_VERSE_BANK = {
    "death": [
        "3:185", "21:35", "29:57", "50:19", "63:10", "4:78", "39:30", "62:8", "56:60", "56:83", "75:26", "23:99"
    ],
    "grave": [
        "102:1", "22:7", "82:4", "100:9", "36:51", "80:21", "35:22"
    ],
    "hell": [
        "2:24", "4:56", "67:6", "78:21", "88:1", "101:6", "14:16", "25:11", "3:131"
    ],
    "wealth": [
        "104:1", "9:34", "18:46", "57:20", "63:9", "2:261", "89:20", "92:18"
    ],
    "nature": [
        "88:17", "55:1", "3:190", "67:3", "78:6", "21:30", "16:10", "30:20", "50:6"
    ],
    "emotional": [
        "39:53", "94:5", "93:3", "2:186", "15:49", "12:86", "12:87", "2:155"
    ],
    "peaceful": [
        "13:28", "89:27", "10:62", "48:4", "24:35", "16:97"
    ],
    "relaxing": [
        "78:9", "28:73", "25:47", "30:21"
    ],
    "motivated": [
        "3:139", "3:200", "2:45", "2:153", "65:2", "29:69"
    ],
    "manners": [
        "49:11", "17:37", "31:18", "17:23", "41:34", "2:83", "16:90"
    ],
    "dua": [
        "2:201", "3:193", "21:87", "7:23", "25:74", "20:25", "27:19", "2:286"
    ],
    "sajda": [
        "32:15", "96:19", "25:64", "22:77", "29:45", "48:29", "20:14", "17:78"
    ]
}

TOPIC_VIDEO_MAP = {
    "death": "death.mp4",
    "grave": "grave.mp4",
    "hell": "hell.mp4",
    "wealth": "wealth.mp4",
    "nature": "nature",
    "emotional": "Emotional",
    "peaceful": "asthatic",
    "relaxing": "relaxing.mp4",
    "motivated": "motivation.mp4",
    "manners": "manners.mp4",
    "dua": "dua.mp4",
    "sajda": "prayer.mp4"
}

def normalize_topic_key(selected_theme):
    if not selected_theme:
        return None
    theme_lower = selected_theme.lower()
    if "auto" in theme_lower or "random" in theme_lower:
        return None
    for key in ["death", "grave", "hell", "fire", "wealth", "nature", "emotional", "mercy", "peace", "relax", "motivat", "manner", "dua", "sajda", "prayer", "namaz"]:
        if key in theme_lower:
            if key == "fire": return "hell"
            if key == "mercy": return "emotional"
            if key == "peace": return "peaceful"
            if key == "relax": return "relaxing"
            if key == "motivat": return "motivated"
            if key == "manner": return "manners"
            if key in ["prayer", "namaz"]: return "sajda"
            return key
    return None

def get_video_and_duration(selection):
    selection_clean = selection.strip().strip("'\"").strip()
    selected_video = None
    recent_bgs = get_recent_bgs()
    
    file_aliases = {
        "hell.mp4": ["hell fire.mp4", "fire mountain.mp4", "fire.mp4", "hell.mp4"],
        "fire.mp4": ["fire mountain.mp4", "hell fire.mp4", "fire.mp4", "hell.mp4"],
        "death.mp4": ["death2.mp4", "death.mp4", "daeth.mp4"],
        "grave.mp4": ["grave.mp4"],
        "wealth.mp4": ["wealth.mp4"],
        "prayer.mp4": ["prayer.mp4", "namaz.mp4", "sajda.mp4"],
        "namaz.mp4": ["namaz.mp4", "prayer.mp4", "sajda.mp4"],
        "sajda.mp4": ["sajda.mp4", "prayer.mp4", "namaz.mp4"],
        "dua.mp4": ["dua.mp4", "emotional.mp4"],
        "manners.mp4": ["manners.mp4", "emotional.mp4", "peace.mp4"],
        "relaxing.mp4": ["relaxing.mp4", "relex.mp4", "peace.mp4", "2.mp4", "4.mp4"],
        "motivation.mp4": ["motivation.mp4", "peace.mp4", "3.mp4"]
    }
    
    search_folders = [
        # Direct bg folder (support both "bg" and "backgrounds")
        os.path.join("bg", "wealth"),
        os.path.join("bg", "Emotional"),
        os.path.join("bg", "nature"),
        os.path.join("bg", "asthatic"),
        "bg",
        # Combined backgrounds directory (primary)
        os.path.join("backgrounds", "wealth"),
        os.path.join("backgrounds", "Emotional"),
        os.path.join("backgrounds", "nature"),
        os.path.join("backgrounds", "asthatic"),
        "backgrounds",
        # New folder (both inside backgrounds and at root)
        os.path.join("backgrounds", "new", "wealth"),
        os.path.join("backgrounds", "new", "Emotional"),
        os.path.join("backgrounds", "new", "nature"),
        os.path.join("backgrounds", "new", "asthatic"),
        os.path.join("new", "wealth"),
        os.path.join("new", "Emotional"),
        os.path.join("new", "nature"),
        os.path.join("new", "asthatic"),
        # Legacy root fallbacks
        "wealth", "Emotional", "nature", "asthatic"
    ]

    # Tier 1: Exact File / Thematic Alias Matching
    if selection_clean.endswith(".mp4"):
        if os.path.exists(selection_clean):
            selected_video = selection_clean
        else:
            search_names = file_aliases.get(selection_clean, [selection_clean])
            candidates = []
            for target_name in search_names:
                for folder in search_folders:
                    candidate = os.path.join(base_dir, folder, target_name)
                    if os.path.exists(candidate) and candidate not in candidates:
                        candidates.append(candidate)
                        
            # Recursive scan inside bg/, backgrounds/, and new/ if not found in defined search folders
            if not candidates:
                for root_name in ["bg", "backgrounds", "new"]:
                    root_dir = os.path.join(base_dir, root_name)
                    if os.path.exists(root_dir):
                        for target_name in search_names:
                            for found in glob.glob(os.path.join(root_dir, "**", target_name), recursive=True):
                                if found not in candidates:
                                    candidates.append(found)

            if candidates:
                # Filter out recently used backgrounds for variety
                fresh_candidates = [c for c in candidates if os.path.normpath(c) not in recent_bgs]
                pool = fresh_candidates if fresh_candidates else candidates
                selected_video = random.choice(pool)
    
    # Tier 2: Broad Folder Matching or Fallback
    if not selected_video:
        target_folders = []
        if selection_clean in ["nature", "Emotional", "asthatic", "wealth"]:
            target_folders = [
                os.path.join("bg", selection_clean),
                os.path.join("backgrounds", selection_clean),
                os.path.join("backgrounds", "new", selection_clean),
                os.path.join("new", selection_clean),
                selection_clean
            ]
        else:
            target_folders = [
                os.path.join("bg", "asthatic"),
                os.path.join("backgrounds", "asthatic"),
                os.path.join("backgrounds", "new", "asthatic"),
                os.path.join("new", "asthatic"),
                "asthatic"
            ]
            
        videos = []
        for tf in target_folders:
            folder_path = os.path.join(base_dir, tf)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                for f in glob.glob(os.path.join(folder_path, "*.mp4")):
                    if f not in videos:
                        videos.append(f)
                        
        if not videos:
            fallback_dirs = [
                os.path.join(base_dir, "bg"),
                os.path.join(base_dir, "bg", "asthatic"),
                os.path.join(base_dir, "backgrounds", "asthatic"),
                os.path.join(base_dir, "backgrounds"),
                os.path.join(base_dir, "new", "asthatic"),
                os.path.join(base_dir, "asthatic")
            ]
            for fd in fallback_dirs:
                if os.path.exists(fd) and os.path.isdir(fd):
                    for f in glob.glob(os.path.join(fd, "*.mp4")):
                        if f not in videos:
                            videos.append(f)
                    if videos:
                        break
                        
        if not videos:
            # Safety net: search all mp4s in bg and backgrounds directories recursively
            for root_name in ["bg", "backgrounds"]:
                bg_dir = os.path.join(base_dir, root_name)
                if os.path.exists(bg_dir):
                    for f in glob.glob(os.path.join(bg_dir, "**", "*.mp4"), recursive=True):
                        if f not in videos:
                            videos.append(f)
                
        if not videos:
            return None, 0.0
                
        fresh_videos = [v for v in videos if os.path.normpath(v) not in recent_bgs]
        pool = fresh_videos if fresh_videos else videos
        selected_video = random.choice(pool)
        
    # Ultra-Fast Duration Probe (OpenCV: ~2ms, zero ffmpeg overhead)
    try:
        import cv2
        cap = cv2.VideoCapture(selected_video)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            if fps > 0 and frames > 0:
                duration = frames / fps
                return selected_video, duration
    except Exception:
        pass

    # Failsafe fallback to MoviePy
    try:
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(selected_video)
        duration = clip.duration
        clip.close()
        return selected_video, duration
    except Exception as e:
        print(f"   > ⚠️ Error reading video duration: {e}")
        return None, 0.0

def get_quran_data(min_duration_sec=20, custom_surah=None, custom_ayah=None, reciter_code="ar.husary", video_mode="Arabic Voice + Bilingual (Urdu)", groq_keys=None, selected_theme="🎲 Auto / Random"):
    if groq_keys is None:
        groq_keys = []
    
    topic_key = normalize_topic_key(selected_theme)
    if topic_key:
        print(f"   > 🎯 Topic Enforcement Active: [{selected_theme}] (Synchronizing Verse & Video Footage)")
    else:
        print(f"   > 📡 Mode: Auto / Random (Groq Semantic Router + Smart Firewall Active)")
    
    while True: 
        if custom_surah and custom_ayah:
            first_endpoint = f"{custom_surah}:{custom_ayah}"
            print(f"   > 🎯 Custom Request: Surah {custom_surah}, Ayah {custom_ayah}")
        elif topic_key and topic_key in TOPIC_VERSE_BANK:
            first_endpoint = random.choice(TOPIC_VERSE_BANK[topic_key])
            print(f"   > 📖 Thematic Verse Target [{topic_key.upper()}]: Surah {first_endpoint}")
        else:
            first_endpoint = str(random.randint(1, 6200))
        
        def fetch_ayah(endpoint):
            fetch_reciter = "ar.husary" if reciter_code == "ar.yasseraddussary" else reciter_code
            url = f"http://api.alquran.cloud/v1/ayah/{endpoint}/editions/quran-uthmani,ur.jalandhry,en.sahih,{fetch_reciter}"
            try:
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    data = res.json()["data"]
                    surah_num = data[0]['surah']['number']
                    ayah_num = data[0]['numberInSurah']
                    audio_url = f"https://everyayah.com/data/Yasser_Ad-Dussary_128kbps/{surah_num:03d}{ayah_num:03d}.mp3" if reciter_code == "ar.yasseraddussary" else data[3]["audio"]
                        
                    return {
                        "arabic": data[0]["text"], "urdu": data[1]["text"], "english": data[2]["text"],
                        "audio_url": audio_url, "surah_name": data[2]['surah']['englishName'],
                        "surah_num": surah_num, "ayah_num": ayah_num, "absolute_num": data[0]['number'] 
                    }
                else:
                    if custom_surah and custom_ayah:
                        print(f"   > ❌ API Error ({res.status_code}): Verse '{endpoint}' does not exist in the Holy Quran.")
            except Exception:
                pass
            return None

        def estimate_duration(verse_data):
            # Fast reciters average ~1.0s per Arabic word
            dur = len(verse_data["arabic"].split()) * 1.0 
            
            # Only add Urdu TTS time if the engine is actually generating an Urdu voice track
            if video_mode in ["Arabic Voice + Bilingual", "Arabic Voice + Bilingual (Urdu)", "Urdu Only"]: 
                dur += len(verse_data["urdu"].split()) * 0.35
                
            return dur

        first_verse = fetch_ayah(first_endpoint)
        if not first_verse:
            if custom_surah and custom_ayah:
                print(f"   > 🛑 Invalid Custom Target: Surah {custom_surah}, Ayah {custom_ayah} not found. Halting.")
                return None
            continue

        # Determine video selection: Topic-driven route OR Groq Semantic Router
        if topic_key and topic_key in TOPIC_VIDEO_MAP:
            routing_selection = TOPIC_VIDEO_MAP[topic_key]
            print(f"   > 🎬 Thematic Video Route: [{routing_selection.upper()}] for Topic [{topic_key.upper()}]")
        else:
            # Route to exact file (Tier 1) OR broad folder (Tier 2) via Groq LLM
            routing_selection = get_semantic_video(first_verse["english"], groq_keys=groq_keys)
            print(f"   > 🧠 Groq Semantic Router matched verse to: [{os.path.basename(routing_selection).upper()}]")

        video_path, video_duration = get_video_and_duration(routing_selection)
        if not video_path:
            continue

        # 🌟 NEW SMART DURATION RULES (STRICTLY > 20s FINAL VIDEO)
        if video_duration < 10.0:
            # Micro videos loop up to 5 times (or up to 32s) to safely clear the 20s minimum
            max_allowed_duration = min(max(video_duration * 5.0, 32.0), 55.0) 
            min_required_duration = 20.0
            print(f"   > 🎞️ Micro video ({video_duration:.1f}s). Max: {max_allowed_duration:.1f}s | Min required: 20.0s.")
            
        elif 10.0 <= video_duration <= 25.0:
            # Short videos loop up to 2.5 times (or up to 36s) to safely clear the 20s minimum
            max_allowed_duration = min(max(video_duration * 2.5, 36.0), 55.0)
            min_required_duration = 20.0
            print(f"   > 🎞️ Short video ({video_duration:.1f}s). Max: {max_allowed_duration:.1f}s | Min required: 20.0s.")
            
        else:
            # Videos > 25s are strictly blocked from looping. 
            max_allowed_duration = min(video_duration, 55.0)
            # Require the audio to fill most of the video, but never drop below 20s
            min_required_duration = max(20.0, max_allowed_duration - 8.0) 
            print(f"   > 🎞️ Long video ({video_duration:.1f}s). No looping. Max: {max_allowed_duration:.1f}s | Min required: {min_required_duration:.1f}s.")

        first_dur = estimate_duration(first_verse)

        if first_dur > max_allowed_duration:
            if custom_surah and custom_ayah:
                if first_dur <= 55.0:
                    max_allowed_duration = min(55.0, first_dur + 3.0)
                    print(f"   > 🎯 Custom Verse Override: Adjusted timeline to {max_allowed_duration:.1f}s to fit custom verse (~{first_dur:.1f}s).")
                else:
                    print(f"   > 🛑 Custom verse duration (~{first_dur:.1f}s) exceeds 55.0s reel ceiling. Surah {custom_surah}:{custom_ayah} is too long for a short. Halting.")
                    return None
            else:
                print(f"   > 🛑 FIREWALL HIT: First verse (~{first_dur:.1f}s) exceeds max limit ({max_allowed_duration:.1f}s). Dropping...")
                continue 
        
        verses_data = [first_verse]
        total_estimated_duration = first_dur
        current_absolute_num = first_verse["absolute_num"]
        
        while True:
            current_absolute_num += 1
            next_verse = fetch_ayah(str(current_absolute_num))
            
            if not next_verse or next_verse["surah_name"] != first_verse["surah_name"]:
                break
                
            next_dur = estimate_duration(next_verse)
            
            if (total_estimated_duration + next_dur) > max_allowed_duration:
                print(f"   > ✂️ Limit Reached! Next verse pushes past {max_allowed_duration:.1f}s. Dropping it and finishing sequence.")
                break
                
            verses_data.append(next_verse)
            total_estimated_duration += next_dur

        # 🌟 SMART MINIMUM FLOOR
        if total_estimated_duration < min_required_duration:
            print(f"   > ⚠️ Audio too short (~{total_estimated_duration:.1f}s). Needs at least {min_required_duration:.1f}s for this video. Retrying...")
            continue
            
        print(f"   > ✅ Locked in {len(verses_data)} verses. Total estimated audio: ~{total_estimated_duration:.1f}s.")
        record_used_bg(video_path)
        break 

    return {
        "reference": "PENDING", 
        "verses": verses_data, 
        "preselected_bg": video_path,
        "target_duration": max_allowed_duration
    }
