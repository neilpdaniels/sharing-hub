import 'package:flutter/material.dart';

import '../models/transaction_models.dart';

class MyTransactionsScreen extends StatelessWidget {
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
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Transactions')),
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
                'Transactions',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              if (loading)
                const Center(child: Padding(
                  padding: EdgeInsets.all(24),
                  child: CircularProgressIndicator(),
                ))
              else if (transactions.isEmpty)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('No transactions yet.'),
                  ),
                )
              else
                ...transactions.map((tx) => _transactionTile(context, tx)),
            ],
          ),
        ),
      ),
    );
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
    final itemTitle = tx.itemName.trim().isEmpty ? 'Rental conversation' : tx.itemName;
    final partiesText = tx.partiesSummary.trim().isEmpty
        ? (tx.counterpartyName.trim().isEmpty ? 'Rental conversation' : tx.counterpartyName)
        : tx.partiesSummary;
    final termsText = '£${tx.price.toStringAsFixed(2)} per day'
        '${tx.quantity > 1 ? ' | qty ${tx.quantity}' : ''}'
        '${rentalDates != null ? ' | $rentalDates' : ''}';

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => onOpenTransaction(tx),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                backgroundColor: const Color(0xFFE7F3F1),
                child: Icon(Icons.handshake_outlined, color: statusColor),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      partiesText,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 4),
                    Text(itemTitle, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 2),
                    Text(termsText, style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: statusColor.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            statusText,
                            style: TextStyle(
                              color: statusColor,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        Text('Updated $updatedText', style: Theme.of(context).textTheme.bodySmall),
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
        return 'Rental discussion';
      case 'RAGR':
        return 'Rental agreed';
      case 'RDAYAWV':
        return 'Checkout awaiting verification';
      case 'RONG':
        return 'Rental ongoing';
      case 'RRTDAYAWV':
        return 'Return awaiting verification';
      case 'RRTDPEND':
        return 'Deposit return pending';
      case 'RRTDCON':
        return 'Deposit contested';
      case 'AWFB':
        return 'Awaiting feedback';
      case 'RCOMP':
        return 'Completed';
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
