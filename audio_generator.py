import asyncio
import edge_tts
import requests
import os
import sys
import gc
import warnings
import time  # 🌟 ADDED: Required for the slow-internet retry delay

# 🌟 UPGRADE 1: Suppress all Hugging Face token and symlink warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
warnings.filterwarnings("ignore", module="huggingface_hub")

from moviepy.editor import AudioFileClip

# 🌟 UPGRADE 2: Import Heavy Audio & AI Libraries gracefully
try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

try:
    from pedalboard import Pedalboard, Reverb, Compressor, HighpassFilter, LowpassFilter
    from pedalboard.io import AudioFile
except ImportError:
    Pedalboard = None

VOICES = {
    "urdu": "ur-PK-AsadNeural",
    "arabic": "ar-SA-HamedNeural"
}

# Safely determine the directory of the running .exe or script
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Force temp_cache to always live inside the actual app folder
TEMP_DIR = os.path.join(base_dir, "temp_cache")
os.makedirs(TEMP_DIR, exist_ok=True)

def cleanup_temp_cache():
    """Cleans up stale audio cache from previous runs to conserve disk space."""
    try:
        import glob
        for f in glob.glob(os.path.join(TEMP_DIR, "*.*")):
            try: os.remove(f)
            except: pass
    except: pass

cleanup_temp_cache()

# --- AI & AUDIO FX FUNCTIONS ---

_whisper_model = None
def get_whisper_model():
    """Lazily load the Whisper model into RAM/GPU based on hardware detection."""
    global _whisper_model
    if _whisper_model is None and WhisperModel is not None:
        try:
            import hardware_optimizer
            w_cfg = hardware_optimizer.get_optimal_whisper_config()
            print(f"   > 🧠 Initializing Whisper AI Engine (Model '{w_cfg['model']}', Device: {w_cfg['device'].upper()}, Threads: {w_cfg['cpu_threads']})...")
            _whisper_model = WhisperModel(
                w_cfg["model"],
                device=w_cfg["device"],
                compute_type=w_cfg["compute_type"],
                cpu_threads=w_cfg["cpu_threads"]
            )
        except Exception as e:
            print(f"   > ⚠️ Whisper Hardware Init Notice ({e}). Falling back to CPU Int8...")
            try:
                _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=1)
            except Exception as fallback_e:
                print(f"   > ❌ Whisper Fallback Error: {fallback_e}")
                return None
    return _whisper_model

def apply_acoustic_profile(audio_path, profile_name):
    """Applies cinematic Reverb and EQ to the audio based on UI selection."""
    if profile_name == "Default (Raw Audio)" or Pedalboard is None:
        return audio_path
        
    print(f"   > 🎛️ Applying Acoustic Profile: {profile_name}")
    try:
        with AudioFile(audio_path) as f:
            audio_data = f.read(f.frames)
            samplerate = f.samplerate

        if profile_name == "Cinematic Emotional":
            board = Pedalboard([
                Compressor(threshold_db=-20, ratio=3.0),
                HighpassFilter(cutoff_frequency_hz=80),
                Reverb(room_size=0.6, damping=0.4, wet_level=0.3)
            ])
        elif profile_name == "Deep Mosque":
            board = Pedalboard([
                Compressor(threshold_db=-15, ratio=2.5),
                LowpassFilter(cutoff_frequency_hz=5000),
                Reverb(room_size=0.9, damping=0.8, wet_level=0.5)
            ])
        elif profile_name == "Crisp Studio":
            board = Pedalboard([
                HighpassFilter(cutoff_frequency_hz=100),
                Compressor(threshold_db=-10, ratio=4.0)
            ])
        else:
            board = Pedalboard([])

        effected_data = board(audio_data, samplerate)
        out_path = audio_path.replace(".mp3", "_fx.wav")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        with AudioFile(out_path, 'w', samplerate, effected_data.shape[0]) as f:
            f.write(effected_data)
            
        return out_path
    except Exception as e:
        print(f"   > ❌ FX Error: {e} - Falling back to raw audio.")
        return audio_path

