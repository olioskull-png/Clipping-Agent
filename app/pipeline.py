import json
import os
from dataclasses import asdict

from app.downloader import download_video
from app.ffmpeg_utils import extract_audio
from app.packager import generate_social_pack
from app.renderer import render_clip
from app.selector import select_clips
from app.srt_utils import generate_srt_for_clip
from app.transcriber import transcribe_audio


def _clip_excerpt(segments, start: float, end: float) -> str:
    parts = [s.text.strip() for s in segments if s.end > start and s.start < end and s.text.strip()]
    return " ".join(parts)


def _save_transcript(job_id: str, language: str, segments) -> str:
    transcript_dir = os.path.join("storage", "transcripts", job_id)
    os.makedirs(transcript_dir, exist_ok=True)
    transcript_path = os.path.join(transcript_dir, "transcript.json")
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "job_id": job_id,
                "language": language,
                "segments": [asdict(s) for s in segments],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return transcript_path


def run_job(
    url: str,
    clips_count: int,
    min_duration: float,
    max_duration: float,
    job_id: str,
    progress_callback=None,
) -> dict:
    def notify(step: str) -> None:
        if progress_callback:
            progress_callback(job_id, step)

    if os.path.isfile(url):
        notify("loading_local_file")
        video_path = url
        info = {
            "title": os.path.splitext(os.path.basename(url))[0],
            "extractor_key": "local",
        }
    else:
        notify("downloading")
        video_path, info = download_video(url, os.path.join("storage", "raw"))

    notify("extracting_audio")
    inter_dir = os.path.join("storage", "intermediate", job_id)
    os.makedirs(inter_dir, exist_ok=True)
    audio_path = os.path.join(inter_dir, "audio.wav")
    extract_audio(video_path, audio_path)

    notify("transcribing")
    segments, language = transcribe_audio(audio_path)
    _save_transcript(job_id, language, segments)

    notify("selecting_clips")
    clips = select_clips(segments, clips_count, min_duration, max_duration)
    if not clips:
        raise RuntimeError("Nu s-au putut selecta clipuri din transcriere.")

    notify("rendering_clips")
    out_dir = os.path.join("output", job_id)
    os.makedirs(out_dir, exist_ok=True)

    rendered_clips = []
    for idx, clip in enumerate(clips, start=1):
        clip_id = f"clip_{idx:03d}"
        srt_path = os.path.join(out_dir, f"{clip_id}.srt")
        mp4_path = os.path.join(out_dir, f"{clip_id}.mp4")

        has_srt = generate_srt_for_clip(segments, clip.start, clip.end, srt_path)
        render_clip(video_path, clip, srt_path if has_srt else None, mp4_path)
        excerpt = _clip_excerpt(segments, clip.start, clip.end)
        social_pack = generate_social_pack(clip, excerpt, language)

        rendered_clips.append(
            {
                "clip_id": clip_id,
                "title": clip.title,
                "start": round(float(clip.start), 2),
                "end": round(float(clip.end), 2),
                "duration": round(float(clip.end) - float(clip.start), 2),
                "reason": clip.reason,
                "hashtags": clip.hashtags,
                "review_status": "pending_review",
                "social": social_pack,
                "file": mp4_path,
                "subtitles": srt_path if has_srt else None,
            }
        )

    metadata = {
        "job_id": job_id,
        "source_url": url,
        "source_platform": info.get("extractor_key", "unknown") if isinstance(info, dict) else "unknown",
        "video_title": info.get("title", "") if isinstance(info, dict) else "",
        "language": language,
        "clips": rendered_clips,
    }
    metadata_path = os.path.join(out_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    notify("completed")
    return metadata
