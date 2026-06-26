"""Text -> speech using edge-tts (FREE neural voices, no API key).

Returns precise per-WORD timings (from edge-tts WordBoundary events) so the
editor can show captions perfectly synced to the speech - a big retention boost.
"""
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


def make_voiceover(text: str, out_path: str):
    """Generate an mp3 voiceover. Returns a list of {word, start, end} timings."""
    return asyncio.run(_synthesize(text, out_path, config.VOICE, config.VOICE_RATE))


if __name__ == "__main__":
    w = make_voiceover("This is a test of the free voiceover system.",
                       str(config.OUTPUT_DIR / "test_voice.mp3"))
    print("words:", w)
