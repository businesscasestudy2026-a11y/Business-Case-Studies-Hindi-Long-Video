import os, requests, json, subprocess
import moviepy.editor as mpe
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, concatenate_videoclips, vfx, afx, ColorClip, ImageClip

chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))

video_title = os.environ.get('TITLE', 'Business Case Study')
thumbnail_prompt = os.environ.get('THUMBNAIL_PROMPT', 'Cinematic business thumbnail')
video_desc = os.environ.get('DESCRIPTION', 'Business case study video.')
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '8798779179:AAH53t28qW6g7QTsB8nGCEswNJz2DXR9ssU')

print(f"Total Scenes to render: {len(scenes_data)}")

rendered_scene_paths = []
audio_clips = []
headers = {"Authorization": pexels_key}
current_time = 0.0

# 🔥 IMPROVEMENT: Duplicate videos se bachne ke liye tracking set
used_videos = set()

try:
    whoosh_sfx = AudioFileClip("whoosh.mp3").volumex(0.25)
    pop_sfx = AudioFileClip("pop.mp3").volumex(0.15)        
except:
    whoosh_sfx = pop_sfx = None

TARGET_W, TARGET_H = 1920, 1080
CROSSFADE_DUR = 0.5  

for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'business').strip()
    text_line = scene.get('text', ' ').strip()
    if not text_line: text_line = " "
    
    # 1. Perfect Scene-by-Scene Audio Sync
    scene_audio_path = f"voiceover_{i}.mp3"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', text_line, '--write-media', scene_audio_path])
    
    try:
        scene_voiceover = AudioFileClip(scene_audio_path)
        if scene_voiceover.duration > 0.5:
            scene_voiceover = scene_voiceover.subclip(0.1)
    except:
        print(f"⚠️ TTS Error on scene {i}. Skipping audio for this scene.")
        scene_voiceover = None

    scene_duration = scene_voiceover.duration if scene_voiceover else 2.0
    if scene_duration < 1.0: scene_duration = 1.0
    
    visual_duration = scene_duration + CROSSFADE_DUR
    
    if scene_voiceover:
        audio_clips.append(scene_voiceover.set_start(current_time))
    
    clip_to_close = None
    video_url = None
    
    try:
        # 🔥 IMPROVEMENT: Top 15 videos mangao taaki choices hon
        res = requests.get(f"https://api.pexels.com/videos/search?query={keyword}&per_page=15&orientation=landscape", headers=headers, timeout=15).json()
        
        if res.get('videos') and len(res['videos']) > 0:
            # Jo video pehle use nahi hui, use select karo
            for v in res['videos']:
                potential_url = v['video_files'][0]['link']
                if potential_url not in used_videos:
                    video_url = potential_url
                    used_videos.add(video_url)
                    break
            
            # Fallback agar saari ki saari 15 videos already use ho chuki hain
            if not video_url:
                video_url = res['videos'][0]['video_files'][0]['link']
                
        # Smart Keyword Fallback (Agar main keyword par koi video na mile)
        if not video_url:
            print(f"⚠️ Keyword '{keyword}' failed. Trying safe business fallback...")
            fallback_res = requests.get(f"https://api.pexels.com/videos/search?query=business startup&per_page=15&orientation=landscape", headers=headers, timeout=15).json()
            if fallback_res.get('videos'):
                for v in fallback_res['videos']:
                    potential_url = v['video_files'][0]['link']
                    if potential_url not in used_videos:
                        video_url = potential_url
                        used_videos.add(video_url)
                        break
                if not video_url:
                    video_url = fallback_res['videos'][0]['video_files'][0]['link']

        if not video_url:
            raise ValueError("No video found on primary and fallback search.")

        vid_path = f"vid_{i}.mp4"
        with open(vid_path, "wb") as f:
            f.write(requests.get(video_url, timeout=30).content)
            
        clip = VideoFileClip(vid_path)
        if clip.duration < visual_duration:
            clip = clip.fx(vfx.loop, duration=visual_duration)
        else:
            clip = clip.subclip(0, visual_duration)
            
        clip_to_close = clip
        clip = clip.resize(height=TARGET_H)
        if clip.w < TARGET_W:
            clip = clip.resize(width=TARGET_W)
        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=TARGET_W, height=TARGET_H)
        
        zoomed_clip = clip.resize(lambda t: 1.0 + 0.04 * (t / visual_duration)).set_position(('center', 'center'))
        
    except Exception as e:
        print(f"⚠️ Pexels Error on scene {i} '{keyword}': {e}. Using solid background.")
        zoomed_clip = ColorClip(size=(TARGET_W, TARGET_H), color=(20, 20, 20)).set_duration(visual_duration)

    final_scene = CompositeVideoClip([zoomed_clip], size=(TARGET_W, TARGET_H)).set_duration(visual_duration)
    
    temp_scene_path = f"temp_scene_{i}.mp4"
    final_scene.write_videofile(temp_scene_path, fps=24, codec="libx264", audio=False, preset="ultrafast", threads=2)
    rendered_scene_paths.append(temp_scene_path)
    
    final_scene.close()
    zoomed_clip.close()
    if clip_to_close:
        clip_to_close.close()
    
    if whoosh_sfx: audio_clips.append(whoosh_sfx.set_start(current_time))
    if pop_sfx: audio_clips.append(pop_sfx.set_start(current_time + 0.1))
            
    current_time += scene_duration
    print(f"Scene {i+1} Ready & Saved: {keyword}")

