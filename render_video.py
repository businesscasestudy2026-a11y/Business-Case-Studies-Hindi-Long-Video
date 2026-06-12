import os, sys, requests, json, subprocess, socket, gc, math, random
import urllib3.util.connection as urllib3_cn
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, TextClip, ColorClip, afx

# Force IPv4 to bypass strict server blocks
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

HINDI_FONT_FILE = "Hindi.ttf" 

# --- VARIABLES FETCHED FROM GITHUB ACTIONS ---
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))
title = os.environ.get('TITLE', 'Mind-blowing Earning Secret')
description = os.environ.get('DESCRIPTION', 'Make money online secret tricks.')
thumbnail_prompt = os.environ.get('THUMBNAIL_PROMPT', 'Cinematic beautiful thumbnail')

print(f"Total Scenes to render: {len(scenes_data)}")

# LONG FORMAT (Landscape 1920x1080) for Earn-Smart
TARGET_W, TARGET_H = 1920, 1080
viral_colors = ['#FFD400', '#00FFFF', '#FFFFFF', '#39FF14']
headers = {"Authorization": pexels_key}

try:
    whoosh_sfx = AudioFileClip("whoosh.mp3").volumex(0.25)
    pop_sfx = AudioFileClip("pop.mp3").volumex(0.15)        
except:
    whoosh_sfx = pop_sfx = None

rendered_videos = []
rendered_audios = []
scene_durations = []

