from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0032_moderationreport'),
    ]

    operations = [
        migrations.AlterField(
            model_name='moderationreport',
            name='reporter',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='submitted_moderation_reports',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='moderationreport',
            name='anonymous_fingerprint',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                editable=False,
                help_text='One-way fingerprint used only for anonymous report rate limits and abuse blocking.',
                max_length=64,
            ),
        ),
    ]
