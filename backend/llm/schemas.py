from pydantic import BaseModel, Field


class Unknown(BaseModel):
    question: str = Field(max_length=2000)
    priority: int = Field(ge=1, le=5)


class AssumptionProvenance(BaseModel):
    text: str = Field(max_length=1000)
    source: str = Field(max_length=100)


class AnalysisSpec(BaseModel):
    goal: str = Field(max_length=4000)
    requirements: list[str] = Field(max_length=50)
    preferences: list[str] = Field(max_length=50)
    constraints: list[str] = Field(max_length=50)
    assumptions: list[str] = Field(max_length=50)
    assumption_provenance: list[AssumptionProvenance] = Field(default_factory=list, max_length=50)
    unknowns: list[Unknown] = Field(max_length=20)

    model_config = {"str_max_length": 4000}


class CustomRequirementMerge(BaseModel):
    added_preferences: list[str] = Field(max_length=50)
    added_constraints: list[str] = Field(max_length=50)
    conflicts: list[str] = Field(max_length=20)


class ClarificationQuestion(BaseModel):
    question: str = Field(max_length=2000)


class UpdatedAnalysisSpec(AnalysisSpec):
    pass
