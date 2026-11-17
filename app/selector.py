import json
import re

from app import config
from app.models import CandidateClip, Segment


def select_clips(
    segments: list[Segment],
    clips_count: int,
    min_duration: float,
    max_duration: float,
) -> list[CandidateClip]:
    if not segments:
        return []

    clips: list[CandidateClip] = []

    if config.llm_enabled():
        try:
            clips = _select_with_llm(segments, clips_count, min_duration, max_duration)
            print(f"LLM a returnat {len(clips)} clipuri.")
        except Exception as e:
            print(f"LLM selection a esuat, fallback la heuristic: {e}")
            clips = []

    # Completeaza cu heuristic daca LLM a dat putine / zero clipuri
    if len(clips) < clips_count:
        extra = _select_heuristic(segments, clips_count * 2, min_duration, max_duration)
        for clip in extra:
            if len(clips) >= clips_count:
                break
            if not _overlaps_existing(clip, clips):
                clips.append(clip)

    return clips[:clips_count]


def _select_with_llm(
    segments: list[Segment],
    clips_count: int,
    min_duration: float,
    max_duration: float,
) -> list[CandidateClip]:
    from openai import OpenAI

    client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL or None)

    lines = []
    total = 0
    max_chars = 30000
    for s in segments:
        line = f"[{s.id}] {s.start:.2f}-{s.end:.2f}: {s.text}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    transcript_text = "\n".join(lines)

    prompt = f"""Ești un editor video specializat în clipuri virale pentru TikTok, YouTube Shorts și Instagram Reels.

Analizează transcript-ul de mai jos și alege cele mai bune {clips_count} momente.

Reguli:
1. Fiecare clip trebuie să aibă între {min_duration:.0f} și {max_duration:.0f} secunde.
2. Folosește DOAR timestamp-urile existente în transcript. NU inventa timestamp-uri.
3. Clipul trebuie să înceapă cu un hook puternic (în primele 2 secunde) și să se încheie cu o concluzie, NU în mijlocul propoziției.
4. Prioritizează: emoție, conflict, informație utilă, umor, declarații puternice, povești.
5. Evită momentele moarte, fără context sauonly cu filler.
6. Pentru fiecare clip scrie un TITLU scurt și captivant (max 60 caractere), un HOOK de 1 rand și 3-5 HASHTAG-uri relevante.
7. Returnează DOAR JSON valid, fără markdown, fără texte în afara JSON-ului.

Format JSON:
{{
  "clips": [
    {{
      "title": "titlu scurt captivant",
      "hook": "o fraza de carlig",
      "start": 123.45,
      "end": 168.90,
      "reason": "de ce este bun clipul",
      "hashtags": ["hash1", "hash2", "hash3"]
    }}
  ]
}}

Transcript:
{transcript_text}
"""

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )
    data = _extract_json(response.choices[0].message.content)

    candidates = []
    for item in data.get("clips", []):
        try:
            candidates.append(
                CandidateClip(
                    title=str(item.get("title", "Clip"))[:80],
                    start=float(item["start"]),
                    end=float(item["end"]),
                    reason=str(item.get("reason", "")),
                    hashtags=list(item.get("hashtags", [])),
                )
            )
        except Exception:
            continue

    return _validate_candidates(candidates, segments, clips_count, min_duration, max_duration)


def _select_heuristic(
    segments: list[Segment],
    clips_count: int,
    min_duration: float,
    max_duration: float,
) -> list[CandidateClip]:
    scored = []
    target = min(max_duration, max(min_duration, 30.0))
    for i, start_seg in enumerate(segments):
        start = start_seg.start
        end = start
        cur = []
        for seg in segments[i:]:
            cur.append(seg)
            end = seg.end
            if end - start >= target or end - start > max_duration:
                break
        if not cur:
            continue
        duration = end - start
        if duration < min_duration:
            continue
        if duration > max_duration:
            end = start + max_duration
        text = " ".join(s.text for s in cur)
        score = min(duration / 60.0, 2.0)
        tl = text.lower()
        if "?" in text:
            score += 1.0
        if "!" in text:
            score += 0.8
        for k in ["important", "atenție", "greșeală", "greșeli", "secret", "niciodată",
                  "bani", "succes", "idee", "lecție", "sfat", "problemă", "soluție",
                  "rezultat", "poveste", "întrebare"]:
            if k in tl:
                score += 0.4
        scored.append((score, CandidateClip(title=text[:60], start=start, end=end, reason="Heuristic")))

    scored.sort(key=lambda x: x[0], reverse=True)
    chosen = []
    for _, cand in scored:
        if len(chosen) >= clips_count:
            break
        if not _overlaps_existing(cand, chosen):
            chosen.append(cand)
    chosen.sort(key=lambda x: x.start)
    return chosen


def _validate_candidates(candidates, segments, clips_count, min_duration, max_duration):
    if not candidates:
        return []
    video_end = max(s.end for s in segments) if segments else 0.0
    valid = []
    for c in candidates:
        start = max(0.0, float(c.start) - 0.3)
        end = float(c.end) + 0.3
        if video_end:
            end = min(end, video_end)
        if end <= start:
            continue
        if end - start < min_duration:
            end = start + min_duration
        if end - start > max_duration:
            end = start + max_duration
        if video_end and end > video_end:
            end = video_end
        if end - start < min_duration:
            continue
        valid.append(CandidateClip(title=c.title, start=start, end=end, reason=c.reason, hashtags=c.hashtags))
    valid.sort(key=lambda x: x.start)
    chosen = []
    for c in valid:
        if len(chosen) >= clips_count:
            break
        if not _overlaps_existing(c, chosen):
            chosen.append(c)
    return chosen


def _overlaps_existing(candidate, existing):
    gap = 5.0
    for clip in existing:
        if candidate.start < clip.end + gap and candidate.end > clip.start - gap:
            return True
    return False


def _extract_json(text):
    text = text.strip()
    text = text.replace("```json", "").replace("```", "")
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return {}
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return {}