# ==========================================
# Process Each Scene (NO AUDIO OVERLAP BUG)
# ==========================================
for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'finance')
    text_line = scene.get('text', '').strip()
    
    if not text_line: continue
    
    temp_txt_path = f"temp_scene_{i}.txt"
    raw_audio = f"raw_audio_{i}.mp3"
    trimmed_audio = f"trimmed_audio_{i}.wav" # WAV ensures perfect frame timing
    
    with open(temp_txt_path, "w", encoding="utf-8") as f:
        f.write(text_line)
        
    try:
        # 1. Native Speedup: MoviePy ki jagah Edge-TTS mein rate badha diya
        subprocess.run([sys.executable, '-m', 'edge_tts', '--voice', 'hi-IN-SwaraNeural', '--rate=+10%', '-f', temp_txt_path, '--write-media', raw_audio], check=True)
        
        # 2. Perfect Trim: FFmpeg se exact 0.2s hataya aur WAV mein convert kiya
        subprocess.run(['ffmpeg', '-y', '-i', raw_audio, '-ss', '0.2', '-c:a', 'pcm_s16le', trimmed_audio], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 3. Get exact duration
        clip_audio = AudioFileClip(trimmed_audio)
        scene_duration = clip_audio.duration
        clip_audio.close()
        
        scene_durations.append(scene_duration)
        
    except Exception as e:
        print(f"Audio failed for scene {i}: {e}")
        continue
        
    # PEXELS VIDEO FETCHING
    try:
        search_query = f"{keyword} finance wealth"
        res = requests.get(f"https://api.pexels.com/videos/search?query={search_query}&per_page=1&orientation=landscape", headers=headers, timeout=15).json()
        
        if 'videos' in res and len(res['videos']) > 0:
            video_url = res['videos'][0]['video_files'][0]['link']
        else:
            res = requests.get("https://api.pexels.com/videos/search?query=abstract technology money&per_page=1&orientation=landscape", headers=headers, timeout=15).json()
            video_url = res['videos'][0]['video_files'][0]['link']
        
        vid_path = f"vid_{i}.mp4"
        with open(vid_path, "wb") as f:
            f.write(requests.get(video_url, timeout=30).content)
            
        clip = VideoFileClip(vid_path).subclip(0, min(scene_duration, VideoFileClip(vid_path).duration))
        if clip.duration < scene_duration:
            clip = afx.vfx.loop(clip, duration=scene_duration)
            
        clip = clip.resize(height=TARGET_H)
        if clip.w < TARGET_W: clip = clip.resize(width=TARGET_W)
        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=TARGET_W, height=TARGET_H)
        
        # Zoom Effect & Overlay
        zoomed_clip = clip.resize(lambda t: 1.0 + 0.04 * (t / scene_duration)).set_position(('center', 'center'))
        dark_overlay = ColorClip(size=(TARGET_W, TARGET_H), color=(0,0,0)).set_opacity(0.40).set_duration(scene_duration).set_position(('center', 'center'))
        
        # 🔥 ADVANCED KINETIC TEXT ENGINE (Perfect Sync & Animations) 🔥
        def advanced_punch_anim(t):
            if t < 0.06: return 1.6 - 10.0 * t  
            elif t < 0.15: return 1.0 + 1.2 * (t - 0.06) 
            return 1.0

        def get_kinetic_pos(base_y, is_shaking, word_idx):
            def pos(t):
                idle_y = 7 * math.sin(t * 8 + word_idx)
                idle_x = 4 * math.cos(t * 6 + word_idx)
                if is_shaking and t > 0.06:
                    return (TARGET_W/2 + 5 * math.sin(t * 75) + idle_x, base_y + 5 * math.cos(t * 85) + idle_y)
                return (TARGET_W/2 + idle_x, base_y + idle_y)
            return pos

        words = text_line.split()
        word_clips = []

        if words:
            # 🚀 SMART SUBTITLE SYNCHRONIZATION 🚀
            word_weights = []
            for w in words:
                wt = len(w)
                if w.endswith(','): wt += 4 
                elif w[-1] in '.?!।': wt += 8 
                word_weights.append(wt)
            
            total_weight = sum(word_weights) if sum(word_weights) > 0 else 1
            current_time_pos = 0.0

            for w_i, word in enumerate(words):
                word_lower = word.lower()
                # Added finance specific danger/highlight keywords 
                is_danger = any(kw in word_lower for kw in ['secret', 'trick', 'hidden', 'scam', 'khatarnaak', 'danger', 'alert', 'mat', 'paisa', 'paise', 'income', 'profit', 'earn'])
                is_highlight = not is_danger and len(word) > 4
                
                duration_per_word = (word_weights[w_i] / total_weight) * scene_duration

                current_color = '#FF003C' if is_danger else ('#000000' if is_highlight else '#FFFFFF')
                bg_color = 'transparent' if is_danger else (random.choice(['#FFD400', '#39FF14', '#00FFFF']) if is_highlight else 'transparent')
                base_size = 155 if is_danger else (140 if is_highlight else 95)

                try:
                    text_y_pos = TARGET_H * 0.75 
                    position_filter = get_kinetic_pos(text_y_pos, is_danger, w_i)

                    if bg_color == 'transparent':
                        shadow_txt = TextClip(word, fontsize=base_size, color='black', font=HINDI_FONT_FILE, method='caption', size=(1500, None)).resize(advanced_punch_anim).set_position(get_kinetic_pos(text_y_pos + 15, is_danger, w_i)).set_duration(duration_per_word).set_start(current_time_pos)
                        bg_txt = TextClip(word, fontsize=base_size, color='black', font=HINDI_FONT_FILE, stroke_color='black', stroke_width=16, method='caption', size=(1500, None)).resize(advanced_punch_anim).set_position(position_filter).set_duration(duration_per_word).set_start(current_time_pos)
                        inner_border_txt = TextClip(word, fontsize=base_size, color='black', font=HINDI_FONT_FILE, stroke_color='white', stroke_width=4, method='caption', size=(1500, None)).resize(advanced_punch_anim).set_position(position_filter).set_duration(duration_per_word).set_start(current_time_pos)
                        main_txt = TextClip(word, fontsize=base_size, color=current_color, font=HINDI_FONT_FILE, method='caption', size=(1500, None)).resize(advanced_punch_anim).set_position(position_filter).set_duration(duration_per_word).set_start(current_time_pos)
                        word_clips.extend([shadow_txt, bg_txt, inner_border_txt, main_txt])
                    else:
                        main_txt = TextClip(word, fontsize=base_size, color=current_color, bg_color=bg_color, font=HINDI_FONT_FILE, method='caption', size=(None, None)).resize(advanced_punch_anim).set_position(position_filter).set_duration(duration_per_word).set_start(current_time_pos)
                        word_clips.append(main_txt)
                except: pass
                
                current_time_pos += duration_per_word

        final_scene = CompositeVideoClip([zoomed_clip, dark_overlay] + word_clips, size=(TARGET_W, TARGET_H)).set_duration(scene_duration)
        
        # RAM FIX: Render Scene Without Audio
        scene_filename = f"scene_rendered_{i}.mp4"
        final_scene.write_videofile(scene_filename, fps=24, codec="libx264", preset="ultrafast", audio=False, logger=None)
        
        rendered_videos.append(scene_filename)
        rendered_audios.append(trimmed_audio)
        
        final_scene.close()
        clip.close()
        del final_scene, clip, zoomed_clip, word_clips
        gc.collect()
        
        print(f"Scene {i+1} Ready: {keyword}")
        
        if os.path.exists(temp_txt_path): os.remove(temp_txt_path)
        if os.path.exists(raw_audio): os.remove(raw_audio)
        
    except Exception as e:
        print(f"Error on scene {i} video processing: {e}")

