from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords


class Friendship(models.Model):
    """
    Represents a friendship / connection request between two users.

    Semantics
    ---------
    When user A (user_from / initiator) sends a request to user B (user_to / target):

    * A's listings are **immediately visible** to B via friends-only searches
      (status PENDING or ACCEPTED).
    * B's listings are visible to A **only after** B accepts (status ACCEPTED).

    So "friends-only" visibility is asymmetric until acceptance.
    """

    user_from = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='friendship_requests_sent',
        on_delete=models.CASCADE
    )
    user_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='friendship_requests_received',
        on_delete=models.CASCADE
    )

    PENDING = 'PENDING'
    ACCEPTED = 'ACCEPTED'
    PAUSED = 'PAUSED'
    BLOCKED = 'BLOCKED'

    STATUS_CHOICES = (
        (PENDING,  'Pending'),
        (ACCEPTED, 'Accepted'),
        (PAUSED,   'Paused'),
        (BLOCKED,  'Blocked'),
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=PENDING,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        unique_together = ('user_from', 'user_to')
        indexes = [
            models.Index(fields=['user_from', 'status']),
            models.Index(fields=['user_to', 'status']),
        ]

    def clean(self):
        if self.user_from_id == self.user_to_id:
            raise ValidationError("You cannot add yourself as a friend.")

    def __str__(self):
        return f"{self.user_from.username} -> {self.user_to.username} ({self.status})"

    def accept(self):
        if self.status != self.PENDING:
            raise ValidationError(f"Cannot accept a friendship with status: {self.status}")
        self.status = self.ACCEPTED
        self.save()

    def reject(self):
        self.delete()

    def pause(self):
        if self.status not in (self.ACCEPTED, self.PENDING):
            raise ValidationError(f"Cannot pause a friendship with status: {self.status}")
        self.status = self.PAUSED
        self.save()

    def unpause(self):
        if self.status != self.PAUSED:
            raise ValidationError("Friendship is not paused.")
        self.status = self.ACCEPTED
        self.save()

    def block(self):
        self.status = self.BLOCKED
        self.save()

    def unblock(self):
        self.delete()


class FriendsHelper:
    """Helper methods for friendship queries."""

    @staticmethod
    def are_friends(user1, user2):
        return Friendship.objects.filter(
            status=Friendship.ACCEPTED
        ).filter(
            models.Q(user_from=user1, user_to=user2) |
            models.Q(user_from=user2, user_to=user1)
        ).exists()

    @staticmethod
    def get_friends(user):
        """Return a User queryset of all ACCEPTED friends."""
        accepted = Friendship.objects.filter(
            status=Friendship.ACCEPTED
        ).filter(
            models.Q(user_from=user) | models.Q(user_to=user)
        )
        friend_ids = set()
        for f in accepted:
            friend_ids.add(f.user_from_id if f.user_to_id == user.pk else f.user_to_id)
        return User.objects.filter(id__in=friend_ids)

    @staticmethod
    def get_visible_friend_ids(user):
        """
        Return a set of user IDs whose listings the given user can see
        under friends-only filtering.

        * Initiators who sent ME a request → visible even if PENDING
        * Recipients of MY request → visible only if ACCEPTED
        """
        initiators = Friendship.objects.filter(
            user_to=user,
            status__in=[Friendship.PENDING, Friendship.ACCEPTED],
        ).values_list('user_from_id', flat=True)

        accepted_targets = Friendship.objects.filter(
            user_from=user,
            status=Friendship.ACCEPTED,
        ).values_list('user_to_id', flat=True)

        return set(initiators) | set(accepted_targets)

    @staticmethod
    def add_friend(user_from, user_to):
        if user_from == user_to:
            raise ValidationError("You cannot add yourself as a friend.")
        existing = Friendship.objects.filter(
            models.Q(user_from=user_from, user_to=user_to) |
            models.Q(user_from=user_to, user_to=user_from)
        ).first()
        if existing:
            if existing.status == Friendship.ACCEPTED:
                raise ValidationError("You are already friends with this user.")
            elif existing.status == Friendship.PENDING:
                raise ValidationError("A friend request is already pending.")
            elif existing.status == Friendship.PAUSED:
                raise ValidationError("This friendship is currently paused.")
            elif existing.status == Friendship.BLOCKED:
                raise ValidationError("You have blocked this user or they have blocked you.")
        friendship = Friendship(user_from=user_from, user_to=user_to)
        friendship.full_clean()
        friendship.save()
        return friendship

    @staticmethod
    def remove_friend(user1, user2):
        Friendship.objects.filter(
            models.Q(user_from=user1, user_to=user2) |
            models.Q(user_from=user2, user_to=user1)
        ).delete()

    @staticmethod
    def get_pending_requests(user):
        return Friendship.objects.filter(user_to=user, status=Friendship.PENDING)
