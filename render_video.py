import os, requests, json, subprocess, gc, random
import moviepy.editor as mpe
from moviepy.editor import VideoFileClip, AudioFileClip, ColorClip, CompositeVideoClip

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
    if not video_url: video_url = get_pexels_video('office team')

    # --- 3. Dynamic Video Normalization (FIXED FREEZE ISSUE) ---
    norm_video_path = f"video_{i}.mp4"
    try:
        raw_vid_path = f"raw_vid_{i}.mp4"
        req = requests.get(video_url, timeout=45)
        with open(raw_vid_path, "wb") as f: f.write(req.content)

        vclip = VideoFileClip(raw_vid_path)
        
        # Loop video smoothly if it's shorter than audio
        if vclip.duration < scene_duration:
            import moviepy.video.fx.all as vfx
            vclip = vclip.fx(vfx.loop, duration=scene_duration)
        else:
            vclip = vclip.subclip(0, scene_duration)

        # Smart Auto-Scaling
        if (vclip.w / vclip.h) > (TARGET_W / TARGET_H):
            vclip = vclip.resize(height=TARGET_H)
        else:
            vclip = vclip.resize(width=TARGET_W)
            
        vclip = vclip.crop(x_center=vclip.w/2, y_center=vclip.h/2, width=TARGET_W, height=TARGET_H)
        
        # 🔥 Smooth Video Motion (No Freezing!) 🔥
        motion_type = random.choice(['zoom_in', 'zoom_out'])
        zoom_factor = 1.05 
        
        if motion_type == 'zoom_in':
            z_clip = vclip.resize(lambda t: 1.0 + (zoom_factor - 1.0) * (t / scene_duration)).set_position(('center', 'center'))
        else:
            z_clip = vclip.resize(lambda t: zoom_factor - (zoom_factor - 1.0) * (t / scene_duration)).set_position(('center', 'center'))

        final_scene = CompositeVideoClip([z_clip], size=(TARGET_W, TARGET_H)).set_duration(scene_duration)

        # Force identical output streams to avoid black screens
        final_scene.write_videofile(norm_video_path, fps=24, codec="libx264", audio=False, preset="ultrafast", ffmpeg_params=['-pix_fmt', 'yuv420p', '-vf', 'setsar=1'], logger=None)

        vclip.close()
        final_scene.close()
        if os.path.exists(raw_vid_path): os.remove(raw_vid_path)
    except Exception as e:
        print(f"Error on scene {i}: {e}")
        cclip = ColorClip(size=(TARGET_W, TARGET_H), color=(20, 20, 20)).set_duration(scene_duration)
        cclip.write_videofile(norm_video_path, fps=24, codec="libx264", audio=False, preset="ultrafast", ffmpeg_params=['-pix_fmt', 'yuv420p', '-vf', 'setsar=1'], logger=None)
        cclip.close()

    video_files.append(norm_video_path)
    gc.collect()
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

# --- 5. Final Master Mix (Grade + Text Watermark + Ducking) ---
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

# 🔥 CHANNEL NAME TEXT + Cinematic Grade 🔥
channel_name = "Business Case Studies"
filter_complex += f"[0:v]eq=contrast=1.05:saturation=1.15,vignette,drawtext=text='{channel_name}':fontcolor=white@0.7:fontsize=50:x=50:y=50[v_graded]; "
current_v_map = "[v_graded]"

if has_logo:
    ffmpeg_cmd.extend(['-i', 'logo.png'])
    filter_complex += f"[{inputs-1}:v]format=rgba,colorchannelmixer=aa=0.85,scale=200:-1[logo]; {current_v_map}[logo]overlay=W-w-40:40[v_out]"
    video_map = "[v_out]"
else:
    video_map = current_v_map

if filter_complex.endswith("; "): filter_complex = filter_complex[:-2]
if filter_complex: ffmpeg_cmd.extend(['-filter_complex', filter_complex])

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