# ==========================================
# DISK CONCATENATION (Merging Safely)
# ==========================================
print("Merging Video scenes safely...")
with open("vid_concat.txt", "w") as f:
    for file in rendered_videos:
        f.write(f"file '{file}'\n")

subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'vid_concat.txt', '-c', 'copy', 'merged_video.mp4'])

print("Merging Audio scenes safely...")
with open("aud_concat.txt", "w") as f:
    for file in rendered_audios:
        f.write(f"file '{file}'\n")

subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'aud_concat.txt', '-c', 'pcm_s16le', 'merged_audio.wav'])

final_video = VideoFileClip("merged_video.mp4")
final_audio = AudioFileClip("merged_audio.wav")

master_audio_clips = [final_audio]
current_time = 0.0

# Add SFX strictly aligned with exact scene timings
for dur in scene_durations:
    if whoosh_sfx:
        master_audio_clips.append(whoosh_sfx.set_start(current_time))
    current_time += dur

# PROGRESS BAR
progress_bar = ColorClip(size=(TARGET_W, 15), color=(255, 0, 0))
progress_bar = progress_bar.set_position(lambda t: (-TARGET_W + int(TARGET_W * (t / max(final_video.duration, 1))), 'bottom'))
progress_bar = progress_bar.set_duration(final_video.duration)

# 🔥 Earn Smart Hindi Watermark Implementation 🔥
watermark = TextClip("Earn Smart Hindi", fontsize=55, color='white', font=HINDI_FONT_FILE, stroke_color='black', stroke_width=2)
watermark = watermark.set_opacity(0.5).set_position((0.75, 0.88), relative=True).set_duration(final_video.duration)

# Watermark composite mein add kiya gaya hai
final_video = CompositeVideoClip([final_video, progress_bar, watermark])

# BACKGROUND MUSIC
try:
    bgm = AudioFileClip("bgm.mp3").volumex(0.08)
    if bgm.duration < final_video.duration: bgm = afx.audio_loop(bgm, duration=final_video.duration)
    else: bgm = bgm.subclip(0, final_video.duration)
    master_audio_clips.append(bgm)
except: pass

final_combined_audio = CompositeAudioClip(master_audio_clips)
final_video = final_video.set_audio(final_combined_audio)

print("Rendering Final COMPRESSED LONG Video...")
final_video.write_videofile("final_video.mp4", fps=24, codec="libx264", audio_codec="aac", threads=2, bitrate="2000k", preset="ultrafast")

# ==========================================
# UPLOAD SYSTEM
# ==========================================
print("Starting Core Indestructible Upload System...")
video_link = "Upload Failed"

endpoints = [
    ("File.io", "https://file.io", "file", lambda r: r.json()['link']),
    ("0x0.st", "https://0x0.st", "file", lambda r: r.text.strip()),
    ("Uguu.se", "https://uguu.se/upload.php", "files[]", lambda r: r.json()['files'][0]['url']),
    ("Catbox.moe", "https://catbox.moe/user/api.php", "reqtype", lambda r: r.text.strip())
]

for name, url, field, get_link in endpoints:
    if video_link != "Upload Failed" and video_link.startswith("http"): break
    try:
        print(f"Trying upload to {name}...")
        files = {field: open("final_video.mp4", 'rb')}
        data = {'reqtype': 'fileupload'} if "catbox" in url else {}
        res = requests.post(url, files=files, data=data, timeout=300)
        
        if res.status_code == 200:
            link = get_link(res)
            if "http" in link: 
                video_link = link
                print(f"✅ Upload Success: {video_link}")
    except Exception as e: 
        print(f"❌ {name} failed: {e}")

# ==========================================
# TELEGRAM BRIDGE
# ==========================================
BOT_TOKEN = "7707041789:AAFB0DUbGlypExkUjxm0qpJC60Cj5HFLd-E" 

safe_description = str(description).replace('\n', '  ')
safe_title = str(title).replace('|', '')

if not chat_id or chat_id == "None":
    print("❌ Error: CHAT_ID is missing. Cannot send Telegram message.")
else:
    message_text = f"READY_TO_UPLOAD|{video_link}|{safe_title}|{thumbnail_prompt}|{safe_description}"
    
    if len(message_text) > 4000:
        message_text = message_text[:3990] + "...[TRUNC]"

    try:
        telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": str(chat_id).strip(), "text": message_text}
        response = requests.post(telegram_url, json=payload)
        
        if response.status_code == 200:
            print(f"✅ Webhook bypassed! Sent video details directly to Telegram! Status: {response.status_code}")
        else:
            print(f"❌ Telegram alert failed! Status: {response.status_code}, Error: {response.text}")
    except Exception as e:
        print(f"❌ Failed to send Telegram alert: {e}")
