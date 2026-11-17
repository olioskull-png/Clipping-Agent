from dataclasses import dataclass, field
@dataclass
class Segment:
    id: int
    start: float
    end: float
    text: str
@dataclass
class CandidateClip:
    title: str
    start: float
    end: float
    reason: str = ""
    hashtags: list = field(default_factory=list)
