from pydantic import BaseModel, Field


class Unknown(BaseModel):
    question: str
    priority: int = Field(ge=1, le=5)


class AnalysisSpec(BaseModel):
    goal: str
    requirements: list[str]
    preferences: list[str]
    constraints: list[str]
    assumptions: list[str]
    unknowns: list[Unknown]


class CustomRequirementMerge(BaseModel):
    added_preferences: list[str]
    added_constraints: list[str]
    conflicts: list[str]
