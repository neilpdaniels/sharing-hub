from django.core.files import File
from django.db import transaction
from django.utils import timezone

from common.models import Category, CategoryAttribute, Order, Product
from transaction.models import Transaction

from .models import CategorySuggestion
from .tasks import send_category_suggestion_decision_email
from .models import CategoryTaxonomyRecommendation


def promote_category_suggestion(suggestion: CategorySuggestion, reviewer) -> Category | Product:
    """Publish the approved product or category proposal and notify the member."""
    if suggestion.status != CategorySuggestion.STATUS_ADMIN_REVIEW:
        raise ValueError('Only suggestions ready for admin review can be promoted.')
    if not suggestion.proposed_parent_id or not suggestion.proposed_description:
        raise ValueError('A target category and description are required before promotion.')

    with transaction.atomic():
        selected = suggestion.generated_images.filter(is_selected=True).first()
        if not selected:
            selected = suggestion.generated_images.first()
        if suggestion.proposal_kind == CategorySuggestion.PROPOSAL_PRODUCT:
            published = Product(
                name=suggestion.normalized_name or suggestion.name,
                category_id=suggestion.proposed_parent,
                description=suggestion.proposed_description,
            )
            if selected and selected.image:
                with selected.image.open('rb') as image_file:
                    published.image.save(selected.image.name.rsplit('/', 1)[-1], File(image_file), save=False)
            published.save()
            suggestion.published_product = published
        else:
            published = Category(
                title=suggestion.normalized_name or suggestion.name,
                parent_category=suggestion.proposed_parent,
                description=suggestion.proposed_description,
            )
            if selected and selected.image:
                with selected.image.open('rb') as image_file:
                    published.image.save(selected.image.name.rsplit('/', 1)[-1], File(image_file), save=False)
            published.save()
            suggestion.published_category = published
        suggestion.status = CategorySuggestion.STATUS_APPROVED
        suggestion.reviewed_by = reviewer
        suggestion.reviewed_at = timezone.now()
        suggestion.promoted_at = timezone.now()
        suggestion.pipeline_error = ''
        suggestion.save()
        transaction.on_commit(lambda: send_category_suggestion_decision_email.delay(suggestion.pk))
    return published


def reject_category_suggestion(suggestion: CategorySuggestion, reviewer) -> None:
    with transaction.atomic():
        suggestion.status = CategorySuggestion.STATUS_REJECTED
        suggestion.reviewed_by = reviewer
        suggestion.reviewed_at = timezone.now()
        if not suggestion.admin_notes:
            suggestion.admin_notes = 'This item is not a fit for the catalogue at the moment.'
        suggestion.save()
        transaction.on_commit(lambda: send_category_suggestion_decision_email.delay(suggestion.pk))


class TaxonomyApplicationError(ValueError):
    """An AI recommendation did not contain a safe, executable tree change."""


def _positive_id(value, label):
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise TaxonomyApplicationError(f'{label} is missing or invalid.') from exc
    if value <= 0:
        raise TaxonomyApplicationError(f'{label} is missing or invalid.')
    return value


def _locked_category(category_id, label):
    try:
        return Category.objects.select_for_update().get(pk=_positive_id(category_id, label))
    except Category.DoesNotExist as exc:
        raise TaxonomyApplicationError(f'{label} no longer exists.') from exc


def _is_descendant(candidate, ancestor):
    current = candidate
    visited = set()
    while current and current.pk not in visited:
        if current.pk == ancestor.pk:
            return True
        visited.add(current.pk)
        current = current.parent_category
    return False


def _merge_categories(source, target):
    if source.pk == target.pk:
        raise TaxonomyApplicationError('A category cannot be merged into itself.')
    if _is_descendant(target, source):
        raise TaxonomyApplicationError('Cannot merge a category into one of its descendants.')

    primary_products = Product.objects.filter(category_id=source)
    primary_count = primary_products.count()
    primary_products.update(category_id=target)

    # Preserve secondary category assignment too, without relying on a fragile
    # bulk through-table update that could violate the M2M unique constraint.
    secondary_products = Product.objects.filter(categories=source).distinct()
    secondary_count = secondary_products.count()
    for product in secondary_products:
        product.categories.remove(source)
        product.categories.add(target)

    child_count = Category.objects.filter(parent_category=source).count()
    Category.objects.filter(parent_category=source).update(parent_category=target)
    source_title = source.title
    source.delete()
    return {
        'operation': 'merge',
        'source_category': source_title,
        'target_category_id': target.pk,
        'primary_products_reassigned': primary_count,
        'secondary_products_reassigned': secondary_count,
        'child_categories_reparented': child_count,
    }


