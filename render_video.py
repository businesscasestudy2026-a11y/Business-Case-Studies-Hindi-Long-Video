import os, requests, json, subprocess, gc
import urllib.parse
from PIL import Image
import io
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip
import moviepy.video.fx.all as vfx

# --- Configuration ---
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))
bot_token = "7707041789:AAFB0DUbGlypExkUjxm0qpJC60Cj5HFLd-E" # Working Bot Token

TARGET_W, TARGET_H = 1920, 1080
video_files, audio_files = [], []

# --- 1. Processing Loop ---
for i, scene in enumerate(scenes_data):
    text_line = scene.get('text', ' ').strip() or " "
    raw_audio, norm_audio = f"raw_a_{i}.mp3", f"a_{i}.wav"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-SwaraNeural', '--text', text_line, '--write-media', raw_audio])
    subprocess.run(['ffmpeg', '-y', '-i', raw_audio, '-ar', '44100', '-ac', '2', norm_audio], check=True)
    
    # Visual Fetching
    ai_prompt = urllib.parse.quote(scene.get('image_prompt', 'business concept'))
    try:
        response = requests.get(f"https://image.pollinations.ai/prompt/{ai_prompt}?width=1920&height=1080&nologo=true", timeout=45)
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        image_path = f"tmp_{i}.jpg"
        image.save(image_path, "JPEG")
        
        # Clip creation
        clip = ImageClip(image_path).set_duration(3).resize(height=TARGET_H).crop(x_center=TARGET_W/2, width=TARGET_W, height=TARGET_H)
        clip.write_videofile(f"v_{i}.mp4", fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)
        video_files.append(f"v_{i}.mp4")
        audio_files.append(norm_audio)
    except Exception as e:
        print(f"Error scene {i}: {e}")

# --- 2. Safe Concatenation ---
with open("vid_concat.txt", "w") as f: [f.write(f"file '{os.path.abspath(v)}'\n") for v in video_files]
with open("aud_concat.txt", "w") as f: [f.write(f"file '{os.path.abspath(a)}'\n") for a in audio_files]

# Merge with error checking
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'vid_concat.txt', '-c', 'copy', 'm_v.mp4'], check=True)
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'aud_concat.txt', '-c', 'pcm_s16le', 'm_a.wav'], check=True)

if not os.path.exists("m_v.mp4"):
    print("❌ Merge Failed: m_v.mp4 not created!")
    exit(1)

# --- 3. Robust Upload ---
def upload_and_notify():
    video_link = "Upload Failed"
    endpoints = [("0x0.st", "https://0x0.st", "file", lambda r: r.text.strip())]
    
    try:
        with open("m_v.mp4", 'rb') as f:
            res = requests.post(endpoints[0][1], files={endpoints[0][2]: f}, timeout=300)
            if res.status_code == 200: video_link = res.text.strip()
    except Exception as e: print(f"Upload error: {e}")
    
    # Notify Telegram
    msg = f"READY_TO_UPLOAD|{video_link}|{os.environ.get('TITLE', 'Case Study')}|{os.environ.get('THUMBNAIL_PROMPT', '')}|{os.environ.get('DESCRIPTION', '')}"
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": msg})

upload_and_notify()
