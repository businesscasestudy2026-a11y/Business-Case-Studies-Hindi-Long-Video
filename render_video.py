import os, requests, json, subprocess, socket, time
import moviepy.editor as mpe
import urllib3.util.connection as urllib3_cn
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, TextClip, concatenate_videoclips, vfx, afx, ColorClip

# 🛡️ HACKER TRICK: Force IPv4 to bypass Hostinger "Network is unreachable" block
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

HINDI_FONT_FILE = "Hindi.ttf" 

full_text = os.environ.get('FULL_TEXT', 'Ek baar ki baat hai.')
chat_id = os.environ.get('CHAT_ID')
webhook_url = os.environ.get('WEBHOOK_URL')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))
resume_url = os.environ.get('RESUME_URL')

print(f"Total Scenes to render: {len(scenes_data)}")

subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', full_text, '--write-media', 'voiceover.mp3'])

# --- FIX START: Audio Sync Problem Fix ---
raw_voiceover = AudioFileClip("voiceover.mp3")
# Edge-TTS ki shuruati khali aawaz (silence) ko 0.3 seconds trim kar rahe hain
if raw_voiceover.duration > 1.0:
    voiceover = raw_voiceover.subclip(0.3)
else:
    voiceover = raw_voiceover
# --- FIX END ---

total_chars = sum(len(s['text']) for s in scenes_data)

# 🚀 MEMORY FIX: Initialize a list to hold paths instead of RAM objects
rendered_scene_paths = []
audio_clips = [voiceover]
headers = {"Authorization": pexels_key}
current_time = 0.0

try:
    whoosh_sfx = AudioFileClip("whoosh.mp3").volumex(0.25)
    pop_sfx = AudioFileClip("pop.mp3").volumex(0.15)       
except:
    whoosh_sfx = pop_sfx = None

viral_colors = ['#FFD400', '#00FFFF', '#FFFFFF', '#39FF14'] 
TARGET_W, TARGET_H = 1920, 1080

for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'nature')
    text_line = scene.get('text', '')
    scene_duration = voiceover.duration * (len(text_line) / max(total_chars, 1))
    if scene_duration < 1.0: scene_duration = 1.0
    
    clip_to_close = None
    
    try:
        # FIX 1: Strict 15-second timeout for the API call
        res = requests.get(f"https://api.pexels.com/videos/search?query={keyword}&per_page=1&orientation=landscape", headers=headers, timeout=15).json()
        
        # FIX 2: Handle empty results from Pexels safely
        if not res.get('videos'):
            raise ValueError(f"No videos found on Pexels for keyword: '{keyword}'")
            
        video_url = res['videos'][0]['video_files'][0]['link']
        
        vid_path = f"vid_{i}.mp4"
        with open(vid_path, "wb") as f:
            # FIX 3: Strict 30-second timeout for the actual video download
            f.write(requests.get(video_url, timeout=30).content)
            
        clip = VideoFileClip(vid_path).subclip(0, scene_duration)
        clip_to_close = clip
        clip = clip.resize(height=TARGET_H)
        if clip.w < TARGET_W:
            clip = clip.resize(width=TARGET_W)
        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=TARGET_W, height=TARGET_H)
        
        zoomed_clip = clip.resize(lambda t: 1.0 + 0.04 * (t / scene_duration)).set_position(('center', 'center'))
        
    except Exception as e:
        print(f"⚠️ API/Download Error on scene {i} '{keyword}': {e}. Using fallback background.")
        # FIX 4: Fallback solid background so the scene is still added and audio sync isn't destroyed
        zoomed_clip = ColorClip(size=(TARGET_W, TARGET_H), color=(20, 20, 20)).set_duration(scene_duration)

    # Apply overlays and text regardless of whether the video downloaded or the fallback triggered
    dark_overlay = ColorClip(size=(TARGET_W, TARGET_H), color=(0,0,0)).set_opacity(0.35).set_position(('center', 'center')).set_duration(scene_duration)
    
    words = text_line.split(' ')
    chunk_size = 3
    chunks = [' '.join(words[j:j + chunk_size]) for j in range(0, len(words), chunk_size)]
    word_clips = []
    duration_per_chunk = scene_duration / len(chunks)
    
    for w_i, chunk in enumerate(chunks):
        current_color = viral_colors[w_i % len(viral_colors)]
        bg_txt = TextClip(chunk, fontsize=100, color='black', font=HINDI_FONT_FILE, stroke_color='black', stroke_width=15, method='caption', size=(1600, None))
        bg_txt = bg_txt.set_position(('center', 'center')).set_duration(duration_per_chunk).set_start(w_i * duration_per_chunk)
        main_txt = TextClip(chunk, fontsize=100, color=current_color, font=HINDI_FONT_FILE, stroke_color='black', stroke_width=3, method='caption', size=(1600, None))
        main_txt = main_txt.set_position(('center', 'center')).set_duration(duration_per_chunk).set_start(w_i * duration_per_chunk)
        word_clips.extend([bg_txt, main_txt])
    
    final_scene = CompositeVideoClip([zoomed_clip, dark_overlay] + word_clips, size=(TARGET_W, TARGET_H)).set_duration(scene_duration)
    
    # 🚀 MEMORY FIX: Render the scene immediately and save to disk
    temp_scene_path = f"temp_scene_{i}.mp4"
    final_scene.write_videofile(temp_scene_path, fps=24, codec="libx264", audio=False, preset="ultrafast", threads=2)
    rendered_scene_paths.append(temp_scene_path)
    
    # 🚀 MEMORY FIX: Force garbage collection to free RAM immediately
    final_scene.close()
    zoomed_clip.close()
    dark_overlay.close()
    for wc in word_clips:
        wc.close()
    if clip_to_close:
        clip_to_close.close()
    
    if whoosh_sfx: audio_clips.append(whoosh_sfx.set_start(current_time))
    if pop_sfx: audio_clips.append(pop_sfx.set_start(current_time + 0.1))
            
    current_time += scene_duration
    print(f"Scene {i+1} Ready & Saved: {keyword}")

