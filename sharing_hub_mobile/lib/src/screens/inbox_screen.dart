import 'package:flutter/material.dart';

import '../models/transaction_models.dart';

class InboxScreen extends StatefulWidget {
  const InboxScreen({
    super.key,
    required this.messages,
    required this.loading,
    required this.onRefresh,
    required this.onOpenTransaction,
  });

  final List<InboxMessage> messages;
  final bool loading;
  final Future<void> Function() onRefresh;
  final Future<void> Function(String transactionReference) onOpenTransaction;

  @override
  State<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends State<InboxScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDarkMode = Theme.of(context).brightness == Brightness.dark;
    final gradientColors = isDarkMode
        ? const [Color(0xFF0F1419), Color(0xFF1A2332)]
        : const [Color(0xFFF8F4EE), Color(0xFFF1FAF8)];

    final receivedMessages = widget.messages
        .where((message) => message.direction == 'received')
        .toList(growable: false);
    final sentMessages = widget.messages
        .where((message) => message.direction != 'received')
        .toList(growable: false);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Messages'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Received'),
            Tab(text: 'Sent'),
          ],
        ),
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: gradientColors,
          ),
        ),
        child: TabBarView(
          controller: _tabController,
          children: [
            _messagesList(
              context,
              receivedMessages,
              emptyText: 'No received messages yet.',
            ),
            _messagesList(
              context,
              sentMessages,
              emptyText: 'No sent messages yet.',
            ),
          ],
        ),
      ),
    );
  }

  Widget _messagesList(
    BuildContext context,
    List<InboxMessage> messages, {
    required String emptyText,
  }) {
    return RefreshIndicator(
      onRefresh: widget.onRefresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const SizedBox(height: 8),
          if (widget.loading)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: CircularProgressIndicator(),
              ),
            )
          else if (messages.isEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(emptyText),
              ),
            )
          else
            ...messages.map((message) => _messageTile(context, message)),
        ],
      ),
    );
  }

  Widget _messageTile(BuildContext context, InboxMessage message) {
    final isReceived = message.direction == 'received';
    final isUnread = message.unread;
    final accentColor = isUnread
        ? Colors.red.shade700
        : isReceived
        ? Colors.blue.shade700
        : Colors.green.shade700;
    final title = message.itemName.trim().isEmpty
        ? 'Rental conversation'
        : message.itemName;
    final counterparty = message.counterpartyName.trim().isEmpty
        ? 'Unknown sender'
        : message.counterpartyName;
    final preview = message.description.trim().isEmpty
        ? message.subject
        : message.description.trim();
    final attachmentCount = message.attachments.length;

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => _MessageDetailScreen(
              message: message,
              onOpenTransaction: widget.onOpenTransaction,
            ),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                backgroundColor: accentColor.withValues(alpha: 0.12),
                child: Icon(
                  isReceived ? Icons.inbox_outlined : Icons.send_outlined,
                  color: accentColor,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      counterparty,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(title, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 2),
                    Text(
                      preview,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: accentColor.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            isReceived ? 'Received' : 'Sent',
                            style: TextStyle(
                              color: accentColor,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        if (isReceived)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: isUnread
                                  ? Colors.red.shade50
                                  : Colors.green.shade50,
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(
                              isUnread ? 'Unread' : 'Read',
                              style: TextStyle(
                                color: isUnread
                                    ? Colors.red.shade700
                                    : Colors.green.shade700,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        if (attachmentCount > 0)
                          Text(
                            'Attachments: $attachmentCount',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        Text(
                          'Updated ${_friendlyDate(message.created)}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                    if (message.transactionReference.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(
                        'Ref ${message.transactionReference}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }

  String _friendlyDate(DateTime? value) {
    if (value == null) {
      return 'recently';
    }
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    return '${months[value.month - 1]} ${value.day}, ${value.year}';
  }
}

class _MessageDetailScreen extends StatelessWidget {
  const _MessageDetailScreen({
    required this.message,
    required this.onOpenTransaction,
  });

  final InboxMessage message;
  final Future<void> Function(String transactionReference) onOpenTransaction;

  @override
  Widget build(BuildContext context) {
    final title = message.itemName.trim().isEmpty
        ? 'Rental conversation'
        : message.itemName;
    final counterparty = message.counterpartyName.trim().isEmpty
        ? 'Unknown sender'
        : message.counterpartyName;
    final body = message.description.trim().isEmpty
        ? message.subject
        : message.description.trim();
    final period = _rentalPeriodLabel(
      message.rentalStartDate,
      message.rentalEndDate,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Message')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 6),
                  Text(
                    'From/To: $counterparty',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Sent ${_friendlyDate(message.created)}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  if (period != null) ...[
                    const SizedBox(height: 4),
                    Text(period, style: Theme.of(context).textTheme.bodySmall),
                  ],
                  const SizedBox(height: 14),
                  Text(body, style: Theme.of(context).textTheme.bodyLarge),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          if (message.transactionReference.isNotEmpty)
            OutlinedButton.icon(
              onPressed: () async {
                await onOpenTransaction(message.transactionReference);
                if (context.mounted) {
                  Navigator.of(context).pop();
                }
              },
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open transaction'),
            ),
        ],
      ),
    );
  }

  String _friendlyDate(DateTime? value) {
    if (value == null) {
      return 'recently';
    }
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    return '${months[value.month - 1]} ${value.day}, ${value.year}';
  }

  String? _rentalPeriodLabel(DateTime? start, DateTime? end) {
    if (start == null && end == null) {
      return null;
    }
    final startLabel = start == null ? '?' : _isoDate(start);
    final endLabel = end == null ? '?' : _isoDate(end);
    return 'Rental dates: $startLabel to $endLabel';
  }

  String _isoDate(DateTime value) {
    return '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
  }
}
