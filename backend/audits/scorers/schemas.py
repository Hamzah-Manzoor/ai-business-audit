from pydantic import BaseModel


class ParameterResult(BaseModel):
    key: str
    score: int
    rationale: str


class CategoryResult(BaseModel):
    category: str
    score: int
    parameters: list[ParameterResult]
    top_issues: list[str]
    summary: str
