import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/account_models.dart';
import '../services/account_repository.dart';

class AccountDetailsScreen extends StatefulWidget {
  const AccountDetailsScreen({
    super.key,
    required this.accessToken,
    required this.accountRepository,
  });

  final String accessToken;
  final AccountRepository accountRepository;

  @override
  State<AccountDetailsScreen> createState() => _AccountDetailsScreenState();
}

class _AccountDetailsScreenState extends State<AccountDetailsScreen> {
  final _formKey = GlobalKey<FormState>();

  final _firstNameController = TextEditingController();
  final _lastNameController = TextEditingController();
  final _emailController = TextEditingController();
  final _mobileController = TextEditingController();
  final _address1Controller = TextEditingController();
  final _address2Controller = TextEditingController();
  final _townController = TextEditingController();
  final _countyController = TextEditingController();
  final _postcodeController = TextEditingController();

  bool _loading = true;
  bool _saving = false;
  AccountDetails? _details;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _firstNameController.dispose();
    _lastNameController.dispose();
    _emailController.dispose();
    _mobileController.dispose();
    _address1Controller.dispose();
    _address2Controller.dispose();
    _townController.dispose();
    _countyController.dispose();
    _postcodeController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
    });

    try {
      final details = await widget.accountRepository.fetchAccountDetails(
        accessToken: widget.accessToken,
      );
      if (!mounted) {
        return;
      }
      _apply(details);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  void _apply(AccountDetails details) {
    _details = details;
    _firstNameController.text = details.firstName;
    _lastNameController.text = details.lastName;
    _emailController.text = details.email;
    _mobileController.text = details.mobileNumber;
    _address1Controller.text = details.addressLine1;
    _address2Controller.text = details.addressLine2;
    _townController.text = details.town;
    _countyController.text = details.county;
    _postcodeController.text = details.postcode;
  }

  Future<void> _startPayoutOnboarding() async {
    try {
      final url = await widget.accountRepository.startPayoutOnboarding(
        accessToken: widget.accessToken,
      );
      if (url.isEmpty || !await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication)) {
        throw Exception('Could not open Stripe payout setup.');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _saving = true;
    });

    try {
      final details = await widget.accountRepository.amendAccount(
        accessToken: widget.accessToken,
        fields: {
          'first_name': _firstNameController.text.trim(),
          'last_name': _lastNameController.text.trim(),
          'email': _emailController.text.trim(),
          'mobile_number': _mobileController.text.trim(),
          'address_line_1': _address1Controller.text.trim(),
          'address_line_2': _address2Controller.text.trim(),
          'town': _townController.text.trim(),
          'county': _countyController.text.trim(),
          'postcode': _postcodeController.text.trim(),
        },
      );
      if (!mounted) {
        return;
      }
      _apply(details);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Account details updated.')),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
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
      appBar: AppBar(title: const Text('Account Details')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Lender payouts', style: TextStyle(fontWeight: FontWeight.bold)),
                          const SizedBox(height: 8),
                          if (_details?.stripeConnectTransfersEnabled ?? false)
                            const Text('Your Stripe payout account can receive rental transfers.')
                          else ...[
                            const Text('Complete secure Stripe payout setup before accepting paid rentals.'),
                            if ((_details?.stripeConnectRequirements ?? const []).isNotEmpty)
                              Text('Stripe still needs: ${_details!.stripeConnectRequirements.join(', ')}'),
                            const SizedBox(height: 8),
                            OutlinedButton(
                              onPressed: _startPayoutOnboarding,
                              child: const Text('Set up lender payouts'),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _firstNameController,
                    decoration: const InputDecoration(labelText: 'First name'),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _lastNameController,
                    decoration: const InputDecoration(labelText: 'Last name'),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _emailController,
                    decoration: const InputDecoration(labelText: 'Email'),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _mobileController,
                    decoration: const InputDecoration(labelText: 'Mobile number'),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _address1Controller,
                    decoration: const InputDecoration(labelText: 'Address line 1'),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _address2Controller,
                    decoration: const InputDecoration(labelText: 'Address line 2'),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _townController,
                    decoration: const InputDecoration(labelText: 'Town'),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _countyController,
                    decoration: const InputDecoration(labelText: 'County'),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _postcodeController,
                    decoration: const InputDecoration(labelText: 'Postcode'),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: _saving ? null : _save,
                    child: Text(_saving ? 'Saving...' : 'Save changes'),
                  ),
                ],
              ),
            ),
    );
  }
}
