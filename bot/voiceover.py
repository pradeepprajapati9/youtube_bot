"""Text -> speech using edge-tts (FREE neural voices, no API key).

Returns precise per-WORD timings (from edge-tts WordBoundary events) so the
editor can show captions perfectly synced to the speech - a big retention boost.
"""
import os
import time
import asyncio
import edge_tts
import config


async def _synthesize(text: str, out_path: str, voice: str, rate: str):
    # boundary="WordBoundary" is required in edge-tts v7 to get per-word timings
    # (the default is SentenceBoundary, which yields none at word level).
    communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7        # 100-ns units -> seconds
                dur = chunk["duration"] / 1e7
                words.append({"word": chunk["text"], "start": start, "end": start + dur})
    return words


def make_voiceover(text: str, out_path: str, retries: int = 3):
    """Generate an mp3 voiceover. Returns a list of {word, start, end} timings.

    edge-tts occasionally returns no audio (a transient Microsoft-side hiccup),
    so retry a few times before giving up instead of failing the whole video.
    """
    last_err = None
    for attempt in range(retries):
        try:
            words = asyncio.run(_synthesize(text, out_path, config.VOICE, config.VOICE_RATE))
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return words
            last_err = RuntimeError("empty audio file")
        except Exception as ex:
            last_err = ex
            print(f"[voiceover] attempt {attempt + 1}/{retries} failed: {ex}")
        time.sleep(2 + attempt * 2)   # 2s, 4s, 6s backoff
    raise RuntimeError(f"voiceover failed after {retries} attempts: {last_err}")


if __name__ == "__main__":
    w = make_voiceover("This is a test of the free voiceover system.",
                       str(config.OUTPUT_DIR / "test_voice.mp3"))
    print("words:", w)
