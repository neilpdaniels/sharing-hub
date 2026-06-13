class NearbyUser {
  NearbyUser({
    required this.id,
    required this.username,
    required this.firstName,
    required this.lastName,
    required this.displayName,
    required this.distanceKm,
    required this.town,
    required this.postcode,
    required this.avatarUrl,
    required this.rating,
    required this.successfulTxns,
    required this.addressVerified,
  });

  final int id;
  final String username;
  final String firstName;
  final String lastName;
  final String displayName;
  final double distanceKm;
  final String town;
  final String postcode;
  final String avatarUrl;
  final double rating;
  final int successfulTxns;
  final bool addressVerified;

  factory NearbyUser.fromJson(Map<String, dynamic> json) {
    return NearbyUser(
      id: json['id'] as int,
      username: json['username'] as String? ?? '',
      firstName: json['first_name'] as String? ?? '',
      lastName: json['last_name'] as String? ?? '',
      displayName: json['display_name'] as String? ?? '',
      distanceKm: (json['distance_km'] as num?)?.toDouble() ?? 0,
      town: json['town'] as String? ?? '',
      postcode: json['postcode'] as String? ?? '',
      avatarUrl: json['avatar_url'] as String? ?? '',
      rating: (json['rating'] as num?)?.toDouble() ?? 0,
      successfulTxns: json['successful_txns'] as int? ?? 0,
      addressVerified: json['address_verified'] as bool? ?? false,
    );
  }
}

class FriendSummary {
  FriendSummary({
    required this.friendshipId,
    required this.userId,
    required this.username,
    required this.displayName,
    required this.town,
    required this.postcode,
    required this.avatarUrl,
    required this.status,
  });

  final int friendshipId;
  final int userId;
  final String username;
  final String displayName;
  final String town;
  final String postcode;
  final String avatarUrl;
  final String status;

  factory FriendSummary.fromJson(Map<String, dynamic> json) {
    return FriendSummary(
      friendshipId: json['friendship_id'] as int,
      userId: json['user_id'] as int,
      username: json['username'] as String? ?? '',
      displayName: json['display_name'] as String? ?? '',
      town: json['town'] as String? ?? '',
      postcode: json['postcode'] as String? ?? '',
      avatarUrl: json['avatar_url'] as String? ?? '',
      status: json['status'] as String? ?? '',
    );
  }
}

class BlockedUserSummary {
  BlockedUserSummary({
    required this.blockId,
    required this.userId,
    required this.username,
    required this.displayName,
  });

  final int blockId;
  final int userId;
  final String username;
  final String displayName;

  factory BlockedUserSummary.fromJson(Map<String, dynamic> json) {
    return BlockedUserSummary(
      blockId: json['block_id'] as int,
      userId: json['user_id'] as int,
      username: json['username'] as String? ?? '',
      displayName: json['display_name'] as String? ?? '',
    );
  }
}

class FriendsHubData {
  FriendsHubData({
    required this.accepted,
    required this.pendingReceived,
    required this.pendingSent,
    required this.blocked,
    required this.acceptedCount,
    required this.pendingReceivedCount,
    required this.pendingSentCount,
    required this.blockedCount,
  });

  final List<FriendSummary> accepted;
  final List<FriendSummary> pendingReceived;
  final List<FriendSummary> pendingSent;
  final List<BlockedUserSummary> blocked;
  final int acceptedCount;
  final int pendingReceivedCount;
  final int pendingSentCount;
  final int blockedCount;
}
