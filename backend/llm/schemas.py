from pydantic import BaseModel, Field


class Unknown(BaseModel):
    question: str
    priority: int = Field(ge=1, le=5)


class AssumptionProvenance(BaseModel):
    text: str
    source: str


class AnalysisSpec(BaseModel):
    goal: str
    requirements: list[str]
    preferences: list[str]
    constraints: list[str]
    assumptions: list[str]
    assumption_provenance: list[AssumptionProvenance] = Field(default_factory=list)
    unknowns: list[Unknown]


class CustomRequirementMerge(BaseModel):
    added_preferences: list[str]
    added_constraints: list[str]
    conflicts: list[str]


class ClarificationQuestion(BaseModel):
    question: str


class UpdatedAnalysisSpec(AnalysisSpec):
    pass
