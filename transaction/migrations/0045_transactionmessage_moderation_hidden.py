from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('transaction', '0044_return_auto_resolution_markers')]

    operations = [
        migrations.AddField(
            model_name='transactionmessage',
            name='moderation_hidden',
            field=models.BooleanField(db_index=True, default=False, help_text='Hidden from members following a confirmed moderation decision.'),
        ),
    ]
