import os, requests, json, subprocess, socket, time
import moviepy.editor as mpe
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, concatenate_videoclips, vfx, afx, ColorClip

full_text = os.environ.get('FULL_TEXT', 'एक बार की बात है।')
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))

# Naye environment variables
video_title = os.environ.get('TITLE', 'Business Case Study')
thumbnail_prompt = os.environ.get('THUMBNAIL_PROMPT', 'Cinematic business thumbnail')
video_desc = os.environ.get('DESCRIPTION', 'Business case study video.')
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '8798779179:AAH53t28qW6g7QTsB8nGCEswNJz2DXR9ssU')

print(f"Total Scenes to render: {len(scenes_data)}")

# Text to Speech generation
subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', full_text, '--write-media', 'voiceover.mp3'])

raw_voiceover = AudioFileClip("voiceover.mp3")
if raw_voiceover.duration > 1.0:
    voiceover = raw_voiceover.subclip(0.3)
else:
    voiceover = raw_voiceover

total_chars = sum(len(s['text']) for s in scenes_data)

rendered_scene_paths = []
audio_clips = [voiceover]
headers = {"Authorization": pexels_key}
current_time = 0.0

try:
    whoosh_sfx = AudioFileClip("whoosh.mp3").volumex(0.25)
    pop_sfx = AudioFileClip("pop.mp3").volumex(0.15)        
except:
    whoosh_sfx = pop_sfx = None

TARGET_W, TARGET_H = 1920, 1080

for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'business')
    text_line = scene.get('text', '')
    scene_duration = voiceover.duration * (len(text_line) / max(total_chars, 1))
    if scene_duration < 1.0: scene_duration = 1.0
    
    clip_to_close = None
    
    try:
        res = requests.get(f"https://api.pexels.com/videos/search?query={keyword}&per_page=1&orientation=landscape", headers=headers, timeout=15).json()
        if not res.get('videos'):
            raise ValueError(f"No videos found on Pexels for keyword: '{keyword}'")
            
        video_url = res['videos'][0]['video_files'][0]['link']
        vid_path = f"vid_{i}.mp4"
        with open(vid_path, "wb") as f:
            f.write(requests.get(video_url, timeout=30).content)
            
        clip = VideoFileClip(vid_path).subclip(0, scene_duration)
        clip_to_close = clip
        clip = clip.resize(height=TARGET_H)
        if clip.w < TARGET_W:
            clip = clip.resize(width=TARGET_W)
        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=TARGET_W, height=TARGET_H)
        
        zoomed_clip = clip.resize(lambda t: 1.0 + 0.04 * (t / scene_duration)).set_position(('center', 'center'))
        
    except Exception as e:
        print(f"⚠️ API/Download Error on scene {i} '{keyword}': {e}. Using fallback background.")
        zoomed_clip = ColorClip(size=(TARGET_W, TARGET_H), color=(20, 20, 20)).set_duration(scene_duration)

    # TEXT REMOVED: Ab sirf clean B-roll video render hoga
    final_scene = CompositeVideoClip([zoomed_clip], size=(TARGET_W, TARGET_H)).set_duration(scene_duration)
    
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

loaded_clips = [VideoFileClip(path) for path in rendered_scene_paths]
final_video = concatenate_videoclips(loaded_clips, method="compose")

# Niche ek choti si red progress bar chhod di hai retention ke liye
final_duration = final_video.duration
progress_bar = ColorClip(size=(TARGET_W, 15), color=(255, 0, 0))
progress_bar = progress_bar.set_position(lambda t: (-TARGET_W + int(TARGET_W * (t / max(final_duration, 1))), 'bottom'))
progress_bar = progress_bar.set_duration(final_duration)
final_video = CompositeVideoClip([final_video, progress_bar])

try:
    bgm = AudioFileClip("bgm.mp3").volumex(0.32)
    if bgm.duration < final_video.duration: bgm = afx.audio_loop(bgm, duration=final_video.duration)
    else: bgm = bgm.subclip(0, final_video.duration)
    audio_clips.append(bgm)
except: pass

final_audio = CompositeAudioClip(audio_clips)
final_video = final_video.set_audio(final_audio)

print("Rendering Final COMPRESSED LONG Video...")
final_video.write_videofile("final_video.mp4", fps=24, codec="libx264", audio_codec="aac", threads=2, bitrate="1000k", preset="ultrafast")

final_video.close()
for c in loaded_clips:
    c.close()

print("Starting Upload System...")
video_link = "Upload Failed"

try:
    print("Trying Tmpfiles API...")
    res = requests.post("https://tmpfiles.org/api/v1/upload", files={'file': open('final_video.mp4', 'rb')}, timeout=600)
    if res.status_code == 200: video_link = res.json()['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
except Exception as e: print(f"Tmpfiles failed: {e}")

if not video_link.startswith("http"):
    try:
        print("Trying 0x0.st API...")
        res = requests.post("https://0x0.st", files={'file': open('final_video.mp4', 'rb')}, timeout=600)
        if res.text.startswith("http"): video_link = res.text.strip()
    except Exception as e: print(f"0x0.st failed: {e}")

print(f"🔥 FINAL VIDEO LINK: {video_link} 🔥")

# Telegram trigger for n8n
try:
    final_msg = f"READY_TO_UPLOAD|{video_link}|{video_title}|{thumbnail_prompt}|{video_desc}"
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": final_msg})
    print("✅ Successfully sent trigger to Telegram!")
except Exception as e:
    print(f"⚠️ Failed to send to Telegram: {e}")
