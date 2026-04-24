# Friends Module Documentation

## Overview
The friends module manages friend relationships between users, allowing them to:
- Send and receive friend requests
- Accept, reject, or cancel friend requests
- Block other users
- View their friend list

## Models

### Friendship
Represents a friendship relationship between two users.

**Fields:**
- `user_from` - User who sent the friend request (ForeignKey)
- `user_to` - User who received the friend request (ForeignKey)
- `status` - One of: PENDING, ACCEPTED, BLOCKED
  - **PENDING**: Request awaiting acceptance
  - **ACCEPTED**: Confirmed friendship
  - **BLOCKED**: User is blocked
- `created_at` - When the friendship was created
- `updated_at` - When the friendship was last updated
- `history` - Historical records of all changes (via django-simple-history)

**Constraints:**
- `unique_together` on `(user_from, user_to)` - Can't have duplicate requests
- Users cannot add themselves as friends

## FriendsHelper Utility Class

Static methods for common friend operations:

### are_friends(user1, user2)
Check if two users are confirmed friends (bidirectional).
```python
from friends.models import FriendsHelper

if FriendsHelper.are_friends(user1, user2):
    print("They are friends")
```

### get_friends(user)
Get all confirmed friends of a user.
```python
friends = FriendsHelper.get_friends(user)
for friend in friends:
    print(friend.username)
```

### add_friend(user_from, user_to)
Send a friend request. Raises ValidationError if:
- Users are the same
- A friendship already exists
- User is already blocked
```python
try:
    FriendsHelper.add_friend(user1, user2)
except ValidationError as e:
    print(f"Error: {e}")
```

### remove_friend(user1, user2)
Remove a confirmed friendship between two users.
```python
FriendsHelper.remove_friend(user1, user2)
```

### get_pending_requests(user)
Get all pending friend requests for a user (where they are the recipient).
```python
pending = FriendsHelper.get_pending_requests(user)
for request in pending:
    print(f"{request.user_from.username} sent you a friend request")
```

## URLs

The friends app includes the following URL routes (namespace: `friends`):

```
friends:friends_list      - GET    - /list/
friends:add_friend        - GET/POST - /add/
friends:pending_requests  - GET    - /requests/pending/
friends:sent_requests     - GET    - /requests/sent/
friends:accept_request    - POST   - /requests/<id>/accept/
friends:reject_request    - POST   - /requests/<id>/reject/
friends:cancel_request    - POST   - /requests/<id>/cancel/
friends:remove_friend     - POST   - /<user_id>/remove/
friends:block_friend      - POST   - /<user_id>/block/
```

## Views

### friends_list
Display the logged-in user's friend list.
- **URL**: `friends:friends_list`
- **Method**: GET
- **Template**: `friends/friends_list.html`
- **Context**: 
  - `friends` - QuerySet of User objects
  - `total_friends` - Count of friends

### pending_requests
Display incoming friend requests awaiting acceptance.
- **URL**: `friends:pending_requests`
- **Method**: GET
- **Template**: `friends/pending_requests.html`
- **Context**:
  - `pending_requests` - QuerySet of Friendship objects
  - `total_pending` - Count of pending requests

### sent_requests
Display outgoing friend requests sent by the user.
- **URL**: `friends:sent_requests`
- **Method**: GET
- **Template**: `friends/sent_requests.html`
- **Context**:
  - `sent_requests` - QuerySet of Friendship objects
  - `total_sent` - Count of sent requests

### add_friend
Send a friend request to another user.
- **URL**: `friends:add_friend`
- **Method**: GET/POST
- **Template**: `friends/add_friend.html`
- **POST Data**: `friend_username` - Username of the user to add
- **Redirects to**: `friends:friends_list` on success

### accept_request
Accept a pending friend request.
- **URL**: `friends:accept_request`
- **Method**: POST
- **URL Parameters**: `friendship_id` - ID of friendship to accept
- **Redirects to**: `friends:pending_requests`

### reject_request
Reject a pending friend request (deletes the Friendship record).
- **URL**: `friends:reject_request`
- **Method**: POST
- **URL Parameters**: `friendship_id` - ID of friendship to reject
- **Redirects to**: `friends:pending_requests`

### remove_friend
Remove a confirmed friend.
- **URL**: `friends:remove_friend`
- **Method**: POST
- **URL Parameters**: `user_id` - ID of friend to remove
- **Redirects to**: `friends:friends_list`

### cancel_request
Cancel a sent friend request.
- **URL**: `friends:cancel_request`
- **Method**: POST
- **URL Parameters**: `friendship_id` - ID of friendship request to cancel
- **Redirects to**: `friends:sent_requests`

### block_friend
Block a user (prevents friendship).
- **URL**: `friends:block_friend`
- **Method**: POST
- **URL Parameters**: `user_id` - ID of user to block
- **Redirects to**: `friends:friends_list`

## Forms

### AddFriendForm
Form for adding a friend by username.
```python
from friends.forms import AddFriendForm

form = AddFriendForm(request.POST)
if form.is_valid():
    friend_user = form.cleaned_data['friend_username']  # Returns User object
```

### FriendshipStatusForm
Form for managing friendship status.
```python
from friends.forms import FriendshipStatusForm

form = FriendshipStatusForm(instance=friendship)
```

## Admin Interface

The Friendship model is registered in Django admin with:
- List display: user_from, user_to, status, created_at, updated_at
- List filters by status and date
- Search by username
- Readonly timestamps
- History tracking via django-simple-history

## Integration with Transactions

When showing transactions, the system can display different prices for friends vs non-friends:

```python
from transaction.models import Transaction
from friends.models import FriendsHelper

transaction = Transaction.objects.get(id=1)
viewing_user = request.user

if FriendsHelper.are_friends(transaction.user_aggressive, viewing_user):
    # Show friend price if available
    price = transaction.friend_price or transaction.price
else:
    # Show regular price
    price = transaction.price
```

## Tests

Comprehensive unit tests are included in `friends/tests.py`:
- Test preventing self-friending
- Test sending friend requests
- Test accepting requests
- Test friend checking
- Test friend list retrieval
- Test removing friends
- Test pending request retrieval
- Test duplicate request prevention

Run tests with:
```bash
python manage.py test friends
```

## Requirements

The friends module requires:
- Django (as part of main project)
- django-simple-history (for history tracking)
- Bootstrap4 (for form rendering)

These are already installed in the project.

## Future Enhancements

Potential improvements:
1. Mutual friend requests (both users send, then auto-accept)
2. Friend groups for bulk operations
3. Friend activity feed
4. Notifications for friend requests
5. Friend statistics and metrics
6. Blocking notifications
7. Limited visibility of profile/transactions for non-friends
