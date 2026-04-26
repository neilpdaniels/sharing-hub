from django.db import migrations, models
import account.validators


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='mobile_number',
            field=models.CharField(default='', max_length=20),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='RegistrationVerification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('first_name', models.CharField(max_length=150)),
                ('last_name', models.CharField(max_length=150)),
                ('date_of_birth', models.DateField(validators=[account.validators.MinAgeValidator])),
                ('mobile_number', models.CharField(max_length=20)),
                ('address_line_1', models.CharField(max_length=255)),
                ('address_line_2', models.CharField(blank=True, max_length=255, null=True)),
                ('town', models.CharField(max_length=255)),
                ('county', models.CharField(blank=True, max_length=255, null=True)),
                ('postcode', models.CharField(max_length=8)),
                ('verification_code', models.CharField(max_length=6, unique=True)),
                ('expires_at', models.DateTimeField()),
                ('is_used', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='registrationverification',
            index=models.Index(fields=['email', 'is_used'], name='account_regi_email_a878fd_idx'),
        ),
        migrations.AddIndex(
            model_name='registrationverification',
            index=models.Index(fields=['expires_at'], name='account_regi_expires_c64689_idx'),
        ),
    ]
