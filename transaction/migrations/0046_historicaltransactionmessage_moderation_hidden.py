from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('transaction', '0045_transactionmessage_moderation_hidden')]

    operations = [
        migrations.AddField(
            model_name='historicaltransactionmessage',
            name='moderation_hidden',
            field=models.BooleanField(db_index=True, default=False, help_text='Hidden from members following a confirmed moderation decision.'),
        ),
    ]
