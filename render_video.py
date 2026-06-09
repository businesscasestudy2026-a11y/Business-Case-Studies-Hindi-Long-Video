import os, requests, json, subprocess

# --- Configuration ---
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))

video_title = os.environ.get('TITLE', 'Business Case Study')
thumbnail_prompt = os.environ.get('THUMBNAIL_PROMPT', 'Cinematic business thumbnail')
video_desc = os.environ.get('DESCRIPTION', 'Business case study video.')
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '8798779179:AAH53t28qW6g7QTsB8nGCEswNJz2DXR9ssU')

print(f"Total Scenes to render: {len(scenes_data)}")

used_videos = set()
video_files = []
audio_files = []

for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'business').strip()
    text_line = scene.get('text', ' ').strip() or " "

    # --- 1. Audio Pipeline (TTS) ---
    raw_audio = f"raw_audio_{i}.mp3"
    norm_audio = f"audio_{i}.wav"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', text_line, '--write-media', raw_audio])

    if os.path.exists(raw_audio):
        subprocess.run(['ffmpeg', '-y', '-i', raw_audio, '-ss', '0.1', '-ar', '44100', '-ac', '2', norm_audio], check=True)
        out = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', norm_audio])
        scene_duration = float(out.decode('utf-8').strip())
    else:
        scene_duration = 3.0
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', str(scene_duration), norm_audio], check=True)

    audio_files.append(norm_audio)

    # --- 2. Video Pipeline (Pexels to Uniform FFmpeg) ---
    video_url = None
    try:
        res = requests.get(f"https://api.pexels.com/videos/search?query={keyword}&per_page=15&orientation=landscape", headers={"Authorization": pexels_key}, timeout=15).json()
        if res.get('videos'):
            for v in res['videos']:
                url = v['video_files'][0]['link']
                if url not in used_videos:
                    video_url = url
                    used_videos.add(url)
                    break
        if not video_url: video_url = res['videos'][0]['video_files'][0]['link']
    except: pass

    norm_video = f"video_{i}.mp4"
    if video_url:
        raw_vid = f"raw_vid_{i}.mp4"
        try:
            with open(raw_vid, "wb") as f: f.write(requests.get(video_url, timeout=30).content)
            
            # Ye step black screen aur glitches ko hamesha ke liye rok dega
            subprocess.run([
                'ffmpeg', '-y', '-stream_loop', '-1', '-i', raw_vid,
                '-vf', 'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=24',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28', '-pix_fmt', 'yuv420p',
                '-t', str(scene_duration), '-an', norm_video
            ], check=True)
            if os.path.exists(raw_vid): os.remove(raw_vid)
        except Exception as e:
            print(f"Error processing video {i}: {e}")
            video_url = None 
    
    # Strict Fallback agar Pexels fail ho jaye
    if not video_url or not os.path.exists(norm_video):
        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=0x1a1a1a:s=1920x1080:r=24',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28', '-pix_fmt', 'yuv420p',
            '-t', str(scene_duration), norm_video
        ], check=True)

    video_files.append(norm_video)
    print(f"Scene {i+1} Processed: {keyword}")

# --- 3. High-Speed Concatenation ---
with open("vid_list.txt", "w") as f:
    for vid in video_files: f.write(f"file '{vid}'\n")

with open("aud_list.txt", "w") as f:
    for aud in audio_files: f.write(f"file '{aud}'\n")

print("Concatenating files...")
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'vid_list.txt', '-c', 'copy', 'merged_video.mp4'], check=True)
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'aud_list.txt', '-c', 'copy', 'merged_audio.wav'], check=True)

# --- 4. Master Mix (BGM Ducking + Logo Overlay) ---
print("Applying Audio Ducking & Finalizing Pipeline...")
has_logo = os.path.exists("logo.png")
has_bgm = os.path.exists("bgm.mp3")

ffmpeg_cmd = ['ffmpeg', '-y', '-i', 'merged_video.mp4', '-i', 'merged_audio.wav']
filter_complex = ""
audio_map = "1:a"
video_map = "0:v"
inputs = 2

if has_bgm:
    ffmpeg_cmd.extend(['-stream_loop', '-1', '-i', 'bgm.mp3'])
    filter_complex += "[1:a]asplit=2[voice_main][voice_control]; [2:a]volume=0.25[bgm_low]; [bgm_low][voice_control]sidechaincompress=threshold=0.08:ratio=8:attack=200:release=1000[ducked_bgm]; [voice_main][ducked_bgm]amix=inputs=2:duration=first[a_out]; "
    audio_map = "[a_out]"
    inputs += 1

if has_logo:
    ffmpeg_cmd.extend(['-i', 'logo.png'])
    filter_complex += f"[{inputs-1}:v]format=rgba,colorchannelmixer=aa=0.85,scale=200:-1[logo]; [0:v][logo]overlay=W-w-40:40[v_out]"
    video_map = "[v_out]"

if filter_complex.endswith("; "): filter_complex = filter_complex[:-2]
if filter_complex: ffmpeg_cmd.extend(['-filter_complex', filter_complex])

ffmpeg_cmd.extend([
    '-map', video_map,
    '-map', audio_map,
    '-c:v', 'libx264', '-b:v', '1500k', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '128k',
    '-shortest', 'final_video.mp4'
])

subprocess.run(ffmpeg_cmd, check=True)

# --- 5. Upload ---
def upload_file(file_path):
    try:
        res = requests.post("https://tmpfiles.org/api/v1/upload", files={'file': open(file_path, 'rb')}, timeout=1200)
        return res.json()['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
    except: return None

video_link = upload_file('final_video.mp4')
if not video_link:
    try:
        res = requests.post("https://0x0.st", files={'file': open('final_video.mp4', 'rb')}, timeout=1200)
        video_link = res.text.strip()
    except: video_link = "Upload Failed"

final_msg = f"READY_TO_UPLOAD|{video_link}|{video_title}|{thumbnail_prompt}|{video_desc}"
requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": final_msg})
