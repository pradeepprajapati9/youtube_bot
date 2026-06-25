"""Assemble a faceless multi-scene vertical Short (moviepy + bundled ffmpeg).

Each scene = its own voiceover + visual (image with Ken-Burns zoom, or video)
+ synced captions. Scenes are concatenated; optional background music is mixed
in if assets/music.mp3 exists.
"""
import os
from moviepy import (
    VideoFileClip, ImageClip, TextClip, AudioFileClip,
    CompositeVideoClip, CompositeAudioClip, ColorClip, concatenate_videoclips,
)
import config

W, H = config.WIDTH, config.HEIGHT


def _font():
    candidates = (
        config.FONT_PATH,
        r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arial.ttf",
        # Linux / GitHub Actions runners
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for f in candidates:
        if os.path.exists(f):
            return f
    return None


def _fit_cover(clip):
    scale = max(W / clip.w, H / clip.h)
    clip = clip.resized(scale)
    return clip.cropped(x_center=clip.w / 2, y_center=clip.h / 2, width=W, height=H)


def _visual(path: str, kind: str, duration: float):
    """A background clip for one scene, exactly `duration` long."""
    if kind == "video" and os.path.exists(path):
        try:
            clip = _fit_cover(VideoFileClip(path).without_audio())
            if clip.duration < duration:
                n = int(duration / clip.duration) + 1
                clip = concatenate_videoclips([clip] * n)
            return clip.subclipped(0, duration)
        except Exception as ex:
            print(f"[editor] video scene failed ({ex})")
    if os.path.exists(path):
        # Ken-Burns via PAN: enlarge the image ONCE (static resize, cheap) and
        # translate it across the frame. Avoids per-frame resampling = much faster.
        img = ImageClip(path).resized(1.15).with_duration(duration)
        max_dx, max_dy = img.w - W, img.h - H
        d = max(duration, 0.1)
        pos = lambda t: (-max_dx * (t / d), -max_dy * (t / d))
        return CompositeVideoClip([img.with_position(pos)],
                                  size=(W, H)).with_duration(duration)
    return ColorClip((W, H), color=(18, 22, 38)).with_duration(duration)


def _chunks(text: str, max_words=4):
    words, out, cur = text.split(), [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words:
            out.append(" ".join(cur)); cur = []
    if cur:
        out.append(" ".join(cur))
    return out or [text]


def _captions(text: str, duration: float, font):
    chunks = _chunks(text)
    per = duration / len(chunks)
    clips = []
    for i, t in enumerate(chunks):
        kw = dict(text=t, font_size=80, color="white", stroke_color="black",
                  stroke_width=6, method="caption", size=(int(W * 0.84), None),
                  text_align="center")
        if font:
            kw["font"] = font
        try:
            tc = TextClip(**kw)
        except TypeError:
            kw.pop("text_align", None)
            tc = TextClip(**kw)
        clips.append(tc.with_start(i * per).with_duration(per)
                       .with_position(("center", int(H * 0.60))))
    return clips


def _scene_clip(scene: dict, font):
    audio = AudioFileClip(scene["voice_path"])
    dur = max(audio.duration - 0.02, 0.5)
    audio = audio.subclipped(0, dur)

    bg = _visual(scene["visual_path"], scene["visual_kind"], dur)
    overlay = ColorClip((W, H), color=(0, 0, 0)).with_opacity(0.30).with_duration(dur)
    caps = _captions(scene["narration"], dur, font)
    return (CompositeVideoClip([bg, overlay, *caps], size=(W, H))
            .with_audio(audio).with_duration(dur))


def _add_music(video):
    """Mix assets/music.mp3 under the narration if it exists (optional)."""
    music_path = config.ASSETS_DIR / "music.mp3"
    if not music_path.exists():
        return video
    try:
        from moviepy.audio.fx import MultiplyVolume
        m = AudioFileClip(str(music_path))
        total = video.duration
        if m.duration < total:
            from moviepy import concatenate_audioclips
            n = int(total / m.duration) + 1
            m = concatenate_audioclips([m] * n)
        m = m.subclipped(0, total).with_effects([MultiplyVolume(0.12)])
        mixed = CompositeAudioClip([video.audio, m])
        return video.with_audio(mixed)
    except Exception as ex:
        print(f"[editor] music skip ({ex})")
        return video


def build_slideshow(scenes: list[dict], out_path: str) -> str:
    """scenes: [{narration, visual_path, visual_kind, voice_path}, ...]"""
    font = _font()
    clips, total = [], 0.0
    for sc in scenes:
        clip = _scene_clip(sc, font)
        if total + clip.duration > config.MAX_SECONDS:
            break  # keep it a Short
        clips.append(clip)
        total += clip.duration

    final = concatenate_videoclips(clips, method="compose")
    final = _add_music(final)
    final.write_videofile(
        out_path, fps=config.FPS, codec="libx264", audio_codec="aac",
        preset="veryfast", threads=4, logger=None,
    )
    return out_path
