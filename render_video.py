import os, requests, json, subprocess, gc, random

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

print(f"Total Scenes to render: {len(scenes_data)}")

# --- Smart Pexels Fetcher ---
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

# --- SRT Time Formatter ---
def format_srt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

srt_content = ""
current_srt_time = 0.0

for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'business').strip()
    text_line = scene.get('text', ' ').strip() or " "

    # --- 1. TTS Generation & Studio EQ Enhancement ---
    raw_audio_path = f"raw_audio_{i}.mp3"
    norm_audio_path = f"audio_{i}.wav"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', text_line, '--write-media', raw_audio_path])

    if os.path.exists(raw_audio_path):
        # 🔥 ELITE HACK 1: Podcast Studio EQ (Deep Bass, Clear Treble) 🔥
        subprocess.run(['ffmpeg', '-y', '-i', raw_audio_path, '-ss', '0.1', '-af', 'bass=g=5:f=110,treble=g=3:f=8000', '-ar', '44100', '-ac', '2', norm_audio_path], check=True)
        out = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', norm_audio_path])
        scene_duration = float(out.decode('utf-8').strip())
    else:
        scene_duration = 3.0
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', str(scene_duration), norm_audio_path], check=True)

    final_audio_path = norm_audio_path
    if os.path.exists("whoosh.mp3") and i > 0:
        mixed_audio = f"mixed_audio_{i}.wav"
        subprocess.run(['ffmpeg', '-y', '-i', norm_audio_path, '-i', 'whoosh.mp3', '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0[aout]', '-map', '[aout]', '-ar', '44100', '-ac', '2', mixed_audio], check=True)
        final_audio_path = mixed_audio

    audio_files.append(final_audio_path)

    # --- Subtitle Logic ---
    start_str = format_srt_time(current_srt_time)
    end_str = format_srt_time(current_srt_time + scene_duration)
    srt_content += f"{i+1}\n{start_str} --> {end_str}\n{text_line}\n\n"
    current_srt_time += scene_duration

    # --- 2. Smart Pexels Fetching ---
    video_url = get_pexels_video(keyword)
    if not video_url: video_url = get_pexels_video('office business')

    # --- 3. Dynamic Video Normalization (Anti-Demonetization Film Grain) ---
    norm_video_path = f"video_{i}.mp4"
    try:
        raw_vid_path = f"raw_vid_{i}.mp4"
        req = requests.get(video_url, timeout=45)
        with open(raw_vid_path, "wb") as f: f.write(req.content)

        motion_type = random.choice(['zoom_in', 'zoom_out', 'pan_left', 'pan_right'])
        
        if motion_type == 'zoom_in':
            zoom_filter = f"zoompan=z='min(zoom+0.0015,1.06)':d={int(scene_duration*24)}:s=1920x1080:fps=24"
        elif motion_type == 'zoom_out':
            zoom_filter = f"zoompan=z='max(1.06-(in/24)*0.0015,1)':d={int(scene_duration*24)}:s=1920x1080:fps=24"
        elif motion_type == 'pan_left':
            zoom_filter = f"zoompan=z=1.06:x='max(0, x-1)':y='y':d={int(scene_duration*24)}:s=1920x1080:fps=24"
        else:
            zoom_filter = f"zoompan=z=1.06:x='min(iw-iw/zoom, x+1)':y='y':d={int(scene_duration*24)}:s=1920x1080:fps=24"

        # 🔥 ELITE HACK 2: noise=alls=2:allf=t+u (Dynamic Film Grain to fool Content ID) 🔥
        vf_chain = f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,{zoom_filter},noise=alls=2:allf=t+u,setsar=1"

        subprocess.run([
            'ffmpeg', '-y', '-stream_loop', '-1', '-i', raw_vid_path,
            '-vf', vf_chain,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28', '-pix_fmt', 'yuv420p',
            '-video_track_timescale', '90000', '-t', str(scene_duration), '-an', norm_video_path
        ], check=True)
        
        if os.path.exists(raw_vid_path): os.remove(raw_vid_path)
    except Exception as e:
        print(f"Error on scene {i}: {e}")
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=0x1a1a1a:s=1920x1080:r=24', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-video_track_timescale', '90000', '-t', str(scene_duration), norm_video_path], check=True)

    video_files.append(norm_video_path)
    print(f"Scene {i+1} Processed")

# --- Save SRT File ---
with open("subtitles.srt", "w", encoding="utf-8") as f:
    f.write(srt_content)

# --- 4. High-Speed FFmpeg Concat ---
with open("vid_list.txt", "w") as f:
    for vid in video_files: f.write(f"file '{vid}'\n")

with open("aud_list.txt", "w") as f:
    for aud in audio_files: f.write(f"file '{aud}'\n")

subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'vid_list.txt', '-c', 'copy', 'merged_video.mp4'], check=True)
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'aud_list.txt', '-c', 'copy', 'merged_audio.wav'], check=True)

# --- 5. Final Master Mix (Grade + Ducking + Watermark + YouTube Optimization) ---
has_logo = os.path.exists("logo.png")
has_bgm = os.path.exists("bgm.mp3")

ffmpeg_cmd = ['ffmpeg', '-y', '-i', 'merged_video.mp4', '-i', 'merged_audio.wav']
filter_complex = ""
audio_map = ""
video_map = ""
inputs = 2

if has_bgm:
    ffmpeg_cmd.extend(['-stream_loop', '-1', '-i', 'bgm.mp3'])
    filter_complex += "[1:a]asplit=2[voice_main][voice_control]; [2:a]volume=0.25[bgm_low]; [bgm_low][voice_control]sidechaincompress=threshold=0.08:ratio=8:attack=200:release=1000[ducked_bgm]; [voice_main][ducked_bgm]amix=inputs=2:duration=first[a_out]; "
    audio_map = "[a_out]"
    inputs += 1
else:
    audio_map = "1:a"

# Cinematic Grade
filter_complex += "[0:v]eq=contrast=1.05:saturation=1.15,vignette[v_graded]; "
current_v_map = "[v_graded]"

if has_logo:
    ffmpeg_cmd.extend(['-i', 'logo.png'])
    filter_complex += f"[{inputs-1}:v]format=rgba,colorchannelmixer=aa=0.85,scale=200:-1[logo]; {current_v_map}[logo]overlay=W-w-40:40[v_out]"
    video_map = "[v_out]"
else:
    video_map = current_v_map

if filter_complex.endswith("; "): filter_complex = filter_complex[:-2]
if filter_complex: ffmpeg_cmd.extend(['-filter_complex', filter_complex])

# 🔥 ELITE HACK 3: YouTube Encoding Standard (Fast Upload, 4K Quality Look) 🔥
ffmpeg_cmd.extend([
    '-map', video_map, '-map', audio_map,
    '-c:v', 'libx264', '-preset', 'fast', '-profile:v', 'high', '-bf', '2', '-g', '48', '-crf', '26', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '128k', '-shortest', 'final_video.mp4'
])
subprocess.run(ffmpeg_cmd, check=True)

# --- 6. Dual Upload System ---
def upload_file(file_path):
    try:
        res = requests.post("https://tmpfiles.org/api/v1/upload", files={'file': open(file_path, 'rb')}, timeout=1200)
        return res.json()['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
    except: return "Failed"

video_link = upload_file('final_video.mp4')
srt_link = upload_file('subtitles.srt')

final_msg = f"READY_TO_UPLOAD|{video_link}|{video_title}|{thumbnail_prompt}|{video_desc}|{srt_link}"
requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": final_msg})
