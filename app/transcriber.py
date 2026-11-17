from faster_whisper import WhisperModel
from app import config
from app.models import Segment
_model = None
def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE_TYPE)
    return _model
def transcribe_audio(audio_path: str) -> tuple[list[Segment], str]:
    model = get_model()
    segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=False)
    result = []
    for i, segment in enumerate(segments, start=1):
        result.append(Segment(id=i, start=float(segment.start), end=float(segment.end), text=segment.text.strip()))
    language = getattr(info, "language", "unknown")
    return result, language
