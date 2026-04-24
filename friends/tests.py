from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Friendship, FriendsHelper


class FriendshipModelTests(TestCase):
    
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='test')
        self.user2 = User.objects.create_user(username='user2', password='test')
        self.user3 = User.objects.create_user(username='user3', password='test')
    
    def test_cannot_add_self_as_friend(self):
        """Test that a user cannot add themselves as a friend."""
        with self.assertRaises(ValidationError):
            FriendsHelper.add_friend(self.user1, self.user1)
    
    def test_add_friend_request(self):
        """Test sending a friend request."""
        friendship = FriendsHelper.add_friend(self.user1, self.user2)
        self.assertEqual(friendship.status, Friendship.PENDING)
        self.assertEqual(friendship.user_from, self.user1)
        self.assertEqual(friendship.user_to, self.user2)
    
    def test_accept_friend_request(self):
        """Test accepting a friend request."""
        friendship = FriendsHelper.add_friend(self.user1, self.user2)
        friendship.accept()
        self.assertEqual(friendship.status, Friendship.ACCEPTED)
    
    def test_are_friends(self):
        """Test checking if two users are friends."""
        friendship = FriendsHelper.add_friend(self.user1, self.user2)
        self.assertFalse(FriendsHelper.are_friends(self.user1, self.user2))
        
        friendship.accept()
        self.assertTrue(FriendsHelper.are_friends(self.user1, self.user2))
        self.assertTrue(FriendsHelper.are_friends(self.user2, self.user1))
    
    def test_get_friends(self):
        """Test getting a user's friend list."""
        friendship1 = FriendsHelper.add_friend(self.user1, self.user2)
        friendship2 = FriendsHelper.add_friend(self.user1, self.user3)
        
        friendship1.accept()
        friendship2.accept()
        
        friends = FriendsHelper.get_friends(self.user1)
        self.assertEqual(friends.count(), 2)
        self.assertIn(self.user2, friends)
        self.assertIn(self.user3, friends)
    
    def test_remove_friend(self):
        """Test removing a friend."""
        friendship = FriendsHelper.add_friend(self.user1, self.user2)
        friendship.accept()
        
        self.assertTrue(FriendsHelper.are_friends(self.user1, self.user2))
        
        FriendsHelper.remove_friend(self.user1, self.user2)
        self.assertFalse(FriendsHelper.are_friends(self.user1, self.user2))
    
    def test_get_pending_requests(self):
        """Test getting pending friend requests."""
        FriendsHelper.add_friend(self.user1, self.user2)
        FriendsHelper.add_friend(self.user3, self.user2)
        
        pending = FriendsHelper.get_pending_requests(self.user2)
        self.assertEqual(pending.count(), 2)
    
    def test_duplicate_friend_request_raises_error(self):
        """Test that sending a duplicate friend request raises an error."""
        FriendsHelper.add_friend(self.user1, self.user2)
        
        with self.assertRaises(ValidationError):
            FriendsHelper.add_friend(self.user1, self.user2)
