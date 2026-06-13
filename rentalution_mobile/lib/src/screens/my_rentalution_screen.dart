import 'package:flutter/material.dart';

class MyRentalutionScreen extends StatelessWidget {
  const MyRentalutionScreen({
    super.key,
    required this.onAccountAmend,
    required this.onOpenInbox,
    required this.onOpenFriends,
    required this.onOpenMyOrders,
    required this.onOpenListMyItem,
    required this.onOpenMyTransactions,
    required this.onOpenFavourites,
    required this.onOpenPaymentMethods,
    required this.onOpenKyc,
    required this.onOpenNotificationSettings,
    required this.activeOrdersCount,
    required this.favouritesCount,
    required this.biometricAvailable,
    required this.biometricEnabled,
    required this.onBiometricToggle,
  });

  final VoidCallback onAccountAmend;
  final VoidCallback onOpenInbox;
  final VoidCallback onOpenFriends;
  final VoidCallback onOpenMyOrders;
  final VoidCallback onOpenListMyItem;
  final VoidCallback onOpenMyTransactions;
  final VoidCallback onOpenFavourites;
  final VoidCallback onOpenPaymentMethods;
  final VoidCallback onOpenKyc;
  final VoidCallback onOpenNotificationSettings;
  final int activeOrdersCount;
  final int favouritesCount;
  final bool biometricAvailable;
  final bool biometricEnabled;
  final ValueChanged<bool>? onBiometricToggle;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Rentalution')),
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
              leading: const Icon(Icons.add_business_outlined),
              title: const Text('List my item'),
              subtitle: const Text('Create a new listing'),
              trailing: const Icon(Icons.chevron_right),
              onTap: onOpenListMyItem,
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.people_outline),
              title: const Text('Friends'),
              subtitle: const Text('See nearby people and connect'),
              trailing: const Icon(Icons.chevron_right),
              onTap: onOpenFriends,
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.shopping_basket_outlined),
              title: const Text('My Listings'),
              subtitle: Text('Active listings: $activeOrdersCount'),
              trailing: const Icon(Icons.chevron_right),
              onTap: onOpenMyOrders,
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.receipt_long_outlined),
              title: const Text('My Bookings'),
              subtitle: const Text('Review active and completed rentals'),
              trailing: const Icon(Icons.chevron_right),
              onTap: onOpenMyTransactions,
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.favorite_outline),
              title: const Text('Favourites'),
              subtitle: Text('Saved listings: $favouritesCount'),
              trailing: const Icon(Icons.chevron_right),
              onTap: onOpenFavourites,
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
          ListTile(
            leading: const Icon(Icons.verified_user_outlined),
            title: const Text('KYC Verification'),
            subtitle: const Text('Check identity verification status'),
            onTap: onOpenKyc,
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
            title: const Text('Notification Settings'),
            subtitle: const Text('Choose which alerts to receive'),
            onTap: onOpenNotificationSettings,
          ),
        ],
      ),
    );
  }
}
