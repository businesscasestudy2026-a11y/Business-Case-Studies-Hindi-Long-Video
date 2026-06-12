import os, requests, json, subprocess, gc, random, re
import urllib.parse
import moviepy.editor as mpe
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
used_videos = set()
video_files = []
audio_files = []
last_successful_media = None  

print(f"Total Scenes to render: {len(scenes_data)}")

def get_pexels_video(query):
    try:
        res = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=15&orientation=landscape", headers={"Authorization": pexels_key}, timeout=15).json()
        if res.get('videos'):
            for v in res['videos']:
                url = v['video_files'][0]['link']
                if url not in used_videos:
                    used_videos.add(url)
                    return url
            return res['videos'][0]['video_files'][0]['link']
    except:
        return None

# --- 1. Processing Loop ---
for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'business').strip()
    image_prompt = scene.get('image_prompt', keyword).strip()
    text_line = scene.get('text', ' ').strip() or " "

    # Audio Pipeline
    raw_audio_path = f"raw_audio_{i}.mp3"
    norm_audio_path = f"audio_{i}.wav"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', text_line, '--write-media', raw_audio_path])
    if os.path.exists(raw_audio_path):
        subprocess.run(['ffmpeg', '-y', '-i', raw_audio_path, '-af', 'silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold=-35dB,bass=g=5:f=110,treble=g=3:f=8000', '-ar', '44100', '-ac', '2', norm_audio_path], check=True)
        out = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', norm_audio_path])
        scene_duration = float(out.decode('utf-8').strip()) + 0.2 
    else:
        scene_duration = 3.0
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', str(scene_duration), norm_audio_path], check=True)
    audio_files.append(norm_audio_path)

    # Visual Pipeline
    video_url = get_pexels_video(keyword)
    norm_video_path = f"video_{i}.mp4"
    try:
        if video_url:
            req = requests.get(video_url, timeout=45)
            with open(f"raw_{i}.mp4", "wb") as f: f.write(req.content)
            vclip = VideoFileClip(f"raw_{i}.mp4").fx(vfx.speedx, 1.2).subclip(0, min(VideoFileClip(f"raw_{i}.mp4").duration, scene_duration))
        else:
            raw_media_path = f"raw_{i}.jpg"
            img_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(image_prompt)}?width=1920&height=1080&nologo=true"
            req = requests.get(img_url, timeout=45)
            with open(raw_media_path, "wb") as f: f.write(req.content)
            vclip = ImageClip(raw_media_path).set_duration(scene_duration)
        
        vclip = vclip.resize(height=TARGET_H).crop(x_center=vclip.w/2, y_center=vclip.h/2, width=TARGET_W, height=TARGET_H)
        final_scene = CompositeVideoClip([vclip.resize(1.05)], size=(TARGET_W, TARGET_H)).set_duration(scene_duration)
        final_scene.write_videofile(norm_video_path, fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)
    except:
        ColorClip(size=(TARGET_W, TARGET_H), color=(30, 30, 30)).set_duration(scene_duration).write_videofile(norm_video_path, fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)
    
    video_files.append(norm_video_path)
    gc.collect()

# --- 2. Final Render ---
with open("vid_list.txt", "w") as f: [f.write(f"file '{v}'\n") for v in video_files]
with open("aud_list.txt", "w") as f: [f.write(f"file '{a}'\n") for a in audio_files]
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'vid_list.txt', '-c', 'copy', 'merged_video.mp4'], check=True)
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'aud_list.txt', '-c', 'copy', 'merged_audio.wav'], check=True)
subprocess.run(['ffmpeg', '-y', '-i', 'merged_video.mp4', '-i', 'merged_audio.wav', '-filter_complex', '[1:a]loudnorm=I=-14[a_out]', '-map', '0:v', '-map', '[a_out]', '-c:v', 'libx264', '-preset', 'fast', '-crf', '26', '-c:a', 'aac', 'final_video.mp4'], check=True)

# --- 3. Final Upload (Guaranteed HTTP Mode) ---
def upload_file(file_path):
    print("Uploading via native cURL (HTTP Mode)...")
    try:
        # HTTP ka use karke SSL handshake error bypass kar diya hai
        command = ['curl', '-s', '-F', f'file=@{file_path}', 'http://0x0.st']
        result = subprocess.check_output(command, timeout=1200).decode('utf-8').strip()
        if "http" in result:
            print(f"Upload success: {result}")
            return result
    except Exception as e:
        print(f"Upload failed: {e}")
    return "Failed"

video_link = upload_file('final_video.mp4')
requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": f"READY_TO_UPLOAD|{video_link}|{video_title}|{thumbnail_prompt}|{video_desc}"}, verify=False)
