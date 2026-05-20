import 'package:flutter/material.dart';

class MySharingHubScreen extends StatelessWidget {
  const MySharingHubScreen({
    super.key,
    required this.onAccountAmend,
    required this.onOpenInbox,
    required this.onOpenMyOrders,
    required this.onOpenMyTransactions,
    required this.onOpenPaymentMethods,
    required this.activeOrdersCount,
    required this.biometricAvailable,
    required this.biometricEnabled,
    required this.onBiometricToggle,
  });

  final VoidCallback onAccountAmend;
  final VoidCallback onOpenInbox;
  final VoidCallback onOpenMyOrders;
  final VoidCallback onOpenMyTransactions;
  final VoidCallback onOpenPaymentMethods;
  final int activeOrdersCount;
  final bool biometricAvailable;
  final bool biometricEnabled;
  final ValueChanged<bool>? onBiometricToggle;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Sharing-Hub')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.mark_email_unread_outlined),
              title: const Text('Messages'),
              subtitle: const Text('All sent and received messages'),
              trailing: const Icon(Icons.chevron_right),
              onTap: onOpenInbox,
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.shopping_basket_outlined),
              title: const Text('My Orders'),
              subtitle: Text('Active orders: $activeOrdersCount'),
              trailing: const Icon(Icons.chevron_right),
              onTap: onOpenMyOrders,
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.receipt_long_outlined),
              title: const Text('My Transactions'),
              subtitle: const Text('Review active and completed rentals'),
              trailing: const Icon(Icons.chevron_right),
              onTap: onOpenMyTransactions,
            ),
          ),
          ListTile(
            leading: const Icon(Icons.account_circle_outlined),
            title: const Text('Account Details'),
            subtitle: const Text('Amend profile and account settings'),
            onTap: onAccountAmend,
          ),
          ListTile(
            leading: const Icon(Icons.credit_card_outlined),
            title: const Text('Payment Methods'),
            subtitle: const Text('Manage saved cards and defaults'),
            onTap: onOpenPaymentMethods,
          ),
          SwitchListTile(
            secondary: const Icon(Icons.fingerprint),
            title: const Text('Biometric unlock'),
            subtitle: Text(
              biometricAvailable
                  ? 'Use Face ID or fingerprint to unlock your saved session'
                  : 'Biometric unlock is not available on this device',
            ),
            value: biometricEnabled,
            onChanged: biometricAvailable ? onBiometricToggle : null,
          ),
          ListTile(
            leading: const Icon(Icons.notifications_active_outlined),
            title: const Text('Pending Actions'),
            subtitle: const Text('Coming soon'),
            enabled: false,
          ),
        ],
      ),
    );
  }
}
