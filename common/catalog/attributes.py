from common.models import CategoryAttribute


def named_attribute_definitions(category):
    return [
        definition
        for definition in category.get_attribute_definitions()
        if (definition.get('name') or '').strip()
    ]


def filterable_attribute_definitions(category):
    return [
        definition
        for definition in named_attribute_definitions(category)
        if definition.get('filterable')
    ]


def sortable_attribute_definitions(category):
    return [
        definition
        for definition in named_attribute_definitions(category)
        if definition.get('sortable')
    ]


def definitions_for_source(category, source='product'):
    source = source or 'product'
    definitions = named_attribute_definitions(category)
    if source == 'order':
        return definitions
    return [
        definition
        for definition in definitions
        if (definition.get('value_source') or CategoryAttribute.VALUE_SOURCE_PRODUCT) == CategoryAttribute.VALUE_SOURCE_PRODUCT
    ]


def field_name_for_definition(definition, source='product'):
    order = int(definition.get('order') or 0)
    product_field = {
        1: 'attribute_one_value',
        2: 'attribute_two_value',
        3: 'attribute_three_value',
        4: 'attribute_four_value',
        5: 'attribute_five_value',
    }.get(order, '')
    if not product_field:
        return ''
    value_source = definition.get('value_source') or CategoryAttribute.VALUE_SOURCE_PRODUCT
    if source == 'order':
        if value_source == CategoryAttribute.VALUE_SOURCE_LISTING:
            return product_field
        return f'product__{product_field}'
    return product_field


def attribute_sort_options(category):
    options = []
    for definition in sortable_attribute_definitions(category):
        name = (definition.get('name') or '').strip()
        if not name:
            continue
        options.append(
            {
                'value': definition['sort_key_asc'],
                'label': f'{name} (A-Z)',
            }
        )
        options.append(
            {
                'value': definition['sort_key_desc'],
                'label': f'{name} (Z-A)',
            }
        )
    return options


def default_sort_value(category, fallback='az'):
    default_order = int(getattr(category, 'default_sorted_attribute', 0) or 0)
    ascending = bool(getattr(category, 'default_sorted_direction_ascending', True))
    for definition in sortable_attribute_definitions(category):
        if int(definition['order']) == default_order:
            return definition['sort_key_asc'] if ascending else definition['sort_key_desc']
    return fallback


def collect_attribute_filter_options(category, queryset, *, source='product'):
    filters = []
    for definition in definitions_for_source(category, source=source):
        if not definition.get('filterable'):
            continue
        values = [value for value in (definition.get('allowed_values') or []) if value]
        if not values:
            field_name = field_name_for_definition(definition, source=source)
            if not field_name:
                continue
            raw_values = queryset.values_list(field_name, flat=True).distinct()
            values = sorted(value for value in raw_values if value)
        filters.append(
            {
                **definition,
                'field_name': field_name_for_definition(definition, source=source),
                'values': values,
            }
        )
    return filters


def apply_attribute_filters(queryset, category, params, *, source='product'):
    chosen = {}
    for definition in definitions_for_source(category, source=source):
        if not definition.get('filterable'):
            continue
        selected = (params.get(definition['query_param']) or '').strip()
        if not selected:
            selected = (definition.get('default_filtered_value') or '').strip()
        if not selected:
            continue
        field_name = field_name_for_definition(definition, source=source)
        if not field_name:
            continue
        queryset = queryset.filter(**{field_name: selected})
        chosen[definition['query_param']] = selected
    return queryset, chosen


def product_attribute_value(product, definition):
    field_name = field_name_for_definition(definition, source='product')
    return (getattr(product, field_name, '') or '').strip()


def matches_attribute_sort(sort_by, definition):
    return sort_by in {definition['sort_key_asc'], definition['sort_key_desc']}