# 2. Cinematic Crossfade Transitions
loaded_clips = []
for i, path in enumerate(rendered_scene_paths):
    c = VideoFileClip(path)
    if i > 0:
        c = c.fx(vfx.crossfadein, CROSSFADE_DUR)
    loaded_clips.append(c)

final_video = concatenate_videoclips(loaded_clips, padding=-CROSSFADE_DUR, method="compose")

final_duration = final_video.duration
progress_bar = ColorClip(size=(TARGET_W, 15), color=(255, 0, 0))
progress_bar = progress_bar.set_position(lambda t: (-TARGET_W + int(TARGET_W * (t / max(final_duration, 1))), 'bottom'))
progress_bar = progress_bar.set_duration(final_duration)
final_video = CompositeVideoClip([final_video, progress_bar])

try:
    logo = (ImageClip("logo.png")
            .resize(width=200) 
            .set_position(("right", "top")) 
            .margin(right=40, top=40, opacity=0) 
            .set_opacity(0.85) 
            .set_duration(final_duration))
    final_video = CompositeVideoClip([final_video, logo])
except Exception as e:
    pass

print("Exporting Voiceover Track...")
final_voice_audio = CompositeAudioClip(audio_clips)
final_voice_audio.write_audiofile("voice_merged.wav", fps=44100)

print("Rendering Visuals (No Audio)...")
final_video.write_videofile("temp_video_no_audio.mp4", fps=24, codec="libx264", audio=False, preset="ultrafast", threads=2)

final_video.close()
for c in loaded_clips:
    c.close()

# 3. Smart Audio Ducking using FFmpeg
print("Applying Cinematic Audio Ducking & Finalizing Video...")
if os.path.exists("bgm.mp3"):
    studio_filter = "[1:a]asplit=2[voice_main][voice_control];[2:a]volume=0.3[bgm_low];[bgm_low][voice_control]sidechaincompress=threshold=0.08:ratio=8:attack=200:release=1000[ducked_bgm];[voice_main][ducked_bgm]amix=inputs=2:duration=first[aout]"
    
    subprocess.run([
        'ffmpeg', '-y',
        '-i', 'temp_video_no_audio.mp4',
        '-i', 'voice_merged.wav',
        '-stream_loop', '-1', '-i', 'bgm.mp3',
        '-filter_complex', studio_filter,
        '-map', '0:v', '-map', '[aout]',
        '-c:v', 'copy', 
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest', 'final_video.mp4'
    ], check=True)
else:
    subprocess.run([
        'ffmpeg', '-y',
        '-i', 'temp_video_no_audio.mp4',
        '-i', 'voice_merged.wav',
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
        'final_video.mp4'
    ], check=True)

# Upload System
video_link = "Upload Failed"
try:
    res = requests.post("https://tmpfiles.org/api/v1/upload", files={'file': open('final_video.mp4', 'rb')}, timeout=600)
    if res.status_code == 200: video_link = res.json()['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
except: pass

if not video_link.startswith("http"):
    try:
        res = requests.post("https://0x0.st", files={'file': open('final_video.mp4', 'rb')}, timeout=600)
        if res.text.startswith("http"): video_link = res.text.strip()
    except: pass

try:
    final_msg = f"READY_TO_UPLOAD|{video_link}|{video_title}|{thumbnail_prompt}|{video_desc}"
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": final_msg})
except: pass
