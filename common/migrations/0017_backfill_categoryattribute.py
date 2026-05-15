from django.db import migrations


def _has_attribute_data(name, sortable, filterable, default_filtered_value):
    return bool(name) or bool(sortable) or bool(filterable) or bool(default_filtered_value)


def forwards_func(apps, schema_editor):
    Category = apps.get_model('common', 'Category')
    CategoryAttribute = apps.get_model('common', 'CategoryAttribute')

    attribute_map = (
        (1, 'attribute_one_name', 'attribute_one_sortable', 'attribute_one_filterable', 'attribute_one_default_filtered_value'),
        (2, 'attribute_two_name', 'attribute_two_sortable', 'attribute_two_filterable', 'attribute_two_default_filtered_value'),
        (3, 'attribute_three_name', 'attribute_three_sortable', 'attribute_three_filterable', 'attribute_three_default_filtered_value'),
        (4, 'attribute_four_name', 'attribute_four_sortable', 'attribute_four_filterable', 'attribute_four_default_filtered_value'),
        (5, 'attribute_five_name', 'attribute_five_sortable', 'attribute_five_filterable', 'attribute_five_default_filtered_value'),
    )

    for category in Category.objects.all().iterator():
        for order, name_f, sortable_f, filterable_f, default_f in attribute_map:
            name = getattr(category, name_f, None)
            sortable = getattr(category, sortable_f, False)
            filterable = getattr(category, filterable_f, False)
            default_filtered_value = getattr(category, default_f, None)

            if not _has_attribute_data(name, sortable, filterable, default_filtered_value):
                continue

            CategoryAttribute.objects.update_or_create(
                category=category,
                order=order,
                defaults={
                    'name': name,
                    'sortable': sortable,
                    'filterable': filterable,
                    'default_filtered_value': default_filtered_value,
                },
            )


def reverse_func(apps, schema_editor):
    # Keep migrated rows in place on reverse to avoid deleting user-updated records.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0016_categoryattribute'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
