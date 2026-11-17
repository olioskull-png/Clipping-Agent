import os
import yt_dlp


def download_video(url: str, raw_dir: str) -> tuple[str, dict]:
    os.makedirs(raw_dir, exist_ok=True)
    # Folosim extractor + id pentru a evita coliziunile între platforme (YouTube, TikTok, Instagram, etc.)
    outtmpl = os.path.join(raw_dir, "%(extractor_key)s_%(id)s.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        base = os.path.splitext(filepath)[0]
        mp4_path = base + ".mp4"
        if os.path.exists(mp4_path):
            filepath = mp4_path
        return filepath, info
