import os, requests, json, subprocess, gc, io
from PIL import Image
import urllib.parse
from moviepy.editor import VideoFileClip, ColorClip, CompositeVideoClip, ImageClip
import moviepy.video.fx.all as vfx

# --- Configuration ---
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '8798779179:AAH53t28qW6g7QTsB8nGCEswNJz2DXR9ssU')

TARGET_W, TARGET_H = 1920, 1080
video_files = []
audio_files = []

# --- Processing Loop ---
for i, scene in enumerate(scenes_data):
    text_line = scene.get('text', ' ').strip() or " "
    raw_audio, norm_audio = f"raw_a_{i}.mp3", f"a_{i}.wav"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', text_line, '--write-media', raw_audio])
    subprocess.run(['ffmpeg', '-y', '-i', raw_audio, '-ar', '44100', '-ac', '2', norm_audio], check=True)
    duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', norm_audio]))
    
    norm_video = f"v_{i}.mp4"
    ai_prompt = urllib.parse.quote(scene.get('image_prompt', 'business concept'))
    
    try:
        # Robust image fetching using io.BytesIO
        response = requests.get(f"https://image.pollinations.ai/prompt/{ai_prompt}?width=1920&height=1080&nologo=true", timeout=45)
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        image_path = f"tmp_{i}.jpg"
        image.save(image_path, "JPEG")
        
        vclip = ImageClip(image_path).set_duration(duration).resize(height=TARGET_H).crop(x_center=TARGET_W/2, width=TARGET_W, height=TARGET_H)
        vclip = vclip.resize(lambda t: 1.0 + 0.05 * (t / duration)).set_position(('center', 'center'))
        
        CompositeVideoClip([vclip], size=(TARGET_W, TARGET_H)).set_duration(duration).write_videofile(norm_video, fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)
    except Exception as e:
        print(f"Error at scene {i}: {e}")
        ColorClip(size=(TARGET_W, TARGET_H), color=(30, 30, 30)).set_duration(duration).write_videofile(norm_video, fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)

    video_files.append(norm_video)
    audio_files.append(norm_audio)
    gc.collect()

# --- Merge and Upload ---
with open("v.txt", "w") as f: [f.write(f"file '{v}'\n") for v in video_files]
with open("a.txt", "w") as f: [f.write(f"file '{a}'\n") for a in audio_files]
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'v.txt', '-c', 'copy', 'm_v.mp4'], check=True)
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'a.txt', '-c', 'copy', 'm_a.wav'], check=True)
subprocess.run(['ffmpeg', '-y', '-i', 'm_v.mp4', '-i', 'm_a.wav', '-filter_complex', '[1:a]loudnorm=I=-14[a_out]', '-map', '0:v', '-map', '[a_out]', '-c:v', 'libx264', '-crf', '26', 'final.mp4'], check=True)

# --- Final Upload (SSL Bypass) ---
def upload_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            res = requests.post("https://0x0.st", files={"file": f}, timeout=1200, verify=False)
        return res.text.strip() if res.status_code == 200 else "Failed"
    except: return "Failed"

video_link = upload_file('final.mp4')
requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": f"READY_TO_UPLOAD|{video_link}|{os.environ.get('TITLE', 'Video')}|{os.environ.get('THUMBNAIL_PROMPT', '')}|{os.environ.get('DESCRIPTION', '')}"}, verify=False)
