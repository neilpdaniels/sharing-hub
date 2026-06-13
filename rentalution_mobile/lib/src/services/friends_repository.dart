import '../models/friends_models.dart';
import 'api_client.dart';

class FriendsRepository {
  FriendsRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<List<NearbyUser>> fetchNearbyPeople({
    required String accessToken,
    int radiusKm = 10,
  }) async {
    final json = await _apiClient.getJsonObject(
      '/friends/nearby/',
      accessToken: accessToken,
      queryParameters: {'radius_km': radiusKm.toString()},
    );
    final results = json['results'] as List<dynamic>? ?? const [];
    return results
        .whereType<Map<String, dynamic>>()
        .map(NearbyUser.fromJson)
        .toList(growable: false);
  }

  Future<FriendsHubData> fetchHub({
    required String accessToken,
  }) async {
    final json = await _apiClient.getJsonObject(
      '/friends/',
      accessToken: accessToken,
    );
    final accepted = (json['accepted'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(FriendSummary.fromJson)
        .toList(growable: false);
    final pendingReceived = (json['pending_received'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(FriendSummary.fromJson)
        .toList(growable: false);
    final pendingSent = (json['pending_sent'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(FriendSummary.fromJson)
        .toList(growable: false);
    final blocked = (json['blocked'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(BlockedUserSummary.fromJson)
        .toList(growable: false);
    return FriendsHubData(
      accepted: accepted,
      pendingReceived: pendingReceived,
      pendingSent: pendingSent,
      blocked: blocked,
      acceptedCount: json['accepted_count'] as int? ?? accepted.length,
      pendingReceivedCount: json['pending_received_count'] as int? ?? pendingReceived.length,
      pendingSentCount: json['pending_sent_count'] as int? ?? pendingSent.length,
      blockedCount: json['blocked_count'] as int? ?? blocked.length,
    );
  }

  Future<String> sendFriendRequest({
    required String accessToken,
    required int userId,
  }) async {
    try {
      final json = await _apiClient.postJson(
        '/friends/$userId/add/',
        const <String, dynamic>{},
        accessToken: accessToken,
      );
      return json['message'] as String? ?? 'Friend request sent.';
    } on ApiException catch (e) {
      throw ApiException(_cleanMessage(e.toString()));
    }
  }

  Future<String> acceptRequest({
    required String accessToken,
    required int friendshipId,
  }) async {
    final json = await _apiClient.postJson(
      '/friends/$friendshipId/accept/',
      const <String, dynamic>{},
      accessToken: accessToken,
    );
    return json['message'] as String? ?? 'Friend request accepted.';
  }

  Future<String> rejectRequest({
    required String accessToken,
    required int friendshipId,
  }) async {
    final json = await _apiClient.postJson(
      '/friends/$friendshipId/reject/',
      const <String, dynamic>{},
      accessToken: accessToken,
    );
    return json['message'] as String? ?? 'Friend request rejected.';
  }

  Future<String> cancelRequest({
    required String accessToken,
    required int friendshipId,
  }) async {
    final json = await _apiClient.postJson(
      '/friends/$friendshipId/cancel/',
      const <String, dynamic>{},
      accessToken: accessToken,
    );
    return json['message'] as String? ?? 'Friend request cancelled.';
  }

  Future<String> removeFriend({
    required String accessToken,
    required int friendshipId,
  }) async {
    final json = await _apiClient.postJson(
      '/friends/$friendshipId/remove/',
      const <String, dynamic>{},
      accessToken: accessToken,
    );
    return json['message'] as String? ?? 'Friend removed.';
  }

  Future<String> blockUser({
    required String accessToken,
    required int userId,
  }) async {
    final json = await _apiClient.postJson(
      '/friends/$userId/block/',
      const <String, dynamic>{},
      accessToken: accessToken,
    );
    return json['message'] as String? ?? 'User blocked.';
  }

  Future<String> unblockUser({
    required String accessToken,
    required int userId,
  }) async {
    final json = await _apiClient.postJson(
      '/friends/$userId/unblock/',
      const <String, dynamic>{},
      accessToken: accessToken,
    );
    return json['message'] as String? ?? 'User unblocked.';
  }

  String _cleanMessage(String message) {
    final trimmed = message.trim();
    if (trimmed.isEmpty) {
      return 'Could not send friend request.';
    }

    final lines = trimmed.split('\n');
    final firstLine = lines.isEmpty ? trimmed : lines.first.trim();
    if (firstLine.contains('NameError')) {
      return 'Could not send friend request right now.';
    }
    return firstLine;
  }
}
