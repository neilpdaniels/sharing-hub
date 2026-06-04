import 'package:flutter/material.dart';

import '../models/transaction_models.dart';
import '../theme.dart';

class MyTransactionsScreen extends StatefulWidget {
  const MyTransactionsScreen({
    super.key,
    required this.transactions,
    required this.loading,
    required this.onRefresh,
    required this.onOpenTransaction,
  });

  final List<TransactionSummary> transactions;
  final bool loading;
  final Future<void> Function() onRefresh;
  final Future<void> Function(TransactionSummary tx) onOpenTransaction;

  @override
  State<MyTransactionsScreen> createState() => _MyTransactionsScreenState();
}

class _MyTransactionsScreenState extends State<MyTransactionsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  static const _openStatuses = {
    'RENQ',
    'RAGR',
    'RDAYAWV',
    'RONG',
    'RRTDAYAWV',
    'RRTDPEND',
  };
  static const _mediationStatuses = {
    'RRTDCON',
    'DMED',
    'DREQ',
  };
  static const _awaitingFeedbackStatuses = {
    'AWFB',
    'FB1SIDE',
  };
  static const _closedStatuses = {
    'CACK',
    'DRET',
    'DRED',
    'RCOMP',
    'RCMPNFB',
    'RRTDRET',
  };

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final gradientColors = sharingHubBackgroundGradient(
      Theme.of(context).brightness,
    );
    final openTransactions = _filterByStatus(widget.transactions, _openStatuses);
    final mediationTransactions =
        _filterByStatus(widget.transactions, _mediationStatuses);
    final awaitingFeedbackTransactions =
        _filterByStatus(
          widget.transactions
              .where((tx) => !tx.feedbackLeftByMe)
              .toList(growable: false),
          _awaitingFeedbackStatuses,
        );
    final closedTransactions =
        _filterByStatus(widget.transactions, _closedStatuses);

    return Scaffold(
      appBar: AppBar(
        title: const Text('My Bookings'),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: [
            Tab(text: 'Open (${openTransactions.length})'),
            Tab(text: 'Mediation${mediationTransactions.isNotEmpty ? ' (${mediationTransactions.length})' : ''}'),
            Tab(text: 'Needing feedback${awaitingFeedbackTransactions.isNotEmpty ? ' (${awaitingFeedbackTransactions.length})' : ''}'),
            Tab(text: 'Closed (${closedTransactions.length})'),
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
            _buildList(context, openTransactions, emptyText: 'No open bookings yet.'),
            _buildList(
              context,
              mediationTransactions,
              emptyText: mediationTransactions.isEmpty
                  ? 'You have no bookings in mediation.'
                  : 'No mediation bookings match.',
            ),
            _buildList(
              context,
              awaitingFeedbackTransactions,
              emptyText: awaitingFeedbackTransactions.isEmpty
                  ? 'You have no bookings awaiting feedback.'
                  : 'No feedback bookings match.',
            ),
            _buildList(context, closedTransactions, emptyText: 'No closed bookings yet.'),
          ],
        ),
      ),
    );
  }

  Widget _buildList(
    BuildContext context,
    List<TransactionSummary> transactions, {
    required String emptyText,
  }) {
    return RefreshIndicator(
      onRefresh: widget.onRefresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const SizedBox(height: 12),
          if (widget.loading)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: CircularProgressIndicator(),
              ),
            )
          else if (transactions.isEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(emptyText),
              ),
            )
          else
            ...transactions.map((tx) => _transactionTile(context, tx)),
        ],
      ),
    );
  }

  List<TransactionSummary> _filterByStatus(
    List<TransactionSummary> items,
    Set<String> statuses,
  ) {
    final filtered =
        items.where((tx) => statuses.contains(tx.status.trim().toUpperCase())).toList();
    filtered.sort((a, b) => (b.updatedAt ?? DateTime.fromMillisecondsSinceEpoch(0))
        .compareTo(a.updatedAt ?? DateTime.fromMillisecondsSinceEpoch(0)));
    return filtered;
  }

  Widget _transactionTile(BuildContext context, TransactionSummary tx) {
    final statusColor = tx.status == 'RENQ'
        ? Colors.orange.shade700
        : tx.status == 'RONG'
        ? Colors.green.shade700
        : Theme.of(context).colorScheme.primary;
    final statusText = _transactionStatusText(tx.status);
    final updatedText = _friendlyDate(tx.updatedAt);
    final rentalDates = _rentalDatesLabel(tx);
    final itemTitle = tx.itemName.trim().isEmpty
        ? 'Rental conversation'
        : tx.itemName;
    final partiesText = tx.partiesSummary.trim().isEmpty
        ? (tx.counterpartyName.trim().isEmpty
              ? 'Rental conversation'
              : tx.counterpartyName)
        : tx.partiesSummary;
    final termsText =
        '£${tx.price.toStringAsFixed(2)} per day'
        '${tx.quantity > 1 ? ' · qty ${tx.quantity}' : ''}';

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => onOpenTransaction(tx),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 54,
                height: 54,
                decoration: BoxDecoration(
                  color: const Color(0xFFE7F3F1),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(Icons.handshake_outlined, color: statusColor),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            itemTitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: statusColor.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            statusText,
                            style: TextStyle(
                              color: statusColor,
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      partiesText,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Colors.grey.shade700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(termsText, style: Theme.of(context).textTheme.bodySmall),
                    if (rentalDates != null) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(
                            Icons.date_range_outlined,
                            size: 14,
                            color: Colors.grey.shade600,
                          ),
                          const SizedBox(width: 4),
                          Flexible(
                            child: Text(
                              rentalDates,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(
                          Icons.update_outlined,
                          size: 14,
                          color: Colors.grey.shade600,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          'Updated $updatedText',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
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

  String _transactionStatusText(String code) {
    switch (code.trim().toUpperCase()) {
      case 'RENQ':
        return 'Discussion';
      case 'RAGR':
        return 'Agreement';
      case 'RDAYAWV':
        return 'Checkout verification';
      case 'RONG':
        return 'Ongoing';
      case 'RRTDAYAWV':
        return 'Return verification';
      case 'RRTDPEND':
        return 'Deposit review';
      case 'RRTDCON':
        return 'Deposit contested';
      case 'AWFB':
        return 'Feedback';
      case 'FB1SIDE':
        return 'Feedback';
      case 'RCOMP':
        return 'Completed';
      case 'RCMPNFB':
        return 'Closed';
      case 'CACK':
        return 'Cancelled';
      case 'DREQ':
        return 'Mediation';
      default:
        return code;
    }
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

  String? _rentalDatesLabel(TransactionSummary tx) {
    final start = tx.rentalStartDate;
    final end = tx.rentalEndDate;
    if (start == null || end == null) {
      return null;
    }
    return '${_friendlyDate(start)} - ${_friendlyDate(end)}';
  }
}