def generate_word_timestamps(audio_path, text, duration):
    """Uses AI to find exact millisecond timestamps for Karaoke glow, with a safe math fallback."""
    print("   > ⏱️ Running AI Word Sync...")
    model = get_whisper_model()
    words = text.split()
    
    # Safe Math Fallback (If no internet or model fails)
    fallback_timestamps = [{"word": w, "start": i * (duration / max(1, len(words))), "end": (i + 1) * (duration / max(1, len(words)))} for i, w in enumerate(words)]
    
    if model is None:
        print("   > ⚠️ AI not available. Using Math Fallback Sync.")
        return fallback_timestamps
        
    try:
        # 🌟 ACCURACY & SPEED FIX: Force Arabic ('ar') and enable Silero VAD (skips silent pauses, 30-50% faster)
        segments, _ = model.transcribe(
            audio_path,
            word_timestamps=True,
            language="ar",
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300)
        )
        ai_words = [word for segment in segments for word in segment.words]
        gc.collect()
        
        aligned = []
        ai_idx = 0
        for w in words:
            if ai_idx < len(ai_words):
                aligned.append({"word": w, "start": ai_words[ai_idx].start, "end": ai_words[ai_idx].end})
                ai_idx += 1
            else:
                last_end = aligned[-1]["end"] if aligned else 0
                aligned.append({"word": w, "start": last_end, "end": last_end + 0.5})
        return aligned
        
    except Exception as e:
        print(f"   > ⚠️ AI Sync failed: {e}. Using Math Fallback Sync.")
        return fallback_timestamps

# --- CORE DOWNLOADING & TIMELINE LOGIC ---