def _merge_categories_into_new(source, target, parent, title, description):
    """Replace two sibling categories with one deliberately named category."""
    if source.pk == target.pk:
        raise TaxonomyApplicationError('Two different categories are required for a new consolidated category.')
    if source.title.strip().casefold() == 'top' or target.title.strip().casefold() == 'top':
        raise TaxonomyApplicationError('The Top category cannot be consolidated.')
    if source.parent_category_id != target.parent_category_id:
        raise TaxonomyApplicationError('New consolidated categories must start with two sibling categories.')
    if source.parent_category_id != parent.pk:
        raise TaxonomyApplicationError('The new category must use the shared parent of both source categories.')
    normalized_title = ' '.join(str(title or '').split())
    if not normalized_title:
        raise TaxonomyApplicationError('A customer-facing name is required for the new consolidated category.')
    if Category.objects.filter(title__iexact=normalized_title).exists():
        raise TaxonomyApplicationError('A category with the proposed consolidated name already exists.')

    source_id, target_id = source.pk, target.pk
    consolidated = Category.objects.create(
        title=normalized_title,
        parent_category=parent,
        description=' '.join(str(description or '').split()),
    )
    source_result = _merge_categories(source, consolidated)
    target_result = _merge_categories(target, consolidated)
    return {
        'operation': 'merge_new',
        'created_category_id': consolidated.pk,
        'created_category_title': consolidated.title,
        'retired_category_ids': [source_id, target_id],
        'primary_products_reassigned': (
            source_result['primary_products_reassigned'] + target_result['primary_products_reassigned']
        ),
        'secondary_products_reassigned': (
            source_result['secondary_products_reassigned'] + target_result['secondary_products_reassigned']
        ),
        'child_categories_reparented': (
            source_result['child_categories_reparented'] + target_result['child_categories_reparented']
        ),
    }


def _retire_category_subtree(source):
    """Delete an entirely empty category branch.

    This is intentionally stricter than a category delete in Django admin: an
    existing order or transaction makes the whole recommendation ineligible,
    rather than allowing a cascade to discard marketplace history.
    """
    if source.title.strip().casefold() == 'top':
        raise TaxonomyApplicationError('The Top category cannot be retired.')

    category_ids = []
    pending_ids = [source.pk]
    while pending_ids:
        category_id = pending_ids.pop()
        if category_id in category_ids:
            continue
        category_ids.append(category_id)
        pending_ids.extend(
            Category.objects.filter(parent_category_id=category_id).values_list('pk', flat=True)
        )

    # Lock each category and product that is about to be removed. A live
    # listing created while staff are reviewing cannot slip through the guard.
    list(Category.objects.select_for_update().filter(pk__in=category_ids))
    products = list(Product.objects.select_for_update().filter(category_id__in=category_ids))
    product_ids = [product.pk for product in products]
    if product_ids:
        raise TaxonomyApplicationError(
            'Not retired: pre-launch taxonomy cleanup only removes genuinely empty category branches. '
            'Use product-worthiness review to prune product templates first.'
        )

    product_count = len(product_ids)
    category_count = len(category_ids)
    source_title = source.title
    source.delete()
    return {
        'operation': 'retire',
        'source_category': source_title,
        'retired_category_count': category_count,
        'retired_product_count': product_count,
    }


