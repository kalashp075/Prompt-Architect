from django.db import migrations


def correct_question_limits(apps, schema_editor):
    PromptSession = apps.get_model("prompt_sessions", "PromptSession")
    PromptSession.objects.filter(
        target_category__in=["frontend", "backend", "fullstack"]
    ).update(question_limit=10)
    PromptSession.objects.filter(
        target_category__in=["general", "design"]
    ).update(question_limit=8)


class Migration(migrations.Migration):
    dependencies = [
        ("prompt_sessions", "0005_specification_assumption_provenance"),
    ]

    operations = [
        migrations.RunPython(correct_question_limits, migrations.RunPython.noop),
    ]
