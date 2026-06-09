"""Domain dataclasses — no ORM, no framework."""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class HotPathResult:
    path: str
    label: str
    confidence: float
    hit_count: int


@dataclass
class EmbeddingResult:
    path: str
    label: str
    description: str
    score: float


@dataclass
class NavigationResult:
    path: Optional[str]
    label: Optional[str]
    confidence: float
    layer: str          # L0 | L1 | L2 | MISS
    response_ms: int
    candidates: List[dict] = field(default_factory=list)
    suggestion: Optional[str] = None

    def to_dict(self):
        return {
            "path": self.path,
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "layer": self.layer,
            "response_ms": self.response_ms,
            "candidates": self.candidates,
            "suggestion": self.suggestion,
        }
