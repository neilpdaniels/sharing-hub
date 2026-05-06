from django.contrib.auth.models import User


class EmailAuthBackend:
    """Authenticate using email address instead of username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username:
            return None
        # Try email first, then fall back to username
        try:
            user = User.objects.get(email__iexact=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            pass
        # Fall back to username lookup (handles case where input matches
        # another user's email but is actually this user's username)
        try:
            user = User.objects.get(username__iexact=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            pass
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
