from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0029_alter_bestpricedforcategory_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='categories',
            field=models.ManyToManyField(blank=True, related_name='products', to='common.Category'),
        ),
    ]
