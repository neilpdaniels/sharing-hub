from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('account', '0026_backfill_transaction_payment_methods')]
    operations = [
        migrations.CreateModel(name='SocialIdentity', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('provider', models.CharField(choices=[('google', 'Google'), ('apple', 'Apple')], max_length=16)),
            ('provider_subject', models.CharField(max_length=255)), ('provider_email', models.EmailField(blank=True, default='', max_length=254)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('last_used_at', models.DateTimeField(auto_now=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='social_identities', to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.AddConstraint(model_name='socialidentity', constraint=models.UniqueConstraint(fields=('provider', 'provider_subject'), name='unique_social_provider_subject')),
    ]
