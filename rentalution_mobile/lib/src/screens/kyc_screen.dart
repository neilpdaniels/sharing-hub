import 'package:flutter/material.dart';

import '../models/account_models.dart';
import '../services/account_repository.dart';

class KycScreen extends StatefulWidget {
  const KycScreen({
    super.key,
    required this.accessToken,
    required this.accountRepository,
    required this.onBack,
  });

  final String? accessToken;
  final AccountRepository accountRepository;
  final VoidCallback onBack;

  @override
  State<KycScreen> createState() => _KycScreenState();
}

class _KycScreenState extends State<KycScreen> {
  bool _loading = true;
  bool _submitting = false;
  String? _error;
  KycStatus? _status;
  List<PaymentMethodSummary> _paymentMethods = const [];
  int? _selectedPaymentMethodId;

  @override
  void initState() {
    super.initState();
    _load();
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
      final status = await widget.accountRepository.fetchKycStatus(
        accessToken: token,
      );
      final paymentMethods = await widget.accountRepository.fetchPaymentMethods(
        accessToken: token,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _status = status;
        _paymentMethods = paymentMethods;
        _selectedPaymentMethodId ??= paymentMethods.isEmpty
            ? null
            : paymentMethods.firstWhere(
                (pm) => pm.isDefault,
                orElse: () => paymentMethods.first,
              ).id;
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

  Widget _checkRow(String label, bool ok) {
    return Row(
      children: [
        Icon(
          ok ? Icons.check_circle_outline : Icons.radio_button_unchecked,
          color: ok ? Colors.green : Colors.orange,
          size: 18,
        ),
        const SizedBox(width: 8),
        Expanded(child: Text(label)),
      ],
    );
  }

  Future<void> _startVerification() async {
    final token = widget.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }
    final paymentMethodId = _selectedPaymentMethodId;
    if (paymentMethodId == null) {
      setState(() {
        _error = 'Please add and select a saved payment method first.';
      });
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final result = await widget.accountRepository.startPaidKycVerification(
        accessToken: token,
        paymentMethodId: paymentMethodId,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            result['message']?.toString() ??
                'Verification fee charged. You can now continue with verification.',
          ),
        ),
      );
      await _load();
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
          _submitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _status;
    return Scaffold(
      appBar: AppBar(
        title: const Text('KYC Verification'),
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
          : ListView(
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
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          status?.statusLabel ?? 'Verification pending',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          status?.isVerified == true
                              ? 'Your identity currently satisfies the platform verification requirement.'
                              : 'Stripe verification is paid and must be charged before the verification session begins. If you stop part-way through, the charge still applies. If your address changes later, you will need to verify again.',
                        ),
                        const SizedBox(height: 16),
                        _checkRow('Email confirmed', status?.emailConfirmed ?? false),
                        const SizedBox(height: 8),
                        _checkRow('Mobile verified', status?.mobileVerified ?? false),
                        const SizedBox(height: 8),
                        _checkRow('Address verified', status?.addressVerified ?? false),
                        const SizedBox(height: 8),
                        _checkRow('Baseline KYC complete', status?.baselineVerified ?? false),
                        if (status?.verifiedAt != null) ...[
                          const SizedBox(height: 12),
                          Text('Verified at: ${status!.verifiedAt}'),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Pay and start verification',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Pick a saved card. We charge the fee before the Stripe verification session begins.',
                        ),
                        const SizedBox(height: 12),
                        DropdownButtonFormField<int>(
                          initialValue: _selectedPaymentMethodId,
                          decoration: const InputDecoration(
                            labelText: 'Saved payment method',
                          ),
                          items: _paymentMethods
                              .map(
                                (pm) => DropdownMenuItem(
                                  value: pm.id,
                                  child: Text(
                                    '${pm.cardBrand} ending ${pm.cardLast4}${pm.isDefault ? ' (Default)' : ''}',
                                  ),
                                ),
                              )
                              .toList(growable: false),
                          onChanged: _submitting
                              ? null
                              : (value) {
                                  setState(() {
                                    _selectedPaymentMethodId = value;
                                  });
                                },
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton(
                            onPressed: _submitting || _selectedPaymentMethodId == null
                                ? null
                                : _startVerification,
                            child: Text(
                              _submitting ? 'Charging...' : 'Pay and start verification',
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}
