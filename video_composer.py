import os
import sys
import glob
import random
import re
import cv2
import numpy as np
import requests
from moviepy.editor import *
from html2image import Html2Image
import PIL.Image
import gc
from moviepy.audio.fx.all import audio_fadeout
import moviepy.video.fx.all as vfx

if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

from proglog import ProgressBarLogger
class CancelableLogger(ProgressBarLogger):
    def __init__(self, abort_check, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.abort_check = abort_check

    def bars_callback(self, bar, attr, value, old_value=None):
        if self.abort_check and not self.abort_check():
            raise RuntimeError("RENDER_ABORTED_BY_USER")

if getattr(sys, 'frozen', False):
    install_dir = os.path.dirname(sys.executable)
else:
    install_dir = os.path.dirname(os.path.abspath(__file__))

app_data_dir = os.path.join(os.environ.get('APPDATA', ''), 'IslamicReelsStudio')
TEMP_DIR = os.path.join(app_data_dir, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)
os.chdir(app_data_dir)

def cleanup_old_temp_files():
    """Removes leftover temporary files from previous runs to save disk space on low-end systems."""
    try:
        patterns = ["temp_batch_*.html", "temp_ref_*.html", "api_cache_*.mp4", "chunk_*.png", "ref_text_*.png", "temp_audio_*.mp4", "test_render_*.mp4"]
        for p in patterns:
            for f in glob.glob(os.path.join(TEMP_DIR, p)):
                try: os.remove(f)
                except: pass
    except Exception:
        pass

# Run initial disk cleanup on startup
cleanup_old_temp_files()

hti = Html2Image(
    output_path=TEMP_DIR, 
    custom_flags=[
        '--default-background-color=00000000', 
        '--hide-scrollbars',
        '--force-device-scale-factor=1',
        '--no-sandbox',                 
        '--disable-gpu',                
        '--disable-dev-shm-usage',      
        '--disable-software-rasterizer',
        '--disable-gpu-compositing',
        '--disable-gpu-rasterization',
        '--log-level=3',
        '--silent',
        '--headless',
        '--allow-file-access-from-files'
    ]
)

chrome_path_1 = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
chrome_path_2 = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

if os.path.exists(chrome_path_1):
    hti.browser.executable = chrome_path_1
elif os.path.exists(chrome_path_2):
    hti.browser.executable = chrome_path_2
elif os.path.exists(edge_path):
    hti.browser.executable = edge_path

def get_all_background_files():
    search_dirs = [
        os.path.join(install_dir, "bg"),
        os.path.join(install_dir, "backgrounds"),
        os.path.join(os.getcwd(), "bg"),
        os.path.join(os.getcwd(), "backgrounds"),
        "bg",
        "backgrounds",
        os.path.join(app_data_dir, "bg"),
        os.path.join(app_data_dir, "backgrounds")
    ]
    extensions = ["*.mp4", "*.MP4", "*.mov", "*.MOV", "*.mkv", "*.MKV", "*.avi", "*.webm"]
    found = []
    for d in search_dirs:
        if os.path.exists(d) and os.path.isdir(d):
            for ext in extensions:
                found.extend(glob.glob(os.path.join(d, ext)))
                found.extend(glob.glob(os.path.join(d, "**", ext), recursive=True))
    seen = set()
    unique_videos = []
    for f in found:
        norm = os.path.abspath(f)
        if norm not in seen:
            seen.add(norm)
            unique_videos.append(f)
    return unique_videos

def get_sequential_background():
    videos = get_all_background_files()
    if not videos: return None
    videos.sort(key=lambda f: int(re.sub(r'\D', '', os.path.basename(f)) or 0))
    index_file = os.path.join(app_data_dir, "last_bg_index.txt")
    current_index = 0
    if os.path.exists(index_file):
        try:
            with open(index_file, "r") as f:
                current_index = int(f.read().strip())
        except: pass
    current_index = current_index % len(videos)
    selected_video = videos[current_index]
    try:
        with open(index_file, "w") as f:
            f.write(str(current_index + 1))
    except: pass
    return selected_video

def crop_to_9_16(clip):
    target_ratio = 9 / 16
    clip_ratio = clip.w / clip.h
    if clip_ratio > target_ratio:
        new_w = int(clip.h * target_ratio)
        clip = vfx.crop(clip, x_center=clip.w/2, width=new_w)
    else:
        new_h = int(clip.w / target_ratio)
        clip = vfx.crop(clip, y_center=clip.h/2, height=new_h)
    return vfx.resize(clip, newsize=(1080, 1920))

def fetch_api_background(pixabay_key, pexels_key):
    queries = ["dark minimalist nature", "night starry sky", "foggy driving night", "cinematic rain abstract", "dark galaxy space", "moody mountain clouds", "slow motion dark water"]
    query = random.choice(queries)
    video_url = None
    
    if pixabay_key:
        try:
            r = requests.get(f"https://pixabay.com/api/videos/?key={pixabay_key}&q={query}&per_page=10", timeout=5).json()
            if r.get('hits'):
                hit = random.choice(r['hits'])
                video_url = hit['videos']['medium']['url']
        except: pass
        
    if not video_url and pexels_key:
        try:
            headers = {"Authorization": pexels_key}
            r = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=10", headers=headers, timeout=5).json()
            if r.get('videos'):
                v = random.choice(r['videos'])
                video_files = v.get('video_files', [])
                if video_files:
                    video_url = video_files[0]['link']
        except: pass
        
    if video_url:
        try:
            temp_name = os.path.join(TEMP_DIR, f"api_cache_{random.randint(100000, 999999)}.mp4")
            with requests.get(video_url, stream=True, timeout=10) as r:
                r.raise_for_status()
                with open(temp_name, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return temp_name
        except Exception as error:
            print(f"   > ⚠️ Live API streaming error ({error}). Triggering immediate local fallback sequence...")
    return None

def build_master_background(total_duration, enable_hook=True, enable_dynamic=True, use_online_clips=False, pixabay_key="", pexels_key="", preselected_bg=None):
    print("   > 🎞️ Assembling Background Track...")

    # 🌟 Semantic Fast-Path: use the pre-selected themed video from news_gatherer
    if preselected_bg and os.path.exists(preselected_bg):
        print(f"   > 🎯 Loading Pre-Selected Semantic Video: {os.path.basename(preselected_bg)}")
        bg_clip = VideoFileClip(preselected_bg).without_audio()
        bg_clip = crop_to_9_16(bg_clip)
        video_duration = bg_clip.duration

        if bg_clip.duration <= 25.0 and total_duration > bg_clip.duration:
            print(f"   > 🔄 Video ({bg_clip.duration:.1f}s) triggered loop to cover audio ({total_duration:.1f}s).")
            bg_clip = bg_clip.fx(vfx.loop, duration=total_duration)
        elif total_duration > bg_clip.duration:
            # Absolute safety net: catches math variances for unlooped long videos
            bg_clip = bg_clip.fx(vfx.loop, duration=total_duration)
        else:
            print(f"   > ✂️ No loop needed. Trimming video ({bg_clip.duration:.1f}s) to match audio ({total_duration:.1f}s).")
            bg_clip = bg_clip.subclip(0, total_duration)

        return bg_clip, os.path.basename(preselected_bg), []

    # --- Original fallback pipeline (hook clips + local/API stitching) ---
    print("   > 🎞️ Assembling Dynamic Background Track...")
    clips_to_concat = []
    cut_times = []
    current_duration = 0.0

    import time
    random.seed(time.time_ns())

    if enable_hook:
        search_dirs = [
            os.path.join(install_dir, "reciter_clips"),
            os.path.join(os.getcwd(), "reciter_clips"),
            "reciter_clips"
        ]
        reciter_files = []
        for d in search_dirs:
            if os.path.exists(d):
                for ext in ["*.mp4", "*.MP4", "*.mov", "*.MOV"]:
                    reciter_files.extend(glob.glob(os.path.join(d, ext)))
        if reciter_files:
            random.shuffle(reciter_files)
            hook_path = reciter_files[0]
            try:
                hook_clip = VideoFileClip(hook_path).without_audio()
                hook_clip = crop_to_9_16(hook_clip)
                hook_duration = min(5.0, total_duration)
                
                if hook_clip.duration < hook_duration:
                    hook_clip = hook_clip.fx(vfx.loop, duration=hook_duration)
                else:
                    hook_clip = hook_clip.subclip(0, hook_duration)
                    
                clips_to_concat.append(hook_clip)
                current_duration += hook_duration
                cut_times.append(current_duration)
                print(f"   > 👤 Hook Forced: {hook_duration:.1f}s from {os.path.basename(hook_path)}")
            except Exception as e:
                print(f"   > ⚠️ Warning: Failed to process hook clip {hook_path}: {e}")

    local_bg_files = get_all_background_files()

    if enable_dynamic:
        if local_bg_files:
            random.shuffle(local_bg_files)
        local_index = 0
        
        while current_duration < total_duration:
            time_needed = total_duration - current_duration
            scene_length = min(10.0, time_needed)
            
            target_path = None
            if use_online_clips and (pixabay_key or pexels_key):
                target_path = fetch_api_background(pixabay_key, pexels_key)

            if not target_path:
                if local_bg_files:
                    target_path = local_bg_files[local_index % len(local_bg_files)]
                    local_index += 1
                else:
                    clips_to_concat.append(ColorClip(size=(1080, 1920), color=(15, 15, 15), duration=scene_length))
                    current_duration += scene_length
                    continue

            try:
                bg_clip = VideoFileClip(target_path).without_audio()
                bg_clip = crop_to_9_16(bg_clip)
                
                if bg_clip.duration < scene_length:
                    bg_clip = bg_clip.fx(vfx.loop, duration=scene_length)
                else:
                    max_start = max(0, bg_clip.duration - scene_length)
                    start_time = random.uniform(0, max_start)
                    bg_clip = bg_clip.subclip(start_time, start_time + scene_length)
                    
                clips_to_concat.append(bg_clip)
                current_duration += scene_length
                
                if current_duration < total_duration:
                    cut_times.append(current_duration)
            except Exception as e:
                print(f"   > ⚠️ Warning: Failed to process dynamic scene clip {target_path}: {e}")
                clips_to_concat.append(ColorClip(size=(1080, 1920), color=(15, 15, 15), duration=scene_length))
                current_duration += scene_length
    else:
        time_needed = total_duration - current_duration
        if time_needed > 0:
            bg_path = get_sequential_background()
            if bg_path:
                try:
                    bg_clip = VideoFileClip(bg_path).without_audio()
                    bg_clip = crop_to_9_16(bg_clip)
                    if bg_clip.duration < time_needed:
                        bg_clip = bg_clip.fx(vfx.loop, duration=time_needed)
                    else:
                        bg_clip = bg_clip.subclip(0, time_needed)
                    clips_to_concat.append(bg_clip)
                except Exception as e:
                    print(f"   > ⚠️ Failed to load static background {bg_path}: {e}")
            else:
                print("   > ⚠️ No local backgrounds found in 'backgrounds/' directory!")

    # 🛡️ FAILSAFE GUARANTEE: If clips_to_concat is empty for ANY reason, create a dark fallback clip!
    if not clips_to_concat:
        print("   > 🛡️ FAILSAFE: Generating solid dark fallback background clip...")
        fallback_dur = max(1.0, total_duration)
        clips_to_concat.append(ColorClip(size=(1080, 1920), color=(15, 15, 15), duration=fallback_dur))

    master_bg = concatenate_videoclips(clips_to_concat, method="compose")
    return master_bg, "Dynamic_Pipeline_Stitched", cut_times

def batch_create_text_images_via_html(chunks_data, font_path, sub_font_path, eng_font_path, ref_font_path, text_color, sub_text_color, eng_text_color, ref_text_color, font_size_px, sub_font_size_px, eng_font_size_px, ref_font_size_px, ref_bg_opacity, subtitle_style="Karaoke (Word Glow)", width=1080, height=900):
    abs_font_path = os.path.abspath(font_path).replace("\\", "/")
    abs_sub_font_path = os.path.abspath(sub_font_path).replace("\\", "/") if sub_font_path else abs_font_path
    abs_eng_font_path = os.path.abspath(eng_font_path).replace("\\", "/") if eng_font_path else abs_font_path
    abs_ref_font_path = os.path.abspath(ref_font_path).replace("\\", "/") if ref_font_path else abs_font_path
    
    temp_html_files = []
    output_filenames = []
    
    for idx, chunk in enumerate(chunks_data):
        font_face_css = f"@font-face {{ font-family: 'MainFont'; src: url('file:///{abs_font_path}'); }}\n"
        ar_text_formatted = " ".join(chunk['ar_words_list'])
        
        urdu_html = ""
        english_html = ""
        
        if chunk.get('ur_text'):
            font_face_css += f"@font-face {{ font-family: 'SubFont'; src: url('file:///{abs_sub_font_path}'); }}\n"
            urdu_html = f'<div class="sub-text">{chunk["ur_text"]}</div>'
        if chunk.get('eng_text'):
            font_face_css += f"@font-face {{ font-family: 'EngFont'; src: url('file:///{abs_eng_font_path}'); }}\n"
            english_html = f'<div class="eng-sub-text">{chunk["eng_text"]}</div>'
            
        html_body = f"""
        <div class="main-text">{ar_text_formatted}</div>
        {urdu_html}
        {english_html}
        """
            
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            {font_face_css}
            body {{
                background-color: transparent; margin: 0;
                display: flex; justify-content: center; align-items: center;
                flex-direction: column; height: {height}px; width: {width}px; overflow: hidden;
            }}
            .main-text {{
                font-family: 'MainFont', sans-serif; font-size: {chunk['active_font_size']}px;
                color: {text_color}; text-align: center; direction: rtl; line-height: 1.6;
                width: 850px; margin: 0 auto; white-space: normal; word-wrap: break-word;
                text-shadow: 0px 0px 20px {text_color}, 0px 0px 40px {text_color}, 2px 5px 15px rgba(0,0,0,0.9);
                opacity: 1.0;
            }}
            .sub-text {{
                font-family: 'SubFont', sans-serif; font-size: {sub_font_size_px}px; 
                color: {sub_text_color}; text-align: center; direction: rtl; line-height: 1.8; 
                text-shadow: 3px 3px 0 #000, 0px 10px 20px rgba(0,0,0,0.9);
                margin-top: 15px; width: 850px; margin: 0 auto;
            }}
            .eng-sub-text {{
                font-family: 'EngFont', Arial, sans-serif; font-size: {eng_font_size_px}px; 
                color: {eng_text_color}; text-align: center; direction: ltr; line-height: 1.5; 
                text-shadow: 2px 2px 0 #000, 0px 8px 15px rgba(0,0,0,0.9);
                margin-top: 15px; width: 850px; margin: 0 auto;
            }}
        </style>
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """
        temp_html_path = os.path.join(TEMP_DIR, f"temp_batch_{idx}_{random.randint(1000,9999)}.html")
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        temp_html_files.append(temp_html_path)
        output_filenames.append(chunk['output_filename'])

    if temp_html_files:
        hti.screenshot(html_file=temp_html_files, save_as=output_filenames, size=(width, height))
        
    for file in temp_html_files:
        if os.path.exists(file):
            os.remove(file)
            
    return [os.path.join(TEMP_DIR, f) for f in output_filenames]

def create_reference_badge_via_html(reference_text, font_path, ref_font_path, ref_text_color, ref_font_size_px, ref_bg_opacity, width=1080, height=250, output_filename="ref_text.png"):
    out_path = os.path.join(TEMP_DIR, output_filename)
    # 🌟 OPTIMIZATION: Ultra-fast PIL direct rendering (eliminates 2nd Chrome startup & ~150MB peak RAM)
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype(ref_font_path, int(ref_font_size_px))
        except Exception:
            font = ImageFont.load_default()
            
        bbox = draw.textbbox((0, 0), reference_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        pad_x = 28
        pad_y = 10
        badge_w = min(text_w + pad_x * 2, width * 0.85)
        badge_h = text_h + pad_y * 2
        
        bx0 = int((width - badge_w) / 2)
        by0 = int((height - badge_h) / 2)
        bx1 = bx0 + int(badge_w)
        by1 = by0 + int(badge_h)
        radius = int(badge_h / 2)
        
        try:
            opacity = float(ref_bg_opacity)
        except Exception:
            opacity = 0.5
            
        # Soft drop shadow
        shadow_alpha = int(70 * opacity)
        draw.rounded_rectangle([bx0, by0 + 3, bx1, by1 + 3], radius=radius, fill=(0, 0, 0, shadow_alpha))
        
        # Pill badge background
        bg_alpha = int(255 * opacity)
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=radius, fill=(0, 0, 0, bg_alpha))
        
        # Center reference text
        draw.text((width / 2, height / 2), reference_text, font=font, fill=ref_text_color, anchor="mm")
        
        img.save(out_path, "PNG")
        return out_path
    except Exception as pil_err:
        print(f"   > ⚠️ PIL Badge render failed: {pil_err}. Falling back to Chrome HTML.")
        abs_ref_font_path = os.path.abspath(ref_font_path).replace("\\", "/")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            @font-face {{ font-family: 'RefFont'; src: url('file:///{abs_ref_font_path}'); }}
            body {{
                background-color: transparent; margin: 0;
                display: flex; justify-content: center; align-items: center;
                height: {height}px; width: {width}px; overflow: hidden;
            }}
            .reference-badge {{
                font-family: 'RefFont', system-ui, sans-serif; font-size: {ref_font_size_px}px; 
                font-weight: 600; color: {ref_text_color}; letter-spacing: 3px; 
                background: rgba(0, 0, 0, {ref_bg_opacity}); padding: 8px 25px; border-radius: 50px; 
                box-shadow: 0px 5px 15px rgba(0,0,0,0.3); text-align: center; max-width: 85%;
            }}
        </style>
        </head>
        <body>
            <div class="reference-badge">{reference_text}</div>
        </body>
        </html>
        """
        temp_html_path = os.path.join(TEMP_DIR, f"temp_ref_{random.randint(10000, 99999)}.html")
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        hti.screenshot(html_file=temp_html_path, save_as=output_filename, size=(width, height))
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)
        return out_path

def generate_cinematic_video(sequence_data, reference_text, font_path, sub_font_path, eng_font_path, ref_font_path, text_color, sub_text_color, eng_text_color, ref_text_color, font_size_px, sub_font_size_px, eng_font_size_px, ref_font_size_px, ref_bg_opacity, main_y_pos, ref_y_pos, output_filename="final_reel.mp4", bg_blur_enabled=False, bg_blur_intensity=15, cpu_core_limit="1 Core (Low-End PC/VPS)", subtitle_style="Karaoke (Word Glow)", abort_check=None, enable_reciter_hook=False, enable_dynamic_scenes=False, sfx_path="", cinematic_arabic_size=180, use_online_clips=False, pixabay_key="", pexels_key="", preselected_bg=None):
    print(f"\n--- 🎬 ASSEMBLING DYNAMIC 1080P REEL ---")
    
    audio_clips = []
    text_clips = []
    temp_images_to_delete = []
    
    final_video = None
    bg_clip = None
    ref_clip = None
    final_audio = None

    try:
        for item in sequence_data:
            clip = AudioFileClip(item['audio'])
            audio_clips.append(clip)

        base_audio = concatenate_audioclips(audio_clips)
        final_video_duration = base_audio.duration 
        
        bg_clip, bg_name, cut_times = build_master_background(
            total_duration=final_video_duration, 
            enable_hook=enable_reciter_hook, 
            enable_dynamic=enable_dynamic_scenes,
            use_online_clips=use_online_clips,
            pixabay_key=pixabay_key,
            pexels_key=pexels_key,
            preselected_bg=preselected_bg  # 🌟 Semantic video forwarded from caller
        )

        if enable_dynamic_scenes and sfx_path and os.path.isfile(sfx_path):
            print(f"   > 🔊 Injecting Transition SFX (Power Vol: 70%) from: {os.path.basename(sfx_path)}")
            audio_layers = [base_audio]
            for t in cut_times:
                try:
                    sfx_clip = AudioFileClip(sfx_path).set_start(t).volumex(0.7)
                    audio_layers.append(sfx_clip)
                except Exception as e:
                    pass
            final_audio = CompositeAudioClip(audio_layers)
            final_audio = final_audio.set_duration(base_audio.duration)
        else:
            final_audio = base_audio

        final_audio = audio_fadeout(final_audio, 0.2)
            
        if bg_blur_enabled and bg_blur_intensity > 0:
            def blur_frame(image):
                img = np.array(image)
                k_size = int(bg_blur_intensity)
                if k_size % 2 == 0: k_size += 1
                return cv2.GaussianBlur(img, (k_size, k_size), 0)
            bg_clip = bg_clip.fl_image(blur_frame)
            
        print("   > ⚡ Batch Generating Text Overlays (High-Speed Mode)...")
        all_chunks_data = []
        from audio_generator import combined_chunk_text
        
        current_time_calc = 0.0
        
        for idx, item in enumerate(sequence_data):
            if abort_check and not abort_check(): raise RuntimeError("RENDER_ABORTED_BY_USER")

            lang = item['lang']
            raw_text = item['text']
            full_sub_text = item.get('sub_text', None) 
            full_eng_text = item.get('eng_text', None)
            
            mode_for_html = "bilingual_combined" if (full_sub_text or full_eng_text) and (lang in ["bilingual", "bilingual_combined"]) else lang
            
            words_per_screen = 6 if lang in ['urdu', 'english'] else 4
                
            combined_chunks = combined_chunk_text(raw_text, full_sub_text, full_eng_text, words_per_chunk=words_per_screen)
            verse_duration = audio_clips[idx].duration
            
            for chunk_idx, (ar_chunk, ur_chunk, eng_chunk) in enumerate(combined_chunks):
                ar_words_in_chunk = ar_chunk.split()
                chunk_word_count = len(ar_words_in_chunk)
                total_words_in_verse = max(1, len(raw_text.split()))
                chunk_duration = verse_duration * (chunk_word_count / total_words_in_verse)
                
                chunk_start = current_time_calc
                chunk_end = current_time_calc + chunk_duration
                current_time_calc += chunk_duration
                
                display_start = chunk_start
                display_duration = chunk_duration
                
                all_chunks_data.append({
                    "ar_words_list": ar_words_in_chunk,
                    "ur_text": ur_chunk,
                    "eng_text": eng_chunk,
                    "lang_mode": mode_for_html,
                    "output_filename": f"chunk_{idx}_{chunk_idx}_{random.randint(100,999)}.png",
                    "duration": display_duration,
                    "start_time": display_start,
                    "active_font_size": font_size_px
                })

        if all_chunks_data:
            batch_create_text_images_via_html(
                all_chunks_data, font_path, sub_font_path, eng_font_path, ref_font_path,
                text_color, sub_text_color, eng_text_color, ref_text_color,
                font_size_px, sub_font_size_px, eng_font_size_px, ref_font_size_px, ref_bg_opacity, subtitle_style, height=900
            )

            for chunk_info in all_chunks_data:
                img_path = os.path.join(TEMP_DIR, chunk_info["output_filename"])
                temp_images_to_delete.append(img_path)
                
                img_clip = ImageClip(img_path).set_position(('center', bg_clip.h * (main_y_pos / 100.0))).set_start(chunk_info["start_time"]).set_end(chunk_info["start_time"] + chunk_info["duration"])
                if not enable_dynamic_scenes:
                    img_clip = img_clip.crossfadein(0.25).crossfadeout(0.25)
                
                text_clips.append(img_clip)

        if not enable_dynamic_scenes:
            ref_img_name = f"ref_text_{random.randint(100,999)}.png"
            ref_path = create_reference_badge_via_html(
                reference_text, font_path, ref_font_path, ref_text_color, ref_font_size_px, ref_bg_opacity, width=1080, height=250, output_filename=ref_img_name
            )
            temp_images_to_delete.append(ref_path)
            ref_clip = ImageClip(ref_path).set_position(('center', bg_clip.h * (ref_y_pos / 100.0))).set_duration(final_video_duration)
            final_video = CompositeVideoClip([bg_clip] + text_clips + [ref_clip])
        else:
            if text_clips:
                final_video = CompositeVideoClip([bg_clip] + text_clips)
            else:
                final_video = bg_clip
            
        final_video = final_video.set_audio(final_audio)
        final_video = final_video.set_duration(final_video_duration) 
        
        import hardware_optimizer
        hw_cfg = hardware_optimizer.get_optimal_render_config(cpu_core_limit)
        render_threads = hw_cfg["threads"]
        render_preset = hw_cfg["preset"]
        fixed_bitrate = hw_cfg.get("bitrate", "4500k")
        bufsize = hw_cfg.get("bufsize", "2000k")
        tune = hw_cfg.get("tune")

        ffmpeg_params = ["-max_muxing_queue_size", "256", "-preset", render_preset, "-bufsize", bufsize]
        if tune:
            ffmpeg_params.extend(["-tune", tune])

        print(f"   > ⚙️ Hardware Acceleration Engine: {hw_cfg['desc']} | Preset: {render_preset.upper()} | Bitrate: {fixed_bitrate}")

        custom_logger = CancelableLogger(abort_check)
        temp_audio_name = os.path.join(TEMP_DIR, f"temp_audio_{random.randint(100000, 999999)}.mp4")

        # Trim memory right before launching heavy FFmpeg encoding
        hardware_optimizer.trim_memory()

        final_video.write_videofile(
            output_filename, fps=30, codec="libx264", audio_codec="aac",
            bitrate=fixed_bitrate, preset=render_preset, threads=render_threads,
            logger=custom_logger, temp_audiofile=temp_audio_name, remove_temp=True,
            ffmpeg_params=ffmpeg_params
        )
        print(f"   > ✅ Video successfully rendered: {output_filename}")
        success = True

    except RuntimeError as e:
        if str(e) == "RENDER_ABORTED_BY_USER":
            print(f"\n   > 🛑 Render Engine Force-Stopped! Cleaned up temporary video data.")
            success = False
        else:
            raise e
            
    finally:
        print("   > 🧹 Closing all MoviePy clips and freeing server RAM...")
        try:
            if 'final_video' in locals() and final_video: final_video.close()
            if 'bg_clip' in locals() and bg_clip: bg_clip.close()
            if 'ref_clip' in locals() and ref_clip: ref_clip.close()
            if 'final_audio' in locals() and final_audio: final_audio.close()
            for clip in audio_clips:
                try: clip.close()
                except: pass
            for t_clip in text_clips:
                try: t_clip.close()
                except: pass
        except: pass

        # Force garbage collection FIRST to release Windows file locks on ImageClips
        try:
            del text_clips, audio_clips
        except: pass
        import gc
        gc.collect()

        # Delete temporary PNGs now that file locks are released
        for temp_img in temp_images_to_delete:
            if os.path.exists(temp_img):
                try: os.remove(temp_img)
                except: pass
                
        if 'temp_audio_name' in locals() and os.path.exists(temp_audio_name):
            try: os.remove(temp_audio_name)
            except: pass
            
        # Clean any remaining temp files in TEMP_DIR
        for pattern in ["temp_batch_*.html", "temp_ref_*.html", "api_cache_*.mp4", "chunk_*.png", "ref_text_*.png", "temp_audio_*.mp4"]:
            for f in glob.glob(os.path.join(TEMP_DIR, pattern)):
                try: os.remove(f)
                except: pass

        # Release unused memory back to OS
        try:
            import hardware_optimizer
            hardware_optimizer.trim_memory()
        except:
            gc.collect()
                
    return success, bg_name
