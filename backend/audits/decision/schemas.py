from typing import Literal
from pydantic import BaseModel


class RecommendationResult(BaseModel):
    issue_id: int
    title: str
    effort: Literal['low', 'medium', 'high']
    impact: Literal['low', 'medium', 'high']
    priority_score: float
    rationale: str
