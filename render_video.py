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

for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'business').strip()
    text_line = scene.get('text', ' ').strip() or " "

    # --- 1. TTS Generation & Normalization ---
    raw_audio_path = f"raw_audio_{i}.mp3"
    norm_audio_path = f"audio_{i}.wav"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', text_line, '--write-media', raw_audio_path])

    try:
        aclip = AudioFileClip(raw_audio_path)
        if aclip.duration > 0.3:
            aclip = aclip.subclip(0.1)
        scene_duration = aclip.duration
        aclip.write_audiofile(norm_audio_path, fps=44100, logger=None)
        aclip.close()
    except:
        scene_duration = 3.0
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', str(scene_duration), '-q:a', '9', '-acodec', 'pcm_s16le', norm_audio_path, '-y'])

    audio_files.append(norm_audio_path)

    # --- 2. Smart Pexels Fetching ---
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
        if not video_url:
            video_url = res['videos'][0]['video_files'][0]['link']
    except:
        video_url = "https://player.vimeo.com/external/372064106.sd.mp4?s=d4052309831778170d62" 

    # --- 3. Dynamic Video Normalization (THE BLACK SCREEN FIX) ---
    norm_video_path = f"video_{i}.mp4"
    try:
        raw_vid_path = f"raw_vid_{i}.mp4"
        with open(raw_vid_path, "wb") as f:
            f.write(requests.get(video_url, timeout=30).content)

        vclip = VideoFileClip(raw_vid_path)
        
        if vclip.duration < scene_duration:
            import moviepy.video.fx.all as vfx
            vclip = vclip.fx(vfx.loop, duration=scene_duration)
        else:
            vclip = vclip.subclip(0, scene_duration)

        vclip = vclip.resize(height=TARGET_H).crop(x_center=vclip.w/2, y_center=vclip.h/2, width=TARGET_W, height=TARGET_H)
        
        motion_type = random.choice(['zoom_in', 'zoom_out', 'pan_left', 'pan_right'])
        zoom_factor = 1.06 
        
        if motion_type == 'zoom_in':
            z_clip = vclip.resize(lambda t: 1.0 + (zoom_factor - 1.0) * (t / scene_duration))
            z_clip = z_clip.set_position(('center', 'center'))
        elif motion_type == 'zoom_out':
            z_clip = vclip.resize(lambda t: zoom_factor - (zoom_factor - 1.0) * (t / scene_duration))
            z_clip = z_clip.set_position(('center', 'center'))
        elif motion_type == 'pan_left':
            z_clip = vclip.resize(zoom_factor)
            z_clip = z_clip.set_position(lambda t: (-115 * (t / scene_duration), 'center'))
        else:
            z_clip = vclip.resize(zoom_factor)
            z_clip = z_clip.set_position(lambda t: (-115 + 115 * (t / scene_duration), 'center'))

        # 🔥 STRICT RESOLUTION LOCK: Forces exact 1920x1080 🔥
        final_scene = CompositeVideoClip([z_clip], size=(TARGET_W, TARGET_H)).set_duration(scene_duration)

        # Force identical pixel format and SAR so FFmpeg concat never fails
        final_scene.write_videofile(norm_video_path, fps=24, codec="libx264", audio=False, preset="ultrafast", ffmpeg_params=['-pix_fmt', 'yuv420p', '-vf', 'setsar=1'], logger=None)

        vclip.close()
        final_scene.close()
        if os.path.exists(raw_vid_path): os.remove(raw_vid_path)
    except Exception as e:
        print(f"Error on scene {i}: {e}")
        cclip = ColorClip(size=(TARGET_W, TARGET_H), color=(30, 30, 30)).set_duration(scene_duration)
        cclip.write_videofile(norm_video_path, fps=24, codec="libx264", audio=False, preset="ultrafast", ffmpeg_params=['-pix_fmt', 'yuv420p', '-vf', 'setsar=1'], logger=None)
        cclip.close()

    video_files.append(norm_video_path)
    gc.collect()
    print(f"Scene {i+1} Normalized ({motion_type if 'motion_type' in locals() else 'fallback'})")

# --- 4. High-Speed FFmpeg Concat ---
with open("vid_list.txt", "w") as f:
    for vid in video_files: f.write(f"file '{vid}'\n")

with open("aud_list.txt", "w") as f:
    for aud in audio_files: f.write(f"file '{aud}'\n")

subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'vid_list.txt', '-c', 'copy', 'merged_video.mp4'], check=True)
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'aud_list.txt', '-c', 'copy', 'merged_audio.wav'], check=True)

# --- 5. Final Master Mix (Anti-Demonetization Grade + Ducking) ---
print("Applying Color Grading, Ducking & Finalizing Pipeline...")
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

# Safe Anti-Demonetization Grade
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

ffmpeg_cmd.extend([
    '-map', video_map,
    '-map', audio_map,
    '-c:v', 'libx264', '-b:v', '1500k', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '128k',
    '-shortest', 'final_video.mp4'
])

subprocess.run(ffmpeg_cmd, check=True)

# --- 6. Robust Upload System ---
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
    except: pass

final_msg = f"READY_TO_UPLOAD|{video_link}|{video_title}|{thumbnail_prompt}|{video_desc}"
requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": final_msg})
