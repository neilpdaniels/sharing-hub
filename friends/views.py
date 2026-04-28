from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db.models import Q

from .models import Friendship, BlockedUser
from .forms import AddFriendForm
from account.models import Profile
from common.geocoding import PostcodeGeocoder


def _get_nearby_friend_suggestions(user, max_distance_km=3, limit=100):
    """Return nearby user suggestions for the add-friend panel."""
    try:
        my_profile = user.profile
    except Exception:
        return {
            'suggestions': [],
            'has_location': False,
            'radius_km': max_distance_km,
        }

    if not my_profile.latitude or not my_profile.longitude:
        return {
            'suggestions': [],
            'has_location': False,
            'radius_km': max_distance_km,
        }

    blocked_ids = set(BlockedUser.objects.filter(blocked_by=user).values_list('blocked_user_id', flat=True))
    blocked_by_ids = set(BlockedUser.objects.filter(blocked_user=user).values_list('blocked_by_id', flat=True))

    relationship_ids = set()
    for user_from_id, user_to_id in Friendship.objects.filter(
        Q(user_from=user) | Q(user_to=user)
    ).values_list('user_from_id', 'user_to_id'):
        if user_from_id != user.id:
            relationship_ids.add(user_from_id)
        if user_to_id != user.id:
            relationship_ids.add(user_to_id)

    excluded_ids = blocked_ids | blocked_by_ids | relationship_ids | {user.id}

    nearby = []
    candidate_profiles = Profile.objects.select_related('user').exclude(
        user_id__in=excluded_ids
    ).exclude(
        latitude__isnull=True
    ).exclude(
        longitude__isnull=True
    )

    for profile in candidate_profiles:
        distance_km = PostcodeGeocoder.calculate_distance(
            my_profile.latitude,
            my_profile.longitude,
            profile.latitude,
            profile.longitude,
        )
        if distance_km <= max_distance_km:
            nearby.append({
                'user': profile.user,
                'distance_km': distance_km,
                'town': profile.town,
                'postcode': profile.postcode,
            })

    nearby.sort(key=lambda item: item['distance_km'])

    return {
        'suggestions': nearby[:limit],
        'has_location': True,
        'radius_km': max_distance_km,
    }


def _build_my_friends_context(user, add_form):
    accepted = Friendship.objects.filter(
        status=Friendship.ACCEPTED,
    ).filter(Q(user_from=user) | Q(user_to=user)).select_related('user_from', 'user_to')

    paused = Friendship.objects.filter(
        status=Friendship.PAUSED,
    ).filter(Q(user_from=user) | Q(user_to=user)).select_related('user_from', 'user_to')

    pending_received = Friendship.objects.filter(
        user_to=user, status=Friendship.PENDING
    ).select_related('user_from')

    pending_sent = Friendship.objects.filter(
        user_from=user, status=Friendship.PENDING
    ).select_related('user_to')

    nearby_data = _get_nearby_friend_suggestions(user)

    return {
        'accepted': accepted,
        'paused': paused,
        'pending_received': pending_received,
        'pending_sent': pending_sent,
        'add_form': add_form,
        'nearby_friend_suggestions': nearby_data['suggestions'],
        'nearby_has_location': nearby_data['has_location'],
        'nearby_radius_km': nearby_data['radius_km'],
    }


@login_required
def my_friends(request):
    """Main friends hub: list of friends, pending/sent requests, and add form."""
    user = request.user
    add_form = AddFriendForm()
    context = _build_my_friends_context(user, add_form)
    return render(request, 'friends/my_friends.html', context)


@login_required
def add_friend(request):
    """Send friend request by username/email or invite if email is not registered."""
    if request.method != 'POST':
        return redirect('friends:my_friends')

    form = AddFriendForm(request.POST)
    if not form.is_valid():
        context = _build_my_friends_context(request.user, form)
        return render(request, 'friends/my_friends.html', context)

    email = form.cleaned_data['email']
    username = form.cleaned_data['username']

    if username:
        target_user = User.objects.get(username=username)
    elif email:
        try:
            target_user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            target_user = None
    else:
        target_user = None

    if target_user and target_user == request.user:
        messages.error(request, 'You cannot add yourself as a friend.')
        return redirect('friends:my_friends')

    if target_user:
        _create_friend_request_with_messages(request, target_user)
    else:
        from .tasks import send_friend_invite_email
        send_friend_invite_email.delay(request.user.id, email)
        messages.success(request, f'An invitation to join has been sent to {email}.')

    return redirect('friends:my_friends')


