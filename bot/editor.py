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
    # Devanagari-capable fonts (needed for Hindi captions)
    hindi = [r"C:\Windows\Fonts\NirmalaB.ttf", r"C:\Windows\Fonts\Nirmala.ttf",
             r"C:\Windows\Fonts\Nirmala.ttc", r"C:\Windows\Fonts\mangal.ttf",
             "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
             "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf"]
    latin = [config.FONT_PATH, r"C:\Windows\Fonts\segoeuib.ttf",
             r"C:\Windows\Fonts\arial.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    # for Hindi, try Devanagari fonts first
    candidates = (hindi + latin) if config.LANG == "hi" else (latin + hindi)
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
        # Ken-Burns via PAN: enlarge the image ONCE (cheap static resize) and
        # translate it across the frame. Direction varies per scene so the motion
        # doesn't feel repetitive. No per-frame resampling = fast.
        img = ImageClip(path).resized(1.18).with_duration(duration)
        mx, my = img.w - W, img.h - H
        d = max(duration, 0.1)
        # 4 pan directions chosen deterministically from the file name
        variant = sum(ord(c) for c in os.path.basename(path)) % 4
        corners = [((0, 0), (-mx, -my)), ((-mx, 0), (0, -my)),
                   ((0, -my), (-mx, 0)), ((-mx, -my), (0, 0))]
        (sx, sy), (ex, ey) = corners[variant]
        pos = lambda t: (sx + (ex - sx) * t / d, sy + (ey - sy) * t / d)
        return CompositeVideoClip([img.with_position(pos)],
                                  size=(W, H)).with_duration(duration)
    return ColorClip((W, H), color=(18, 22, 38)).with_duration(duration)


def _make_text(text: str, font):
    kw = dict(text=text.upper(), font_size=82, color="white", stroke_color="black",
              stroke_width=7, method="caption", size=(int(W * 0.82), None),
              text_align="center")
    if font:
        kw["font"] = font
    try:
        return TextClip(**kw)
    except TypeError:
        kw.pop("text_align", None)
        return TextClip(**kw)


def _word_captions(words: list, duration: float, font):
    """Captions perfectly synced to speech (from edge-tts word timings).
    Shows up to 3 words at a time, advancing exactly as they're spoken."""
    groups = []
    i = 0
    while i < len(words):
        grp = words[i:i + 3]
        groups.append({"text": " ".join(w["word"] for w in grp),
                       "start": grp[0]["start"]})
        i += 3
    clips = []
    for j, g in enumerate(groups):
        start = g["start"]
        end = groups[j + 1]["start"] if j + 1 < len(groups) else duration
        end = min(end, duration)
        if end - start < 0.05:
            continue
        tc = (_make_text(g["text"], font)
              .with_start(start).with_duration(end - start)
              .with_position(("center", int(H * 0.55))))
        clips.append(tc)
    return clips


def _even_captions(text: str, duration: float, font):
    """Fallback when no word timings are available: split text evenly."""
    words = text.split()
    chunks = [" ".join(words[i:i + 3]) for i in range(0, len(words), 3)] or [text]
    per = duration / len(chunks)
    return [(_make_text(t, font).with_start(k * per).with_duration(per)
             .with_position(("center", int(H * 0.55)))) for k, t in enumerate(chunks)]


def _latin_font():
    """A Latin font for the English subtitle line (Devanagari fonts may lack Latin)."""
    for f in (config.FONT_PATH, r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return f
    return None


def _english_caption(text: str, duration: float):
    """A static smaller English translation line shown below the main captions."""
    kw = dict(text=text, font_size=48, color="#ffe14d", stroke_color="black",
              stroke_width=4, method="caption", size=(int(W * 0.86), None),
              text_align="center")
    f = _latin_font()
    if f:
        kw["font"] = f
    try:
        tc = TextClip(**kw)
    except TypeError:
        kw.pop("text_align", None)
        tc = TextClip(**kw)
    return tc.with_duration(duration).with_position(("center", int(H * 0.72)))


def _scene_clip(scene: dict, font):
    audio = AudioFileClip(scene["voice_path"])
    dur = max(audio.duration - 0.02, 0.5)
    audio = audio.subclipped(0, dur)

    bg = _visual(scene["visual_path"], scene["visual_kind"], dur)
    overlay = ColorClip((W, H), color=(0, 0, 0)).with_opacity(0.30).with_duration(dur)
    words = scene.get("words")
    caps = _word_captions(words, dur, font) if words else _even_captions(
        scene["narration"], dur, font)
    layers = [bg, overlay, *caps]
    # for Hindi videos, add an English subtitle line so more people can follow
    if config.LANG == "hi" and scene.get("narration_en"):
        layers.append(_english_caption(scene["narration_en"], dur))
    return (CompositeVideoClip(layers, size=(W, H))
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


def build_slideshow(scenes: list[dict], out_path: str, max_seconds: float = None) -> str:
    """scenes: [{narration, visual_path, visual_kind, voice_path}, ...]

    max_seconds caps total length; defaults to config.MAX_SECONDS (Shorts).
    Pass a larger value (e.g. from longform.py) for regular long-form videos.
    """
    cap = max_seconds or config.MAX_SECONDS
    font = _font()
    clips, total = [], 0.0
    for sc in scenes:
        clip = _scene_clip(sc, font)
        if total + clip.duration > cap:
            break  # length limit reached
        clips.append(clip)
        total += clip.duration

    final = concatenate_videoclips(clips, method="compose")
    # gentle fade in/out for a polished intro/outro
    try:
        from moviepy import vfx
        final = final.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
    except Exception as ex:
        print(f"[editor] fade skipped ({ex})")
    final = _add_music(final)
    final.write_videofile(
        out_path, fps=config.FPS, codec="libx264", audio_codec="aac",
        preset="veryfast", threads=4, logger=None,
    )
    return out_path
