import 'package:flutter/material.dart';

import '../models/friends_models.dart';
import '../services/friends_repository.dart';

class FriendsScreen extends StatefulWidget {
  const FriendsScreen({
    super.key,
    required this.accessToken,
    required this.friendsRepository,
    required this.onBack,
  });

  final String? accessToken;
  final FriendsRepository friendsRepository;
  final VoidCallback onBack;

  @override
  State<FriendsScreen> createState() => _FriendsScreenState();
}

class _FriendsScreenState extends State<FriendsScreen> {
  final TextEditingController _searchController = TextEditingController();
  bool _loading = true;
  bool _busy = false;
  String? _error;
  List<FriendSummary> _accepted = const [];
  List<FriendSummary> _pendingReceived = const [];
  List<FriendSummary> _pendingSent = const [];
  List<BlockedUserSummary> _blocked = const [];
  List<NearbyUser> _nearbyPeople = const [];
  final Set<int> _pendingRequests = <int>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final token = widget.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final hub = await widget.friendsRepository.fetchHub(accessToken: token);
      final nearby = await widget.friendsRepository.fetchNearbyPeople(
        accessToken: token,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _accepted = hub.accepted;
        _pendingReceived = hub.pendingReceived;
        _pendingSent = hub.pendingSent;
        _blocked = hub.blocked;
        _nearbyPeople = nearby;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  Future<void> _sendRequest(int userId, String label) async {
    final token = widget.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }
    setState(() {
      _busy = true;
      _pendingRequests.add(userId);
    });
    try {
      final message = await widget.friendsRepository.sendFriendRequest(
        accessToken: token,
        userId: userId,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      _searchController.clear();
      await _load();
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
          _pendingRequests.remove(userId);
        });
      }
    }
  }

  Future<void> _blockUser(int userId, String label) async {
    final token = widget.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }
    setState(() {
      _busy = true;
    });
    try {
      final message = await widget.friendsRepository.blockUser(
        accessToken: token,
        userId: userId,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      await _load();
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  Future<void> _unblockUser(int userId, String label) async {
    final token = widget.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }
    setState(() {
      _busy = true;
    });
    try {
      final message = await widget.friendsRepository.unblockUser(
        accessToken: token,
        userId: userId,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      await _load();
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  Future<void> _runFriendAction(
    Future<String> Function() action,
  ) async {
    final token = widget.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }
    setState(() {
      _busy = true;
    });
    try {
      final message = await action();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      await _load();
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  List<NearbyUser> get _filteredNearby {
    final query = _searchController.text.trim().toLowerCase();
    if (query.isEmpty) {
      return _nearbyPeople;
    }
    return _nearbyPeople.where((person) {
      final haystack = [
        person.username,
        person.displayName,
        person.town,
        person.postcode,
      ].join(' ').toLowerCase();
      return haystack.contains(query);
    }).toList(growable: false);
  }

  Widget _sectionTitle(String title, {String? subtitle}) {
    return Padding(
      padding: const EdgeInsets.only(top: 16, bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          if (subtitle != null) ...[
            const SizedBox(height: 4),
            Text(subtitle, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ],
      ),
    );
  }

  Widget _buildSectionCard({
    required String title,
    required String subtitle,
    required Widget emptyState,
    required List<Widget> children,
  }) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: Theme.of(
                      context,
                    ).colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    subtitle,
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            if (children.isEmpty)
              DefaultTextStyle(
                style: Theme.of(context).textTheme.bodyMedium!,
                child: emptyState,
              )
            else
              Column(
                children: children
                    .map(
                      (child) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: child,
                      ),
                    )
                    .toList(growable: false),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildFriendCard(FriendSummary friend) {
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          child: Text(friend.displayName.isNotEmpty ? friend.displayName[0].toUpperCase() : '?'),
        ),
        title: Text(friend.displayName),
        subtitle: Text(
          [
            '@${friend.username}',
            if (friend.town.isNotEmpty) friend.town,
            if (friend.postcode.isNotEmpty) friend.postcode,
          ].join(' • '),
        ),
        trailing: TextButton(
          onPressed: _busy
              ? null
              : () => _runFriendAction(
                    () => widget.friendsRepository.removeFriend(
                      accessToken: widget.accessToken!,
                      friendshipId: friend.friendshipId,
                    ),
                  ),
          child: const Text('Remove'),
        ),
      ),
    );
  }

  Widget _buildPendingCard(FriendSummary friend, {required bool incoming}) {
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          child: Text(friend.displayName.isNotEmpty ? friend.displayName[0].toUpperCase() : '?'),
        ),
        title: Text(friend.displayName),
        subtitle: Text(incoming ? 'Waiting for your response' : 'Awaiting their response'),
        trailing: Wrap(
          spacing: 8,
          children: incoming
              ? [
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => _runFriendAction(
                              () => widget.friendsRepository.acceptRequest(
                                accessToken: widget.accessToken!,
                                friendshipId: friend.friendshipId,
                              ),
                            ),
                    child: const Text('Accept'),
                  ),
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => _runFriendAction(
                              () => widget.friendsRepository.rejectRequest(
                                accessToken: widget.accessToken!,
                                friendshipId: friend.friendshipId,
                              ),
                            ),
                    child: const Text('Reject'),
                  ),
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => _blockUser(friend.userId, friend.displayName),
                    child: const Text('Block'),
                  ),
                ]
              : [
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => _runFriendAction(
                              () => widget.friendsRepository.cancelRequest(
                                accessToken: widget.accessToken!,
                                friendshipId: friend.friendshipId,
                              ),
                            ),
                    child: const Text('Cancel'),
                  ),
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => _blockUser(friend.userId, friend.displayName),
                    child: const Text('Block'),
                  ),
                ],
        ),
      ),
    );
  }

  Widget _buildBlockedCard(BlockedUserSummary block) {
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          child: Text(block.displayName.isNotEmpty ? block.displayName[0].toUpperCase() : '?'),
        ),
        title: Text(block.displayName),
        subtitle: Text('@${block.username}'),
        trailing: TextButton(
          onPressed: _busy
              ? null
              : () => _unblockUser(block.userId, block.displayName),
          child: const Text('Unblock'),
        ),
      ),
    );
  }

  Widget _buildNearbyCard(NearbyUser person) {
    final fullLabel = person.displayName.isNotEmpty ? person.displayName : person.username;
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          child: Text(fullLabel.isNotEmpty ? fullLabel[0].toUpperCase() : '?'),
        ),
        title: Text(fullLabel),
        subtitle: Text(
          [
            '@${person.username}',
            '${person.distanceKm.toStringAsFixed(1)} km away',
            if (person.town.isNotEmpty) person.town,
            if (person.postcode.isNotEmpty) person.postcode,
          ].join(' • '),
        ),
        trailing: ElevatedButton(
          onPressed: _busy || _pendingRequests.contains(person.id)
              ? null
              : () => _sendRequest(person.id, fullLabel),
          child: const Text('Add'),
        ),
        onLongPress: _busy ? null : () => _blockUser(person.id, fullLabel),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Friends'),
        leading: IconButton(
          onPressed: widget.onBack,
          icon: const Icon(Icons.arrow_back),
        ),
        actions: [
          IconButton(
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(
                        _error!,
                        style: TextStyle(color: Theme.of(context).colorScheme.error),
                      ),
                    ),
                  TextField(
                    controller: _searchController,
                    decoration: const InputDecoration(
                      prefixIcon: Icon(Icons.search),
                      labelText: 'Search nearby people',
                    ),
                    onChanged: (_) => setState(() {}),
                  ),
                  _buildSectionCard(
                    title: 'Accepted friends',
                    subtitle: '${_accepted.length}',
                    emptyState: const Text('No friends yet.'),
                    children: _accepted.map(_buildFriendCard).toList(growable: false),
                  ),
                  _buildSectionCard(
                    title: 'Incoming requests',
                    subtitle: '${_pendingReceived.length}',
                    emptyState: const Text('No incoming requests.'),
                    children: _pendingReceived
                        .map(
                          (friend) => _buildPendingCard(
                            friend,
                            incoming: true,
                          ),
                        )
                        .toList(growable: false),
                  ),
                  _buildSectionCard(
                    title: 'Sent requests',
                    subtitle: '${_pendingSent.length}',
                    emptyState: const Text('No sent requests.'),
                    children: _pendingSent
                        .map(
                          (friend) => _buildPendingCard(
                            friend,
                            incoming: false,
                          ),
                        )
                        .toList(growable: false),
                  ),
                  _buildSectionCard(
                    title: 'Nearby people',
                    subtitle: '${_filteredNearby.length}',
                    emptyState: const Text('No nearby people found.'),
                    children: _filteredNearby.map(_buildNearbyCard).toList(growable: false),
                  ),
                  _buildSectionCard(
                    title: 'Blocked users',
                    subtitle: '${_blocked.length}',
                    emptyState: const Text('No blocked users.'),
                    children: _blocked.map(_buildBlockedCard).toList(growable: false),
                  ),
                ],
              ),
            ),
    );
  }
}