@login_required
def add_friend_user(request, user_id):
    """Send friend request directly to a known user id (used from product page)."""
    if request.method != 'POST':
        return redirect('friends:my_friends')

    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, 'You cannot add yourself as a friend.')
        return redirect('friends:my_friends')

    _create_friend_request_with_messages(request, target_user)

    back_url = request.META.get('HTTP_REFERER')
    if back_url:
        return redirect(back_url)
    return redirect('friends:my_friends')


@login_required
def add_to_my_list_user(request, user_id):
    """Add a user to my one-way friend list without sending them a request."""
    if request.method != 'POST':
        return redirect('friends:my_friends')

    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, 'You cannot add yourself to your list.')
        return redirect('friends:my_friends')

    if BlockedUser.objects.filter(
        Q(blocked_by=request.user, blocked_user=target_user) |
        Q(blocked_by=target_user, blocked_user=request.user)
    ).exists():
        messages.warning(request, 'You cannot add this user to your list.')
    else:
        existing = Friendship.objects.filter(
            Q(user_from=request.user, user_to=target_user) |
            Q(user_from=target_user, user_to=request.user)
        ).first()

        if existing:
            status_labels = {
                Friendship.ACCEPTED: 'You are already connected with this user.',
                Friendship.PENDING: 'A connection with this user already exists.',
                Friendship.PAUSED: 'Your connection with this user is currently paused.',
                Friendship.BLOCKED: 'You cannot add this user to your list.',
            }
            messages.warning(request, status_labels.get(existing.status, 'A connection already exists.'))
        else:
            # Reverse-direction pending gives request.user immediate visibility
            # of target_user friends-only listings without notifying target_user.
            Friendship.objects.create(
                user_from=target_user,
                user_to=request.user,
                status=Friendship.PENDING,
            )
            messages.success(request, f"{target_user.get_full_name() or target_user.username} added to your list.")

    back_url = request.META.get('HTTP_REFERER')
    if back_url:
        return redirect(back_url)
    return redirect('friends:my_friends')


def _create_friend_request_with_messages(request, target_user):
    existing = Friendship.objects.filter(
        Q(user_from=request.user, user_to=target_user) |
        Q(user_from=target_user, user_to=request.user)
    ).first()
    if existing:
        status_labels = {
            Friendship.ACCEPTED: 'You are already friends.',
            Friendship.PENDING: 'A friend request is already pending.',
            Friendship.PAUSED: 'Your friendship is currently paused.',
            Friendship.BLOCKED: 'You cannot add this user.',
        }
        messages.warning(request, status_labels.get(existing.status, 'A connection already exists.'))
        return

    friendship = Friendship(user_from=request.user, user_to=target_user)
    friendship.full_clean()
    friendship.save()
    from .tasks import send_friend_request_notification
    send_friend_request_notification.delay(request.user.id, target_user.id)
    messages.success(request, f'Friend request sent to {target_user.get_full_name() or target_user.username}.')


