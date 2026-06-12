import os, requests, json, subprocess, gc, random, re
from PIL import Image
import urllib.parse
from moviepy.editor import VideoFileClip, AudioFileClip, ColorClip, CompositeVideoClip, ImageClip
import moviepy.video.fx.all as vfx

# --- Configuration ---
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))
video_title = os.environ.get('TITLE', 'Business Case Study')
thumbnail_prompt = os.environ.get('THUMBNAIL_PROMPT', 'Cinematic business thumbnail')
video_desc = os.environ.get('DESCRIPTION', 'Business case study video.')
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '8798779179:AAH53t28qW6g7QTsB8nGCEswNJz2DXR9ssU')

TARGET_W, TARGET_H = 1920, 1080
video_files = []
audio_files = []

# --- Render Loop ---
for i, scene in enumerate(scenes_data):
    text_line = scene.get('text', ' ').strip() or " "
    raw_audio, norm_audio = f"raw_a_{i}.mp3", f"a_{i}.wav"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', text_line, '--write-media', raw_audio])
    subprocess.run(['ffmpeg', '-y', '-i', raw_audio, '-ar', '44100', '-ac', '2', norm_audio], check=True)
    duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', norm_audio]))
    
    norm_video = f"v_{i}.mp4"
    image_path = f"tmp_{i}.jpg"
    
    # Image fetching
    ai_prompt = urllib.parse.quote(scene.get('image_prompt', 'business'))
    req = requests.get(f"https://image.pollinations.ai/prompt/{ai_prompt}?width=1920&height=1080&nologo=true", timeout=45)
    
    # Robust Image saving using PIL
    img = Image.open(requests.get(f"https://image.pollinations.ai/prompt/{ai_prompt}?width=1920&height=1080&nologo=true", stream=True).raw)
    img.convert('RGB').save(image_path, "JPEG")
    
    # Video Clip creation
    vclip = ImageClip(image_path).set_duration(duration).resize(height=TARGET_H).crop(x_center=TARGET_W/2, width=TARGET_W, height=TARGET_H)
    vclip.write_videofile(norm_video, fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)
    
    video_files.append(norm_video)
    audio_files.append(norm_audio)
    gc.collect()

# --- Merge and Upload ---
# ... (Baaki concat aur upload logic same rahega) ...