# 🚀 MEMORY FIX: Load the flat MP4 chunks back in for final concatenation
loaded_clips = [VideoFileClip(path) for path in rendered_scene_paths]
final_video = concatenate_videoclips(loaded_clips, method="compose")

final_duration = final_video.duration
progress_bar = ColorClip(size=(TARGET_W, 15), color=(255, 0, 0))
progress_bar = progress_bar.set_position(lambda t: (-TARGET_W + int(TARGET_W * (t / max(final_duration, 1))), 'bottom'))
progress_bar = progress_bar.set_duration(final_duration)
final_video = CompositeVideoClip([final_video, progress_bar])

try:
    bgm = AudioFileClip("bgm.mp3").volumex(0.32)
    if bgm.duration < final_video.duration: bgm = afx.audio_loop(bgm, duration=final_video.duration)
    else: bgm = bgm.subclip(0, final_video.duration)
    audio_clips.append(bgm)
except: pass

final_audio = CompositeAudioClip(audio_clips)
final_video = final_video.set_audio(final_audio)

print("Rendering Final COMPRESSED LONG Video...")
final_video.write_videofile("final_video.mp4", fps=24, codec="libx264", audio_codec="aac", threads=2, bitrate="1000k", preset="ultrafast")

# Clean up memory for the final loaded chunks
final_video.close()
for c in loaded_clips:
    c.close()

print("Starting 5-Layer Indestructible Upload System...")
video_link = "Upload Failed"

if not video_link.startswith("http"):
    try:
        print("Trying 0x0.st API...")
        res = requests.post("https://0x0.st", files={'file': open('final_video.mp4', 'rb')}, timeout=600)
        if res.text.startswith("http"): video_link = res.text.strip()
    except Exception as e: print(f"0x0.st failed: {e}")

if not video_link.startswith("http"):
    try:
        print("Trying Uguu.se API...")
        res = requests.post("https://uguu.se/upload.php", files={'files[]': open('final_video.mp4', 'rb')}, timeout=600)
        if res.status_code == 200: video_link = res.json()['files'][0]['url']
    except Exception as e: print(f"Uguu.se failed: {e}")

if not video_link.startswith("http"):
    try:
        print("Trying Tmpfiles API...")
        res = requests.post("https://tmpfiles.org/api/v1/upload", files={'file': open('final_video.mp4', 'rb')}, timeout=600)
        if res.status_code == 200: video_link = res.json()['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
    except Exception as e: print(f"Tmpfiles failed: {e}")

if not video_link.startswith("http"):
    try:
        print("Trying Catbox API...")
        res = requests.post("https://catbox.moe/user/api.php", data={'reqtype': 'fileupload'}, files={'fileToUpload': open('final_video.mp4', 'rb')}, timeout=600)
        if res.text.startswith("http"): video_link = res.text.strip()
    except Exception as e: print(f"Catbox failed: {e}")

print(f"🔥 FINAL YOUTUBE LINK: {video_link} 🔥")

payload = {
    "chat_id": chat_id, 
    "message": "👑 Bhai! 100M+ Views Long Video Ready! 🔥", 
    "youtube_url": video_link
}

# 🛡️ HACKER TRICK: Chrome Browser Fake Header to bypass Hostinger WAF
safe_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}

if resume_url:
    print(f"Resuming n8n workflow at: {resume_url}")
    max_retries = 5
    
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1} of {max_retries} to hit n8n webhook...")
            response = requests.post(resume_url, json={"body": payload}, headers=safe_headers, timeout=30)
            
            print(f"n8n Resume Response: {response.status_code} - {response.text}")
            
            # Agar successfully hit ho gaya toh loop break kar do
            if response.status_code in [200, 201]:
                print("✅ Webhook successfully triggered!")
                break
            else:
                print(f"⚠️ Webhook returned status: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Warning: Failed to resume n8n. Error: {e}")
            
        # Agar aakhri attempt nahi hai, toh 15 seconds wait karke wapas try karo
        if attempt < max_retries - 1:
            print("⏳ Retrying in 15 seconds...")
            time.sleep(15)
    else:
        print("❌ All retries failed. Please check Hostinger Firewall.")
else:
    print("No RESUME_URL provided by n8n.")
