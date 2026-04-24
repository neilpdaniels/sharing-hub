from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db.models import Q
from .models import Friendship, FriendsHelper
from .forms import AddFriendForm


# ---------------------------------------------------------------------------
# Consolidated "My Friends" hub
# ---------------------------------------------------------------------------

@login_required
def my_friends(request):
    """Main friends hub: list of friends, pending/sent requests, and add form."""
    user = request.user

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

    add_form = AddFriendForm()

    context = {
        'accepted': accepted,
        'paused': paused,
        'pending_received': pending_received,
        'pending_sent': pending_sent,
        'add_form': add_form,
    }
    return render(request, 'friends/my_friends.html', context)


# ---------------------------------------------------------------------------
# Add friend by email
# ---------------------------------------------------------------------------

@login_required
def add_friend(request):
    if request.method != 'POST':
        return redirect('friends:my_friends')

    form = AddFriendForm(request.POST)
    if not form.is_valid():
        # Re-render hub with the form errors
        user = request.user
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
        return render(request, 'friends/my_friends.html', {
            'accepted': accepted, 'paused': paused,
            'pending_received': pending_received, 'pending_sent': pending_sent,
            'add_form': form,
        })

    email = form.cleaned_data['email']
    username = form.cleaned_data['username']

    # Resolve target user
    if username:
        target_user = User.objects.get(username=username)  # validated in form
    elif email:
        try:
            target_user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            target_user = None
    else:
        target_user = None

    if target_user and target_user == request.user:
        messages.error(request, "You cannot add yourself as a friend.")
        return redirect('friends:my_friends')

    if target_user:
        existing = Friendship.objects.filter(
            Q(user_from=request.user, user_to=target_user) |
            Q(user_from=target_user, user_to=request.user)
        ).first()
        if existing:
            status_labels = {
                Friendship.ACCEPTED: "You are already friends.",
                Friendship.PENDING:  "A friend request is already pending.",
                Friendship.PAUSED:   "Your friendship is currently paused.",
                Friendship.BLOCKED:  "You cannot add this user.",
            }
            messages.warning(request, status_labels.get(existing.status, "A connection already exists."))
        else:
            friendship = Friendship(user_from=request.user, user_to=target_user)
            friendship.full_clean()
            friendship.save()
            from .tasks import send_friend_request_notification
            send_friend_request_notification.delay(request.user.id, target_user.id)
            messages.success(request, f"Friend request sent to {target_user.get_full_name() or target_user.username}.")
    else:
        # Non-member — send invite email (only possible via email path)
        from .tasks import send_friend_invite_email
        send_friend_invite_email.delay(request.user.id, email)
        messages.success(request, f"An invitation to join has been sent to {email}.")

    return redirect('friends:my_friends')


# ---------------------------------------------------------------------------
# Accept / reject / cancel
# ---------------------------------------------------------------------------

