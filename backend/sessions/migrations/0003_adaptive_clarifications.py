from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prompt_sessions", "0002_alter_promptsession_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="promptsession",
            name="assumptions_requested",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="promptsession",
            name="current_question",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="promptsession",
            name="question_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="promptsession",
            name="question_limit",
            field=models.PositiveSmallIntegerField(default=8),
        ),
    ]
