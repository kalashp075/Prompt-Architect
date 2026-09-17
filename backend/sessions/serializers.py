from rest_framework import serializers

from .models import GeneratedPrompt, PromptSession, Specification


class SpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specification
        fields = (
            "goal", "requirements", "preferences", "constraints",
            "assumptions", "unknowns", "answers", "custom_requirements",
        )


class GeneratedPromptSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedPrompt
        fields = ("content", "created_at")


class PromptSessionSerializer(serializers.ModelSerializer):
    specification = SpecificationSerializer(read_only=True)
    generated_prompt = GeneratedPromptSerializer(read_only=True)

    class Meta:
        model = PromptSession
        fields = (
            "id", "raw_input", "target_category", "status", "created_at",
            "updated_at", "specification", "generated_prompt",
        )


class CreateSessionSerializer(serializers.Serializer):
    raw_input = serializers.CharField(min_length=10, max_length=4000)
    target_category = serializers.ChoiceField(choices=PromptSession.TargetCategory.choices)


class AnswersSerializer(serializers.ListSerializer):
    child = serializers.DictField()


class CustomRequirementsSerializer(serializers.Serializer):
    custom_requirements = serializers.CharField(allow_blank=True, max_length=4000)


class SpecificationUpdateSerializer(serializers.Serializer):
    goal = serializers.CharField()
    requirements = serializers.ListField(child=serializers.CharField())
    preferences = serializers.ListField(child=serializers.CharField())
    constraints = serializers.ListField(child=serializers.CharField())
    assumptions = serializers.ListField(child=serializers.CharField())
    unknowns = serializers.ListField(child=serializers.DictField())
    answers = serializers.ListField(child=serializers.DictField())
    custom_requirements = serializers.CharField(allow_blank=True)