# 🌟 THE FIX: Slow Internet Shield with Retries and Chunk Streaming
def download_arabic_audio(audio_url, output_filename, max_retries=5):
    print("   > ⬇️ Downloading official Arabic recitation (Protected Mode)...")
    
    for attempt in range(1, max_retries + 1):
        try:
            # Increased timeout to 120 seconds and enabled chunk streaming
            response = requests.get(audio_url, timeout=120, stream=True)
            
            if response.status_code == 200:
                os.makedirs(os.path.dirname(output_filename), exist_ok=True)
                with open(output_filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return output_filename
            else:
                print(f"   > ⚠️ Server error {response.status_code}. Retrying...")
                
        except Exception as e:
            print(f"   > ⚠️ Download timeout/error on attempt {attempt}/{max_retries}: {e}")
            
        if attempt < max_retries:
            print("   > 🔄 Waiting 3 seconds before retrying...")
            time.sleep(3)
            
    print("   > ❌ FATAL: Failed to download Arabic audio after all retries.")
    return None

async def generate_ai_voiceover(text, language, output_audio):
    print(f"   > 🎙️ Generating {language.upper()} Voiceover...")
    voice = VOICES.get(language, VOICES["urdu"])
    communicate = edge_tts.Communicate(text, voice)
    os.makedirs(os.path.dirname(output_audio), exist_ok=True)
    await communicate.save(output_audio)
    return output_audio

# 🌟 UPGRADE 3: Updated Signature to accept acoustic_profile
def prepare_audio_timeline(verses_data, mode, acoustic_profile="Default (Raw Audio)"):
    print(f"\n   > ⚙️ Building Audio Timeline & Enforcing 55s True Limit...")
    sequence = []
    
    MAX_TRUE_DURATION = 55.0
    current_total_duration = 0.0
    
    for idx, verse in enumerate(verses_data):
        ar_path = os.path.join(TEMP_DIR, f"temp_ar_{idx}.mp3")
        ur_path = os.path.join(TEMP_DIR, f"temp_ur_{idx}.mp3")
        en_path = os.path.join(TEMP_DIR, f"temp_en_{idx}.mp3")
        
        main_audio_path = None
        entry = {"surah_name": verse['surah_name'], "ayah_num": verse['ayah_num']}

        if mode == "Arabic Only":
            main_audio_path = download_arabic_audio(verse['audio_url'], ar_path)
            entry.update({"text": verse['arabic'], "eng_text": verse['english'], "lang": "arabic"})
            
        elif mode in ["Urdu Only"]:
            asyncio.run(generate_ai_voiceover(verse['urdu'], "urdu", ur_path))
            main_audio_path = ur_path
            entry.update({"text": verse['urdu'], "eng_text": verse['english'], "lang": "urdu"})
            
        elif mode == "English Only":
            asyncio.run(generate_ai_voiceover(verse['english'], "english", en_path))
            main_audio_path = en_path
            entry.update({"text": verse['english'], "eng_text": None, "lang": "english"})
            
        elif mode in ["Arabic + Urdu", "Arabic Voice + Bilingual (Urdu)"]:
            main_audio_path = download_arabic_audio(verse['audio_url'], ar_path)
            entry.update({"text": verse['arabic'], "sub_text": verse['urdu'], "eng_text": verse['english'], "lang": "bilingual"})
            
        if not main_audio_path or not os.path.exists(main_audio_path):
            print("   > ❌ Missing audio file. Skipping verse.")
            continue
            
        try:
            temp_clip = AudioFileClip(main_audio_path)
            exact_clip_duration = temp_clip.duration
            temp_clip.close()
        except:
            print("   > ❌ Corrupt audio downloaded. Skipping verse.")
            continue
            
        if current_total_duration + exact_clip_duration > MAX_TRUE_DURATION:
            print(f"   > 🛑 55-SECOND FIREWALL HIT! (Rejecting Ayah {verse['ayah_num']}). Video safely capped at {current_total_duration:.1f}s")
            if os.path.exists(main_audio_path): os.remove(main_audio_path)
            break 
            
        # 🌟 THE SYNC FIX: 1. Get exact timestamps from the CLEAN, RAW audio first!
        if mode in ["Arabic Only", "Arabic + Urdu", "Arabic Voice + Bilingual (Urdu)"]:
            entry["timestamps"] = generate_word_timestamps(main_audio_path, verse['arabic'], exact_clip_duration)
        else:
            entry["timestamps"] = []

        # 🌟 THE SYNC FIX: 2. Apply the heavy FX (Reverb/Echo) AFTER we have the timestamps
        final_audio_path = apply_acoustic_profile(main_audio_path, acoustic_profile)
        entry["audio"] = final_audio_path

        current_total_duration += exact_clip_duration
        sequence.append(entry)
        print(f"   > ✅ Added Ayah {verse['ayah_num']} (Video is now {current_total_duration:.1f}s / {MAX_TRUE_DURATION}s)")
            
    try:
        import hardware_optimizer
        hardware_optimizer.trim_memory()
    except:
        pass
    return sequence

def combined_chunk_text(raw_text, full_sub_text, full_eng_text, words_per_chunk=4):
    ar_words = raw_text.split()
    num_chunks = max(1, (len(ar_words) + words_per_chunk - 1) // words_per_chunk)
    
    ar_chunks = []
    for i in range(0, len(ar_words), words_per_chunk):
        ar_chunks.append(" ".join(ar_words[i:i + words_per_chunk]))
        
    def chunk_proportionally(text):
        if not text: return [None] * num_chunks
        words = text.split()
        if not words: return [None] * num_chunks
        chunk_size = max(1, len(words) // num_chunks)
        chunks = []
        for i in range(num_chunks):
            if i == num_chunks - 1:
                chunks.append(" ".join(words[i*chunk_size : ]))
            else:
                chunks.append(" ".join(words[i*chunk_size : (i+1)*chunk_size]))
        return chunks

    ur_chunks = chunk_proportionally(full_sub_text)
    eng_chunks = chunk_proportionally(full_eng_text)
    
    return list(zip(ar_chunks, ur_chunks, eng_chunks))

def cleanup_audio_files(sequence_data):
    for item in sequence_data:
        if os.path.exists(item['audio']):
            try: os.remove(item['audio'])
            except: pass
        # Clean up the original mp3 if we created a _fx.wav version
        original_mp3 = item['audio'].replace('_fx.wav', '.mp3')
        if os.path.exists(original_mp3):
            try: os.remove(original_mp3)
            except: pass
            
    # Clean up the dedicated temporary cache folder
    import shutil
    try:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
            os.makedirs(TEMP_DIR, exist_ok=True) # Instantly rebuild the empty shell
            print("[+] Temporary cache cleared and reset for next loop.")
    except Exception as e:
        print(f"[-] Cache reset warning: {e}")
