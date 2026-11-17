import subprocess
from typing import List
def run_command(cmd: List[str], cwd: str | None = None) -> None:
    print("\n$ " + " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=cwd)
def extract_audio(video_path: str, audio_path: str) -> None:
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", audio_path]
    run_command(cmd)
