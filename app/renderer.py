import os
from app.ffmpeg_utils import run_command
from app.models import CandidateClip


def _escape_ffmpeg_path(path: str) -> str:
    escaped = os.path.abspath(path).replace("\\", "/")
    if ":" in escaped:
        drive, rest = escaped.split(":", 1)
        escaped = f"{drive}\\:{rest}"
    return escaped


def render_clip(
    video_path: str,
    clip: CandidateClip,
    srt_path: str | None,
    output_path: str,
    use_face_tracking: bool = True,
) -> None:
    abs_video = os.path.abspath(video_path)
    abs_output = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    duration = max(0.5, float(clip.end) - float(clip.start))

    crop_x_expr = None
    if use_face_tracking:
        try:
            from app.tracker import build_crop_x_expression

            crop_x_expr = build_crop_x_expression(abs_video, float(clip.start), float(clip.end))
        except Exception as e:
            print(f"Face tracking fallback to center crop: {e}")

    if crop_x_expr:
        crop_filter = f"crop=ih*9/16:ih:'{crop_x_expr}':0"
    else:
        crop_filter = "crop='if(gt(iw/ih,9/16),ih*9/16,iw)':'if(gt(iw/ih,9/16),ih,iw*16/9)'"

    filters = [crop_filter, "scale=1080:1920"]
    if srt_path and os.path.exists(srt_path) and os.path.getsize(srt_path) > 0:
        abs_srt = _escape_ffmpeg_path(srt_path)
        filters.append(f"subtitles='{abs_srt}'")

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(clip.start),
        "-t", str(duration),
        "-i", abs_video,
        "-vf", ",".join(filters),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        abs_output,
    ]
    run_command(cmd, cwd=os.path.dirname(abs_output))
