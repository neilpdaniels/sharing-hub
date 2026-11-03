from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0031_orderimage_processing_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ModerationReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target_type', models.CharField(choices=[('listing', 'Listing'), ('user', 'User'), ('message', 'Message')], db_index=True, max_length=12)),
                ('target_id', models.PositiveIntegerField(db_index=True)),
                ('reason', models.CharField(choices=[('sexual_content', 'Sexual or nudity content'), ('child_safety', 'Child safety concern'), ('threat_or_harassment', 'Threats, harassment or bullying'), ('graphic_violence', 'Graphic violence'), ('illegal_or_unsafe_item', 'Illegal or unsafe item/content'), ('hate_or_discrimination', 'Hate or discrimination'), ('scam_or_fraud', 'Scam or fraud'), ('other', 'Other objectionable content')], db_index=True, max_length=32)),
                ('details', models.TextField(blank=True, default='', max_length=1500)),
                ('target_snapshot', models.JSONField(blank=True, default=dict)),
                ('content_hidden_pending_review', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('open', 'New'), ('reviewing', 'Reviewing'), ('resolved', 'Resolved')], db_index=True, default='open', max_length=12)),
                ('outcome', models.CharField(blank=True, choices=[('remove_and_block_author', 'Remove content and block posting user'), ('dismiss_report', 'Dismiss report; allow content'), ('dismiss_and_block_reporter', 'Dismiss abusive report and block reporter')], default='', max_length=32)),
                ('moderator_notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='submitted_moderation_reports', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_moderation_reports', to=settings.AUTH_USER_MODEL)),
                ('target_owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='received_moderation_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.AddIndex(
            model_name='moderationreport',
            index=models.Index(fields=['status', 'target_type', 'target_id'], name='common_mode_status_9aba26_idx'),
        ),
    ]
