"""One-time YouTube authorization. Run this once; it opens a browser,
you log in + allow, and the token is saved to credentials/token.json.
After this, main.py can upload without asking again.
"""
from bot import uploader

if __name__ == "__main__":
    print("Opening browser for YouTube authorization...")
    print("If a browser doesn't open, copy the printed URL into your browser.")
    uploader._get_service()  # triggers the OAuth flow + saves token.json
    print("\n✅ Authorization complete! token.json saved.")
    print("You can now set DO_UPLOAD=true in .env and run main.py to upload.")