@login_required
def accept_request(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_to != request.user:
        return HttpResponseForbidden()
    if friendship.status != Friendship.PENDING:
        messages.warning(request, "This request is no longer pending.")
    else:
        friendship.accept()
        messages.success(request, f"You are now friends with {friendship.user_from.get_full_name() or friendship.user_from.username}!")
    return redirect('friends:my_friends')


@login_required
def reject_request(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_to != request.user:
        return HttpResponseForbidden()
    if friendship.status != Friendship.PENDING:
        messages.warning(request, "This request is no longer pending.")
    else:
        username = friendship.user_from.username
        friendship.reject()
        messages.success(request, f"Friend request from {username} declined.")
    return redirect('friends:my_friends')


@login_required
def cancel_request(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_from != request.user:
        return HttpResponseForbidden()
    if friendship.status != Friendship.PENDING:
        messages.warning(request, "This request is no longer pending.")
    else:
        username = friendship.user_to.username
        friendship.reject()
        messages.success(request, f"Friend request to {username} cancelled.")
    return redirect('friends:my_friends')


# ---------------------------------------------------------------------------
# Pause / unpause
# ---------------------------------------------------------------------------

@login_required
def pause_friendship(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_from != request.user and friendship.user_to != request.user:
        return HttpResponseForbidden()
    try:
        friendship.pause()
        messages.success(request, "Friendship paused.")
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
        messages.success(request, "Friendship resumed.")
    except Exception as e:
        messages.error(request, str(e))
    return redirect('friends:my_friends')


# ---------------------------------------------------------------------------
# Remove / block
# ---------------------------------------------------------------------------

@login_required
def remove_friend(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id)
    if friendship.user_from != request.user and friendship.user_to != request.user:
        return HttpResponseForbidden()
    other = friendship.user_to if friendship.user_from == request.user else friendship.user_from
    friendship.delete()
    messages.success(request, f"You removed {other.get_full_name() or other.username} from your friends.")
    return redirect('friends:my_friends')


# ---------------------------------------------------------------------------
# Legacy list views (kept for back-compat, redirect to hub)
# ---------------------------------------------------------------------------

@login_required
def friends_list(request):
    return redirect('friends:my_friends')


@login_required
def pending_requests(request):
    return redirect('friends:my_friends')


@login_required
def sent_requests(request):
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
    messages.success(request, f"You blocked {user_to_block.username}.")
    return redirect('friends:my_friends')

    """Display the logged-in user's friend list."""
    user = request.user
    friends = FriendsHelper.get_friends(user)
    
    context = {
        'friends': friends.order_by('username'),
        'total_friends': friends.count(),
    }
    return render(request, 'friends/friends_list.html', context)


@login_required
def pending_requests(request):
    """Display pending friend requests for the logged-in user."""
    user = request.user
    pending = FriendsHelper.get_pending_requests(user)
    
    context = {
        'pending_requests': pending.order_by('-created_at'),
        'total_pending': pending.count(),
    }
    return render(request, 'friends/pending_requests.html', context)


@login_required
def sent_requests(request):
    """Display friend requests sent by the logged-in user."""
    user = request.user
    sent = Friendship.objects.filter(
        user_from=user,
        status=Friendship.PENDING
    ).order_by('-created_at')
    
    context = {
        'sent_requests': sent,
        'total_sent': sent.count(),
    }
    return render(request, 'friends/sent_requests.html', context)


@login_required
def add_friend(request):
    """Send a friend request to another user."""
    if request.method == 'POST':
        form = AddFriendForm(request.POST)
        if form.is_valid():
            friend_user = form.cleaned_data['friend_username']
            try:
                FriendsHelper.add_friend(request.user, friend_user)
                messages.success(request, f"Friend request sent to {friend_user.username}!")
                return redirect('friends:friends_list')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = AddFriendForm()
    
    context = {'form': form}
    return render(request, 'friends/add_friend.html', context)


@login_required
def accept_request(request, friendship_id):
    """Accept a pending friend request."""
    friendship = get_object_or_404(Friendship, id=friendship_id)
    
    # Only the recipient can accept
    if friendship.user_to != request.user:
        return HttpResponseForbidden("You cannot accept this request.")
    
    if friendship.status != Friendship.PENDING:
        messages.warning(request, "This request is no longer pending.")
        return redirect('friends:pending_requests')
    
    friendship.accept()
    messages.success(request, f"You are now friends with {friendship.user_from.username}!")
    return redirect('friends:pending_requests')


@login_required
def reject_request(request, friendship_id):
    """Reject a pending friend request."""
    friendship = get_object_or_404(Friendship, id=friendship_id)
    
    # Only the recipient can reject
    if friendship.user_to != request.user:
        return HttpResponseForbidden("You cannot reject this request.")
    
    if friendship.status != Friendship.PENDING:
        messages.warning(request, "This request is no longer pending.")
        return redirect('friends:pending_requests')
    
    username = friendship.user_from.username
    friendship.reject()
    messages.success(request, f"Friend request from {username} rejected.")
    return redirect('friends:pending_requests')


@login_required
def remove_friend(request, user_id):
    """Remove a friend."""
    friend = get_object_or_404(User, id=user_id)
    
    try:
        FriendsHelper.remove_friend(request.user, friend)
        messages.success(request, f"You removed {friend.username} from your friends.")
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('friends:friends_list')


@login_required
def cancel_request(request, friendship_id):
    """Cancel a sent friend request."""
    friendship = get_object_or_404(Friendship, id=friendship_id)
    
    # Only the sender can cancel
    if friendship.user_from != request.user:
        return HttpResponseForbidden("You cannot cancel this request.")
    
    if friendship.status != Friendship.PENDING:
        messages.warning(request, "This request is no longer pending.")
        return redirect('friends:sent_requests')
    
    username = friendship.user_to.username
    friendship.reject()
    messages.success(request, f"Friend request to {username} cancelled.")
    return redirect('friends:sent_requests')


@login_required
def block_friend(request, user_id):
    """Block a user."""
    user_to_block = get_object_or_404(User, id=user_id)
    
    # Check if friendship exists
    friendship = Friendship.objects.filter(
        Q(user_from=request.user, user_to=user_to_block) |
        Q(user_from=user_to_block, user_to=request.user)
    ).first()
    
    if friendship:
        if friendship.user_from == request.user:
            friendship.block()
        else:
            # If they sent the request, delete it and create a new blocked one
            friendship.delete()
            blocked = Friendship(
                user_from=request.user,
                user_to=user_to_block,
                status=Friendship.BLOCKED
            )
            blocked.save()
    else:
        # Create a new blocked friendship
        blocked = Friendship(
            user_from=request.user,
            user_to=user_to_block,
            status=Friendship.BLOCKED
        )
        blocked.save()
    
    messages.success(request, f"You blocked {user_to_block.username}.")
    return redirect('friends:friends_list')
