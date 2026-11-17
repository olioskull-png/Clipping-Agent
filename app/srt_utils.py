from app.models import Segment
def format_srt_time(seconds: float) -> str:
    if seconds < 0: seconds = 0.0
    ms = int((seconds % 1) * 1000)
    total_seconds = int(seconds)
    hh = total_seconds // 3600
    mm = (total_seconds % 3600) // 60
    ss = total_seconds % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"
def generate_srt_for_clip(segments: list[Segment], clip_start: float, clip_end: float, srt_path: str) -> bool:
    entries = []
    for segment in segments:
        if segment.end <= clip_start or segment.start >= clip_end: continue
        start = max(segment.start, clip_start) - clip_start
        end = min(segment.end, clip_end) - clip_start
        if end <= start: continue
        entries.append((start, end, segment.text.strip()))
    if not entries: return False
    with open(srt_path, "w", encoding="utf-8") as f:
        for index, (start, end, text) in enumerate(entries, start=1):
            if end <= start: end = start + 0.5
            f.write(f"{index}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{text}\n\n")
    return True
