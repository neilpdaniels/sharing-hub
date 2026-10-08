from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('account', '0024_profile_stripe_connect_fields')]

    operations = [
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_rental_updates', models.BooleanField(default=True)),
                ('email_conversation_messages', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='notification_preferences', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
