import os, requests, json, subprocess, gc
import moviepy.editor as mpe
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, concatenate_videoclips, vfx, afx, ColorClip, ImageClip

# Configuration
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))
video_title = os.environ.get('TITLE', 'Business Case Study')
thumbnail_prompt = os.environ.get('THUMBNAIL_PROMPT', 'Cinematic business thumbnail')
video_desc = os.environ.get('DESCRIPTION', 'Business case study video.')
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '8798779179:AAH53t28qW6g7QTsB8nGCEswNJz2DXR9ssU')

rendered_scene_paths = []
audio_clips = []
headers = {"Authorization": pexels_key}
current_time = 0.0
used_videos = set()
TARGET_W, TARGET_H = 1920, 1080
CROSSFADE_DUR = 0.5 

for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'business').strip()
    text_line = scene.get('text', ' ').strip() or " "
    
    # 1. TTS
    scene_audio_path = f"voiceover_{i}.mp3"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', text_line, '--write-media', scene_audio_path])
    scene_voiceover = AudioFileClip(scene_audio_path).subclip(0.1) if os.path.exists(scene_audio_path) else None
    
    scene_duration = scene_voiceover.duration if scene_voiceover else 3.0
    visual_duration = scene_duration + CROSSFADE_DUR
    if scene_voiceover: audio_clips.append(scene_voiceover.set_start(current_time))
    
    # 2. Hardened Visual Fetching
    clip = None
    try:
        res = requests.get(f"https://api.pexels.com/videos/search?query={keyword}&per_page=5&orientation=landscape", headers=headers, timeout=10).json()
        if res.get('videos'):
            for v in res['videos']:
                url = v['video_files'][0]['link']
                if url not in used_videos:
                    vid_path = f"vid_{i}.mp4"
                    with open(vid_path, "wb") as f: f.write(requests.get(url, timeout=20).content)
                    clip = VideoFileClip(vid_path).subclip(0, visual_duration)
                    used_videos.add(url); break
        
        if clip:
            clip = clip.resize(height=TARGET_H).crop(x_center=clip.w/2, y_center=clip.h/2, width=TARGET_W, height=TARGET_H)
            zoomed_clip = clip.resize(lambda t: 1.0 + 0.04 * (t / visual_duration))
        else:
            raise Exception("No Pexels video")
    except:
        # FALLBACK: Agar video na mile toh ek generic solid color background use karein
        zoomed_clip = ColorClip(size=(TARGET_W, TARGET_H), color=(50, 50, 50)).set_duration(visual_duration)

    temp_path = f"temp_{i}.mp4"
    zoomed_clip.write_videofile(temp_path, fps=24, codec="libx264", audio=False, preset="ultrafast")
    rendered_scene_paths.append(temp_path)
    zoomed_clip.close(); gc.collect()
    current_time += scene_duration

# 3. Concatenation
loaded_clips = [VideoFileClip(path) for path in rendered_scene_paths]
final_video = concatenate_videoclips([c.crossfadein(CROSSFADE_DUR) if i > 0 else c for i, c in enumerate(loaded_clips)], padding=-CROSSFADE_DUR, method="compose")

# Logo
try:
    logo = (ImageClip("logo.png").resize(width=200).set_position(("right", "top")).set_opacity(0.85).set_duration(final_video.duration))
    final_video = CompositeVideoClip([final_video, logo])
except: pass

# Audio/Visual Merge
final_video.write_videofile("temp_no_audio.mp4", fps=24, codec="libx264", audio=False, preset="ultrafast")
CompositeAudioClip(audio_clips).write_audiofile("voice_merged.wav", fps=44100)

subprocess.run([
    'ffmpeg', '-y', '-i', 'temp_no_audio.mp4', '-i', 'voice_merged.wav', '-stream_loop', '-1', '-i', 'bgm.mp3',
    '-filter_complex', '[1:a]asplit=2[v][vc];[2:a]volume=0.3[bgm_l];[bgm_l][vc]sidechaincompress=threshold=0.08:ratio=8[bgm_d];[v][bgm_d]amix=inputs=2[aout]',
    '-map', '0:v', '-map', '[aout]', '-c:v', 'libx264', '-b:v', '800k', '-c:a', 'aac', '-b:a', '128k', '-shortest', 'final_video.mp4'
], check=True)

# Upload
res = requests.post("https://tmpfiles.org/api/v1/upload", files={'file': open('final_video.mp4', 'rb')}, timeout=1200)
link = res.json()['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": f"READY_TO_UPLOAD|{link}|{video_title}|{thumbnail_prompt}|{video_desc}"})
