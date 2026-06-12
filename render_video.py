import os, sys, requests, json, subprocess, socket, gc, math, random
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, ColorClip, ImageClip, afx
import urllib.parse

# --- 1. CONFIGURATION ---
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))
bot_token = "7707041789:AAFB0DUbGlypExkUjxm0qpJC60Cj5HFLd-E" # Aapka Working Bot Token
HINDI_FONT_FILE = "Hindi.ttf"
TARGET_W, TARGET_H = 1920, 1080

# --- 2. ADVANCED RENDER ENGINE (From Business Case Study) ---
rendered_videos, rendered_audios, scene_durations = [], [], []

for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'finance')
    text_line = scene.get('text', '').strip()
    
    # Audio with Edge-TTS
    raw_audio, trimmed_audio = f"raw_{i}.mp3", f"trim_{i}.wav"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-SwaraNeural', '--text', text_line, '--write-media', raw_audio], check=True)
    subprocess.run(['ffmpeg', '-y', '-i', raw_audio, '-ss', '0.2', '-c:a', 'pcm_s16le', trimmed_audio], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    dur = AudioFileClip(trimmed_audio).duration
    scene_durations.append(dur)
    
    # Visual Fetching (Pexels)
    res = requests.get(f"https://api.pexels.com/videos/search?query={keyword}&per_page=1&orientation=landscape", headers={"Authorization": pexels_key}, timeout=15).json()
    vid_url = res['videos'][0]['video_files'][0]['link'] if res.get('videos') else "https://static.videezy.com/system/resources/previews/000/004/630/original/abstract-background-2.mp4"
    
    with open(f"vid_{i}.mp4", "wb") as f: f.write(requests.get(vid_url).content)
    
    # Clip processing with Zoom & Overlay
    clip = VideoFileClip(f"vid_{i}.mp4").subclip(0, min(dur, 20)).resize(height=TARGET_H).crop(x_center=TARGET_W/2, width=TARGET_W, height=TARGET_H)
    zoomed = clip.resize(lambda t: 1.0 + 0.04 * (t / dur)).set_position(('center', 'center'))
    overlay = ColorClip(size=(TARGET_W, TARGET_H), color=(0,0,0)).set_opacity(0.4).set_duration(dur)
    
    final_scene = CompositeVideoClip([zoomed, overlay], size=(TARGET_W, TARGET_H)).set_duration(dur)
    final_scene.write_videofile(f"scene_{i}.mp4", fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)
    
    rendered_videos.append(f"scene_{i}.mp4")
    rendered_audios.append(trimmed_audio)
    gc.collect()

# --- 3. MERGING & MASTER MIX ---
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'vid_concat.txt', '-c', 'copy', 'm_v.mp4']) # Note: Create vid_concat.txt
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'aud_concat.txt', '-c', 'pcm_s16le', 'm_a.wav'])

# Add Watermark & BGM
final_video = VideoFileClip("m_v.mp4").set_audio(AudioFileClip("m_a.wav"))
watermark = TextClip("Business Case Studies", fontsize=55, color='white', font=HINDI_FONT_FILE).set_opacity(0.5).set_position((0.75, 0.88), relative=True).set_duration(final_video.duration)
final_video = CompositeVideoClip([final_video, watermark])
final_video.write_videofile("final_video.mp4", codec="libx264", audio_codec="aac", preset="ultrafast")

# --- 4. INDESTRUCTIBLE UPLOAD & DIRECT TELEGRAM BRIDGE ---
def upload_and_notify():
    video_link = "Upload Failed"
    # Working Failover System
    endpoints = [
        ("0x0.st", "https://0x0.st", "file", lambda r: r.text.strip()),
        ("File.io", "https://file.io", "file", lambda r: r.json()['link'])
    ]
    
    for name, url, field, get_link in endpoints:
        try:
            with open("final_video.mp4", 'rb') as f:
                res = requests.post(url, files={field: f}, timeout=300)
            if res.status_code == 200:
                video_link = get_link(res)
                break
        except: continue
        
    # Telegram Direct Notify
    msg = f"READY_TO_UPLOAD|{video_link}|{title}|{thumbnail_prompt}|{description}"
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": msg})

upload_and_notify()
