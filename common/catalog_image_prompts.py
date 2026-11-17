"""Ground catalogue image prompts in the actual category tree."""

from __future__ import annotations

from collections import defaultdict

from .models import Category, Product


# Deliberately non-linear so two variants do not simply look like the same
# collection with one extra object added.
SUBJECT_COUNTS_BY_VARIANT = (2, 4, 3, 5)


def category_image_subjects(category: Category, variant_index: int = 0) -> list[str]:
    """Select two to five real product/category labels for one image variant.

    This follows the old Midjourney workflow's approach: use direct products
    and immediate child categories first, then descend only if that does not
    provide enough real catalogue subjects. Rotation makes multiple generated
    candidates meaningfully different without inventing objects.
    """
    children_by_parent: dict[int | None, list[Category]] = defaultdict(list)
    categories = list(Category.objects.only('id', 'title', 'parent_category_id').order_by('title', 'id'))
    for child in categories:
        children_by_parent[child.parent_category_id].append(child)

    product_names_by_category: dict[int, list[str]] = defaultdict(list)
    for category_id, name in Product.objects.filter(
        category_id__isnull=False,
    ).order_by('category_id', 'name', 'id').values_list('category_id', 'name'):
        product_names_by_category[category_id].append(name)

    direct_children = children_by_parent.get(category.id, [])
    candidates = list(product_names_by_category.get(category.id, []))
    candidates.extend(child.title for child in direct_children)

    # A category without enough direct evidence may show a small, representative
    # subset of actual descendant products. It never falls back to invented
    # examples or generic category-title guesses.
    pending = list(direct_children)
    while pending and len(candidates) < 12:
        child = pending.pop(0)
        candidates.extend(product_names_by_category.get(child.id, []))
        pending.extend(children_by_parent.get(child.id, []))

    unique = []
    seen = set()
    for value in candidates:
        clean = ' '.join((value or '').split())
        if clean and clean.casefold() not in seen:
            seen.add(clean.casefold())
            unique.append(clean)

    if not unique:
        return []
    desired_count = min(len(unique), SUBJECT_COUNTS_BY_VARIANT[variant_index % len(SUBJECT_COUNTS_BY_VARIANT)])
    start = (variant_index * 3) % len(unique)
    rotated = unique[start:] + unique[:start]
    return rotated[:desired_count]


def build_category_image_prompt(
    category: Category,
    *,
    prompt_prefix: str = '',
    variant_index: int = 0,
) -> str:
    """Build a category prompt that explicitly constrains the visual subject."""
    subjects = category_image_subjects(category, variant_index)
    description = ' '.join((category.description or '').split())
    actual_subjects = ', '.join(f'“{subject}”' for subject in subjects)
    grounding = (
        f'Include these actual underlying catalogue subjects: {actual_subjects}. '
        'Depict only those subjects or clearly necessary neutral studio props; do not invent unrelated products. '
        if subjects else
        'No underlying products or child categories are currently available. Use only the category title and do not invent a specific product. '
    )
    return ' '.join(part for part in (
        prompt_prefix.strip(),
        f'Category: {category.title}.',
        description,
        grounding,
        'Create a realistic, trustworthy UK rental category image, with the listed subjects visibly represented, '
        'plain light background, soft studio lighting, square composition, no people, no text, no watermark and no readable brand logos.',
    ) if part)
