import json
from app import config
from app.models import CandidateClip


def _normalize_hashtags(raw_tags: list | None) -> list[str]:
    tags = []
    for tag in raw_tags or []:
        clean = str(tag).strip()
        if not clean:
            continue
        if not clean.startswith("#"):
            clean = f"#{clean}"
        if clean not in tags:
            tags.append(clean)
    return tags or ["#shorts", "#reels", "#tiktok"]


def _fallback_pack(clip: CandidateClip, excerpt: str) -> dict:
    tags = _normalize_hashtags(clip.hashtags)
    tags_str = " ".join(tags[:5])
    hook = clip.title.strip() or "Highlight Clip"
    summary = clip.reason.strip() or excerpt[:160].strip()

    return {
        "youtube_shorts": {
            "title": hook[:100],
            "description": f"{summary}\n\n{tags_str}".strip(),
            "hashtags": tags[:5],
        },
        "tiktok": {
            "caption": f"{hook}\n{summary[:120]}\n{tags_str}".strip(),
            "hashtags": tags[:5],
        },
        "instagram_reels": {
            "caption": f"{hook}\n\n{summary}\n\n{tags_str}".strip(),
            "hashtags": tags[:8],
        },
    }


def generate_social_pack(
    clip: CandidateClip,
    transcript_excerpt: str,
    language: str = "en",
) -> dict:
    if not config.llm_enabled():
        return _fallback_pack(clip, transcript_excerpt)

    try:
        from app.llm_client import chat_completion

        prompt = (
            f"Language: {language}\n"
            f"Clip title/hook: {clip.title}\n"
            f"Selection reason: {clip.reason}\n"
            f"Transcript excerpt: {transcript_excerpt[:1000]}\n\n"
            "Return ONLY valid JSON with keys 'youtube_shorts', 'tiktok', 'instagram_reels':\n"
            "- youtube_shorts: {title (<=95 chars), description, hashtags (array of 3-5)}\n"
            "- tiktok: {caption (hook + short CTA), hashtags (array of 3-5)}\n"
            "- instagram_reels: {caption (engaging + save/share CTA), hashtags (array of 5-8)}"
        )
        content = chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are a social media copywriter. Output strict JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            timeout=20.0,
        )
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        data = json.loads(content.strip())

        fallback = _fallback_pack(clip, transcript_excerpt)
        yt = data.get("youtube_shorts") or {}
        tt = data.get("tiktok") or {}
        ig = data.get("instagram_reels") or {}
        return {
            "youtube_shorts": {
                "title": str(yt.get("title") or fallback["youtube_shorts"]["title"])[:100],
                "description": str(yt.get("description") or fallback["youtube_shorts"]["description"]),
                "hashtags": _normalize_hashtags(yt.get("hashtags") or fallback["youtube_shorts"]["hashtags"]),
            },
            "tiktok": {
                "caption": str(tt.get("caption") or fallback["tiktok"]["caption"]),
                "hashtags": _normalize_hashtags(tt.get("hashtags") or fallback["tiktok"]["hashtags"]),
            },
            "instagram_reels": {
                "caption": str(ig.get("caption") or fallback["instagram_reels"]["caption"]),
                "hashtags": _normalize_hashtags(ig.get("hashtags") or fallback["instagram_reels"]["hashtags"]),
            },
        }
    except Exception as e:
        print(f"Social pack fallback for '{clip.title}': {e}")
        return _fallback_pack(clip, transcript_excerpt)
