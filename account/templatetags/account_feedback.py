from django import template

from transaction.helpers import get_user_feedback_breakdown

register = template.Library()


@register.simple_tag(takes_context=True)
def feedback_breakdown_for_user(context, user):
    if not user:
        return get_user_feedback_breakdown(user_id=None)

    user_id = getattr(user, 'id', None)
    if not user_id:
        return get_user_feedback_breakdown(user_id=None)

    cache = context.render_context.setdefault('feedback_breakdown_cache', {})
    if user_id not in cache:
        cache[user_id] = get_user_feedback_breakdown(user_id=user_id)
    return cache[user_id]
