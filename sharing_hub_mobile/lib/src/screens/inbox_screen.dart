import 'package:flutter/material.dart';

import '../models/transaction_models.dart';

class InboxScreen extends StatelessWidget {
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
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Inbox')),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFFF8F4EE), Color(0xFFF1FAF8)],
          ),
        ),
        child: RefreshIndicator(
          onRefresh: onRefresh,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const SizedBox(height: 12),
              Text(
                'Messages',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              if (loading)
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: CircularProgressIndicator(),
                  ),
                )
              else if (messages.isEmpty)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('No messages yet.'),
                  ),
                )
              else
                ...messages.map((message) => _messageTile(context, message)),
            ],
          ),
        ),
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
    final title = message.itemName.trim().isEmpty ? 'Rental conversation' : message.itemName;
    final counterparty = message.counterpartyName.trim().isEmpty ? 'Unknown sender' : message.counterpartyName;
    final preview = message.description.trim().isEmpty ? message.subject : message.description.trim();
    final attachmentCount = message.attachments.length;

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: message.transactionReference.isEmpty ? null : () => onOpenTransaction(message.transactionReference),
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
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 4),
                    Text(title, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 2),
                    Text(preview, maxLines: 2, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
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
                        if (isUnread)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.red.shade50,
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(
                              'Unread',
                              style: TextStyle(
                                color: Colors.red.shade700,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        if (attachmentCount > 0)
                          Text('Attachments: $attachmentCount', style: Theme.of(context).textTheme.bodySmall),
                        Text('Updated ${_friendlyDate(message.created)}', style: Theme.of(context).textTheme.bodySmall),
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