@login_required
def accept_request(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_to != request.user:
        return HttpResponseForbidden()
    if friendship.status != Friendship.PENDING:
        messages.warning(request, 'This request is no longer pending.')
    else:
        friendship.accept()
        messages.success(request, f'You are now friends with {friendship.user_from.get_full_name() or friendship.user_from.username}!')
    return redirect('friends:my_friends')


@login_required
def reject_request(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_to != request.user:
        return HttpResponseForbidden()
    if friendship.status != Friendship.PENDING:
        messages.warning(request, 'This request is no longer pending.')
    else:
        username = friendship.user_from.username
        friendship.reject()
        messages.success(request, f'Friend request from {username} declined.')
    return redirect('friends:my_friends')


@login_required
def cancel_request(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_from != request.user:
        return HttpResponseForbidden()
    if friendship.status != Friendship.PENDING:
        messages.warning(request, 'This request is no longer pending.')
    else:
        username = friendship.user_to.username
        friendship.reject()
        messages.success(request, f'Friend request to {username} cancelled.')
    return redirect('friends:my_friends')


@login_required
def pause_friendship(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_from != request.user and friendship.user_to != request.user:
        return HttpResponseForbidden()
    try:
        friendship.pause()
        messages.success(request, 'Friendship paused.')
    except Exception as e:
        messages.error(request, str(e))
    return redirect('friends:my_friends')


@login_required
def unpause_friendship(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_from != request.user and friendship.user_to != request.user:
        return HttpResponseForbidden()
    try:
        friendship.unpause()
        messages.success(request, 'Friendship resumed.')
    except Exception as e:
        messages.error(request, str(e))
    return redirect('friends:my_friends')


@login_required
def remove_friend(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_from != request.user and friendship.user_to != request.user:
        return HttpResponseForbidden()
    other = friendship.user_to if friendship.user_from == request.user else friendship.user_from
    friendship.delete()
    messages.success(request, f'You removed {other.get_full_name() or other.username} from your friends.')
    return redirect('friends:my_friends')


@login_required
def block_friend(request, user_id):
    user_to_block = get_object_or_404(User, id=user_id)
    friendship = Friendship.objects.filter(
        Q(user_from=request.user, user_to=user_to_block) |
        Q(user_from=user_to_block, user_to=request.user)
    ).first()
    if friendship:
        if friendship.user_from == request.user:
            friendship.block()
        else:
            friendship.delete()
            Friendship.objects.create(user_from=request.user, user_to=user_to_block, status=Friendship.BLOCKED)
    else:
        Friendship.objects.create(user_from=request.user, user_to=user_to_block, status=Friendship.BLOCKED)
    messages.success(request, f'You blocked {user_to_block.username}.')
    return redirect('friends:my_friends')


# Blocked Users Management

@login_required
def blocked_users(request):
    """Display list of users the current user has blocked."""
    user = request.user
    blocked = BlockedUser.objects.filter(blocked_by=user).select_related('blocked_user')
    
    context = {
        'blocked': blocked,
    }
    return render(request, 'friends/blocked_users.html', context)


@login_required
def block_user(request, user_id):
    """Block a user (prevent them from seeing our listings and vice versa)."""
    user_to_block = get_object_or_404(User, id=user_id)
    
    if user_to_block == request.user:
        messages.error(request, 'You cannot block yourself.')
        return redirect('friends:blocked_users')
    
    # Check if already blocked
    if BlockedUser.objects.filter(blocked_by=request.user, blocked_user=user_to_block).exists():
        messages.warning(request, f'{user_to_block.username} is already blocked.')
        return redirect('friends:blocked_users')
    
    # Create block record
    report_flagged = request.POST.get('report_flagged') == 'on'
    BlockedUser.objects.create(
        blocked_by=request.user,
        blocked_user=user_to_block,
        report_flagged=report_flagged
    )
    
    # If we have an active friendship, remove it
    Friendship.objects.filter(
        Q(user_from=request.user, user_to=user_to_block) |
        Q(user_from=user_to_block, user_to=request.user)
    ).delete()
    
    messages.success(request, f'You blocked {user_to_block.get_full_name() or user_to_block.username}.')
    
    back_url = request.META.get('HTTP_REFERER')
    if back_url and 'blocked' not in back_url:
        return redirect(back_url)
    return redirect('friends:blocked_users')


@login_required
def unblock_user(request, user_id):
    """Unblock a user."""
    user_to_unblock = get_object_or_404(User, id=user_id)
    
    block = BlockedUser.objects.filter(blocked_by=request.user, blocked_user=user_to_unblock).first()
    if not block:
        messages.warning(request, f'{user_to_unblock.username} is not blocked.')
        return redirect('friends:blocked_users')
    
    block.delete()
    messages.success(request, f'You unblocked {user_to_unblock.get_full_name() or user_to_unblock.username}.')
    return redirect('friends:blocked_users')


# legacy redirects
@login_required
def friends_list(request):
    return redirect('friends:my_friends')


@login_required
def pending_requests(request):
    return redirect('friends:my_friends')


@login_required
def sent_requests(request):
    return redirect('friends:my_friends')
