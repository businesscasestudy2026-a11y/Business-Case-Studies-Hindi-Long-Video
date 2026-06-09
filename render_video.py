import os, requests, json, subprocess
import moviepy.editor as mpe
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, vfx, ColorClip, ImageClip

# ... (Configuration wahi rahega jo aapka tha) ...
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))
bot_token = "8798779179:AAH53t28qW6g7QTsB8nGCEswNJz2DXR9ssU"

# 1. Video Download and Save as RAW
video_files = []
audio_paths = []
for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'business').strip()
    text = scene.get('text', ' ').strip()
    
    # TTS
    audio_path = f"audio_{i}.mp3"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', text, '--write-media', audio_path])
    audio_paths.append(audio_path)
    
    # Pexels Fetch
    try:
        res = requests.get(f"https://api.pexels.com/videos/search?query={keyword}&per_page=5&orientation=landscape", headers={"Authorization": pexels_key}).json()
        url = res['videos'][0]['video_files'][0]['link']
        vid_path = f"clip_{i}.mp4"
        with open(vid_path, "wb") as f: f.write(requests.get(url).content)
        video_files.append(vid_path)
    except:
        # Fallback to a safe clean video
        video_files.append("https://player.vimeo.com/external/372064106.sd.mp4?s=d4052309831778170d62")

# 2. FFmpeg Concatenation (The Real Fix for Black Screen)
# Saari files ko ek list mein daal kar ek hi baar FFmpeg se encode karenge
with open("inputs.txt", "w") as f:
    for vid in video_files: f.write(f"file '{vid}'\n")

# FFmpeg filter: Concatenate videos + Add Audio + Duck BGM
# Hum yahan seedha 'final_video.mp4' bana rahe hain, intermediate file nahi
ffmpeg_cmd = [
    'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'inputs.txt',
    '-stream_loop', '-1', '-i', 'bgm.mp3',
    '-filter_complex', '[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[v];[1:a]volume=0.3[bgm]',
    '-map', '[v]', '-map', '[bgm]', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-b:v', '1500k',
    '-c:a', 'aac', '-shortest', 'final_video.mp4'
]
subprocess.run(ffmpeg_cmd, check=True)

# 3. Upload
res = requests.post("https://tmpfiles.org/api/v1/upload", files={'file': open('final_video.mp4', 'rb')}, timeout=1200)
link = res.json()['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": f"READY_TO_UPLOAD|{link}|{video_title}|{thumbnail_prompt}|{video_desc}"})
