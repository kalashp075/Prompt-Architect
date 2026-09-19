from rest_framework import serializers

from .models import GeneratedPrompt, PromptSession, Specification


class SpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specification
        fields = (
            "goal", "requirements", "preferences", "constraints",
            "assumptions", "assumption_provenance", "unknowns", "answers",
            "custom_requirements",
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
            "updated_at", "question_limit", "question_count", "current_question",
            "assumptions_requested", "specification", "generated_prompt",
        )


class CreateSessionSerializer(serializers.Serializer):
    raw_input = serializers.CharField(min_length=10, max_length=4000)
    target_category = serializers.ChoiceField(choices=PromptSession.TargetCategory.choices)


class AnswersSerializer(serializers.ListSerializer):
    child = serializers.DictField()

    def validate(self, data):
        if len(data) > 20:
            raise serializers.ValidationError("At most 20 answers are allowed.")
        for item in data:
            for key in ("question", "answer"):
                if key in item and (not isinstance(item[key], str) or len(item[key]) > 2000):
                    raise serializers.ValidationError(f"{key} is too long.")
        return data


class QuestionAnswerSerializer(serializers.Serializer):
    answer = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    skipped = serializers.BooleanField(default=False)


class CustomRequirementsSerializer(serializers.Serializer):
    custom_requirements = serializers.CharField(allow_blank=True, max_length=4000)


class SpecificationUpdateSerializer(serializers.Serializer):
    goal = serializers.CharField(max_length=4000)
    requirements = serializers.ListField(child=serializers.CharField(max_length=1000), max_length=50)
    preferences = serializers.ListField(child=serializers.CharField(max_length=1000), max_length=50)
    constraints = serializers.ListField(child=serializers.CharField(max_length=1000), max_length=50)
    assumptions = serializers.ListField(child=serializers.CharField(max_length=1000), max_length=50)
    assumption_provenance = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )
    unknowns = serializers.ListField(child=serializers.DictField(), max_length=20)
    answers = serializers.ListField(child=serializers.DictField(), max_length=20)
    custom_requirements = serializers.CharField(allow_blank=True, max_length=4000)
