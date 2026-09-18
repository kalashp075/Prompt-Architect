import uuid

from django.db import models

from accounts.models import User


class PromptSession(models.Model):
    class TargetCategory(models.TextChoices):
        GENERAL = "general", "General"
        DESIGN = "design", "Design/UI"
        FRONTEND = "frontend", "Frontend"
        BACKEND = "backend", "Backend"
        FULLSTACK = "fullstack", "Full Stack"

    class Status(models.TextChoices):
        ANALYZING = "analyzing", "Analyzing"
        AWAITING_ANSWERS = "awaiting_answers", "Awaiting answers"
        GENERATING_ASSUMPTIONS = "generating_assumptions", "Generating assumptions"
        AWAITING_CUSTOM_REQS = "awaiting_custom_reqs", "Awaiting custom requirements"
        READY_FOR_REVIEW = "ready_for_review", "Ready for review"
        GENERATING = "generating", "Generating"
        COMPLETE = "complete", "Complete"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prompt_sessions",
    )
    raw_input = models.TextField()
    target_category = models.CharField(max_length=20, choices=TargetCategory.choices)
    status = models.CharField(max_length=30, choices=Status.choices)
    question_limit = models.PositiveSmallIntegerField(default=8)
    question_count = models.PositiveSmallIntegerField(default=0)
    current_question = models.TextField(blank=True)
    assumptions_requested = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Specification(models.Model):
    session = models.OneToOneField(
        PromptSession, on_delete=models.CASCADE, related_name="specification"
    )
    goal = models.TextField()
    requirements = models.JSONField(default=list)
    preferences = models.JSONField(default=list)
    constraints = models.JSONField(default=list)
    assumptions = models.JSONField(default=list)
    assumption_provenance = models.JSONField(default=list)
    unknowns = models.JSONField(default=list)
    answers = models.JSONField(default=list)
    custom_requirements = models.TextField(blank=True)


class GeneratedPrompt(models.Model):
    session = models.OneToOneField(
        PromptSession, on_delete=models.CASCADE, related_name="generated_prompt"
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