def apply_taxonomy_recommendation(recommendation: CategoryTaxonomyRecommendation, reviewer):
    """Apply one approved, validated tree change and retain an audit result.

    This intentionally refuses ambiguous actions. A human can edit the JSON
    proposed action in admin, rather than letting an uncertain model choose a
    destructive fallback.
    """
    if recommendation.status == CategoryTaxonomyRecommendation.STATUS_IMPLEMENTED:
        return recommendation.implementation_result
    action = recommendation.proposed_action or {}
    operation = str(action.get('operation') or '').strip().lower()
    expected_operations = {
        CategoryTaxonomyRecommendation.TYPE_MISSING: {'create'},
        CategoryTaxonomyRecommendation.TYPE_MOVE: {'move'},
        CategoryTaxonomyRecommendation.TYPE_DUPLICATE: {'merge', 'merge_new'},
        CategoryTaxonomyRecommendation.TYPE_RETIRE: {'retire', 'merge'},
        CategoryTaxonomyRecommendation.TYPE_SPLIT: {'split'},
        CategoryTaxonomyRecommendation.TYPE_ATTRIBUTE: {'add_attribute'},
    }
    if operation not in expected_operations.get(recommendation.recommendation_type, set()):
        raise TaxonomyApplicationError('This recommendation has no safe executable action. Edit or reject it instead.')

    with transaction.atomic():
        recommendation = CategoryTaxonomyRecommendation.objects.select_for_update().get(pk=recommendation.pk)
        if operation == 'create':
            title = ' '.join(str(action.get('title') or '').split())
            if not title:
                raise TaxonomyApplicationError('A new category title is required.')
            if Category.objects.filter(title__iexact=title).exists():
                raise TaxonomyApplicationError('A category with that title already exists.')
            parent = _locked_category(action.get('parent_category_id'), 'Parent category')
            category = Category.objects.create(
                title=title,
                parent_category=parent,
                description=' '.join(str(action.get('description') or '').split()),
            )
            result = {'operation': 'create', 'created_category_id': category.pk, 'parent_category_id': parent.pk}
        elif operation == 'move':
            category = _locked_category(action.get('category_id'), 'Category')
            parent = _locked_category(action.get('parent_category_id'), 'New parent category')
            if category.pk == parent.pk or _is_descendant(parent, category):
                raise TaxonomyApplicationError('Cannot move a category beneath itself or one of its descendants.')
            old_parent_id = category.parent_category_id
            category.parent_category = parent
            category.save(update_fields=['parent_category'])
            result = {'operation': 'move', 'category_id': category.pk, 'old_parent_category_id': old_parent_id, 'parent_category_id': parent.pk}
        elif operation == 'merge_new':
            source = _locked_category(action.get('source_category_id'), 'Source category')
            target = _locked_category(action.get('target_category_id'), 'Target category')
            parent = _locked_category(action.get('parent_category_id'), 'New category parent')
            result = _merge_categories_into_new(
                source, target, parent, action.get('title'), action.get('description'),
            )
        elif operation == 'merge' or (operation == 'retire' and action.get('target_category_id')):
            source = _locked_category(action.get('source_category_id'), 'Source category')
            target = _locked_category(action.get('target_category_id'), 'Target category')
            result = _merge_categories(source, target)
            result['operation'] = operation
        elif operation == 'retire':
            source = _locked_category(action.get('source_category_id'), 'Source category')
            result = _retire_category_subtree(source)
        elif operation == 'split':
            source = _locked_category(action.get('source_category_id'), 'Source category')
            if Product.objects.filter(category_id=source).exists():
                raise TaxonomyApplicationError(
                    'This split has products that need assigning. Edit the tree manually or use a future mapped split workflow.'
                )
            new_categories = action.get('new_categories') or []
            if len(new_categories) < 2:
                raise TaxonomyApplicationError('A split needs at least two new child categories.')
            created = []
            for item in new_categories:
                title = ' '.join(str(item.get('title') or '').split())
                if not title or Category.objects.filter(title__iexact=title).exists():
                    raise TaxonomyApplicationError('Each split category needs a unique title that is not already in use.')
                category = Category.objects.create(
                    title=title,
                    parent_category=source,
                    description=' '.join(str(item.get('description') or '').split()),
                )
                created.append(category.pk)
            result = {'operation': 'split', 'source_category_id': source.pk, 'created_category_ids': created}
        else:  # add_attribute
            category = _locked_category(action.get('category_id'), 'Category')
            try:
                order = int(action.get('order'))
            except (TypeError, ValueError) as exc:
                raise TaxonomyApplicationError('Attribute order must be a whole number from 1 to 5.') from exc
            if order not in range(1, 6):
                raise TaxonomyApplicationError('Attribute order must be a whole number from 1 to 5.')
            if CategoryAttribute.objects.filter(category=category, order=order).exists():
                raise TaxonomyApplicationError('That attribute position is already configured; do not overwrite it.')
            legacy_suffix = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five'}[order]
            if (getattr(category, f'attribute_{legacy_suffix}_name') or '').strip():
                raise TaxonomyApplicationError('That attribute position is already configured; do not overwrite it.')
            name = ' '.join(str(action.get('name') or '').split())
            # Listing is the safe default for a peer-to-peer catalogue: the
            # lender supplies it for their specific item. Product is reserved
            # for a curated, immutable value shared by every listing.
            value_source = str(action.get('value_source') or CategoryAttribute.VALUE_SOURCE_LISTING).strip().lower()
            allowed_values = [
                ' '.join(str(value).split())
                for value in (action.get('allowed_values') or [])
                if ' '.join(str(value).split())
            ]
            allowed_values = list(dict.fromkeys(allowed_values))
            if not name or value_source not in {CategoryAttribute.VALUE_SOURCE_PRODUCT, CategoryAttribute.VALUE_SOURCE_LISTING}:
                raise TaxonomyApplicationError('Attribute name and a product or listing value source are required.')
            if not 2 <= len(allowed_values) <= 12:
                raise TaxonomyApplicationError('An attribute needs between 2 and 12 distinct choices.')
            attribute = CategoryAttribute.objects.create(
                category=category,
                order=order,
                name=name,
                value_source=value_source,
                filterable=True,
                allowed_values_text='\n'.join(allowed_values),
            )
            result = {
                'operation': 'add_attribute',
                'category_id': category.pk,
                'category_attribute_id': attribute.pk,
                'order': order,
                'name': name,
                'value_source': value_source,
                'allowed_values': allowed_values,
            }

        recommendation.status = CategoryTaxonomyRecommendation.STATUS_IMPLEMENTED
        recommendation.reviewed_by = reviewer
        recommendation.reviewed_at = timezone.now()
        recommendation.implementation_result = result
        recommendation.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'implementation_result'])
    return result
