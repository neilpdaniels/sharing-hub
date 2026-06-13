import 'package:flutter/material.dart';

import '../services/push_notification_service.dart';

class NotificationSettingsScreen extends StatefulWidget {
  const NotificationSettingsScreen({
    super.key,
    required this.initialPreferences,
    required this.onSave,
    required this.onBack,
  });

  final NotificationPreferences initialPreferences;
  final Future<void> Function(NotificationPreferences preferences) onSave;
  final VoidCallback onBack;

  @override
  State<NotificationSettingsScreen> createState() =>
      _NotificationSettingsScreenState();
}

class _NotificationSettingsScreenState
    extends State<NotificationSettingsScreen> {
  late bool _transactionEnquiry;
  late bool _transactionMessages;
  late bool _inAppAlerts;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _transactionEnquiry = widget.initialPreferences.transactionEnquiry;
    _transactionMessages = widget.initialPreferences.transactionMessages;
    _inAppAlerts = widget.initialPreferences.inAppAlerts;
  }

  Future<void> _save() async {
    if (_saving) {
      return;
    }

    setState(() {
      _saving = true;
    });

    try {
      await widget.onSave(
        NotificationPreferences(
          transactionEnquiry: _transactionEnquiry,
          transactionMessages: _transactionMessages,
          inAppAlerts: _inAppAlerts,
        ),
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Notification settings saved.')),
      );
      widget.onBack();
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          onPressed: widget.onBack,
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Back',
        ),
        title: const Text('Notification settings'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          SwitchListTile(
            title: const Text('Transaction enquiries'),
            subtitle: const Text(
              'Push notifications when someone sends a new enquiry on your listing.',
            ),
            value: _transactionEnquiry,
            onChanged: (value) {
              setState(() {
                _transactionEnquiry = value;
              });
            },
          ),
          SwitchListTile(
            title: const Text('Transaction messages'),
            subtitle: const Text(
              'Push notifications for new messages in your bookings.',
            ),
            value: _transactionMessages,
            onChanged: (value) {
              setState(() {
                _transactionMessages = value;
              });
            },
          ),
          SwitchListTile(
            title: const Text('In-app alerts'),
            subtitle: const Text(
              'Show alert dialogs in the app when notifications arrive while using the app.',
            ),
            value: _inAppAlerts,
            onChanged: (value) {
              setState(() {
                _inAppAlerts = value;
              });
            },
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _saving ? null : _save,
            icon: _saving
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.save_outlined),
            label: Text(_saving ? 'Saving...' : 'Save preferences'),
          ),
        ],
      ),
    );
  }
}
