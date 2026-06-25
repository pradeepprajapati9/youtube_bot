"""Text -> speech using edge-tts (FREE Microsoft neural voices, no API key)."""
import asyncio
import edge_tts
import config


async def _synthesize(text: str, out_path: str, voice: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def make_voiceover(text: str, out_path: str) -> str:
    """Generate an mp3 voiceover. Returns the path."""
    asyncio.run(_synthesize(text, out_path, config.VOICE))
    return out_path


if __name__ == "__main__":
    p = make_voiceover("This is a test of the free voiceover system.",
                       str(config.OUTPUT_DIR / "test_voice.mp3"))
    print("saved:", p)
