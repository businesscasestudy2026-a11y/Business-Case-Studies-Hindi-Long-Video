import os, requests, json, subprocess, gc
import urllib.parse
from PIL import Image
import io
from moviepy.editor import VideoFileClip, AudioFileClip, ColorClip, CompositeVideoClip, ImageClip
import moviepy.video.fx.all as vfx

# --- Configuration ---
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))
bot_token = "7707041789:AAFB0DUbGlypExkUjxm0qpJC60Cj5HFLd-E" # Aapka Working Token

TARGET_W, TARGET_H = 1920, 1080
video_files, audio_files = [], []

# --- 1. Processing Loop (Fixed Image Fallback) ---
for i, scene in enumerate(scenes_data):
    text_line = scene.get('text', ' ').strip() or " "
    raw_audio, norm_audio = f"raw_a_{i}.mp3", f"a_{i}.wav"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-SwaraNeural', '--text', text_line, '--write-media', raw_audio])
    subprocess.run(['ffmpeg', '-y', '-i', raw_audio, '-ar', '44100', '-ac', '2', norm_audio], check=True)
    duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', norm_audio]))
    
    norm_video = f"v_{i}.mp4"
    ai_prompt = urllib.parse.quote(scene.get('image_prompt', 'business concept'))
    
    try:
        # Robust Fetching
        response = requests.get(f"https://image.pollinations.ai/prompt/{ai_prompt}?width=1920&height=1080&nologo=true", timeout=45)
        if response.status_code == 200 and len(response.content) > 1000:
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            image_path = f"tmp_{i}.jpg"
            image.save(image_path, "JPEG")
            vclip = ImageClip(image_path).set_duration(duration).resize(height=TARGET_H).crop(x_center=TARGET_W/2, width=TARGET_W, height=TARGET_H)
            vclip = vclip.resize(lambda t: 1.0 + 0.05 * (t / duration)).set_position(('center', 'center'))
            vclip.write_videofile(norm_video, fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)
        else:
            raise Exception("Invalid image data")
    except Exception as e:
        print(f"Fallback to ColorClip at scene {i}: {e}")
        ColorClip(size=(TARGET_W, TARGET_H), color=(30, 30, 30)).set_duration(duration).write_videofile(norm_video, fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)
    
    video_files.append(os.path.abspath(norm_video))
    audio_files.append(os.path.abspath(norm_audio))
    gc.collect()

# --- 2. Safe Concatenation ---
with open("vid_concat.txt", "w") as f: [f.write(f"file '{v}'\n") for v in video_files]
with open("aud_concat.txt", "w") as f: [f.write(f"file '{a}'\n") for a in audio_files]

subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'vid_concat.txt', '-c', 'copy', 'm_v.mp4'], check=True)
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'aud_concat.txt', '-c', 'pcm_s16le', 'm_a.wav'], check=True)

# --- 3. Robust Upload & Notify ---
def upload_and_notify():
    video_link = "Upload Failed"
    try:
        res = subprocess.check_output(['curl', '-s', '-F', 'file=@m_v.mp4', 'http://0x0.st'], timeout=300).decode('utf-8').strip()
        if res.startswith('http'): video_link = res
    except: pass
    
    msg = f"READY_TO_UPLOAD|{video_link}|{os.environ.get('TITLE', 'Case Study')}|{os.environ.get('THUMBNAIL_PROMPT', '')}|{os.environ.get('DESCRIPTION', '')}"
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": msg})

upload_and_notify()
