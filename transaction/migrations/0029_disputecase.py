from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0028_transaction_deposit_reminder_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DisputeCase',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('case_number', models.CharField(db_index=True, max_length=32, unique=True)),
                ('reason_code', models.CharField(choices=[('missing_rental', 'Missing rental'), ('missing_return', 'Missing return'), ('deposit_contest', 'Deposit contest'), ('general', 'General dispute'), ('dispute_team', 'Dispute team review')], default='general', max_length=32)),
                ('status', models.CharField(choices=[('open', 'Open'), ('needs_info', 'Needs info'), ('under_review', 'Under review'), ('escalated', 'Escalated'), ('resolved', 'Resolved'), ('closed', 'Closed')], default='open', max_length=20)),
                ('outcome', models.CharField(choices=[('pending', 'Pending'), ('lender', 'Lender favoured'), ('borrower', 'Borrower favoured'), ('split', 'Split outcome'), ('void', 'Void / no payout'), ('refund', 'Refund / release'), ('other', 'Other')], default='pending', max_length=20)),
                ('summary', models.TextField(blank=True, default='')),
                ('resolution_notes', models.TextField(blank=True, default='')),
                ('evidence_bundle', models.JSONField(blank=True, default=dict)),
                ('deposit_return_amount', models.FloatField(default=0)),
                ('payment_offset_amount', models.FloatField(default=0)),
                ('sla_due_at', models.DateTimeField(blank=True, null=True)),
                ('escalated_at', models.DateTimeField(blank=True, null=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('amended', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_dispute_cases', to=settings.AUTH_USER_MODEL)),
                ('raised_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='raised_dispute_cases', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_dispute_cases', to=settings.AUTH_USER_MODEL)),
                ('transaction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dispute_cases', to='transaction.transaction')),
            ],
        ),
    ]
