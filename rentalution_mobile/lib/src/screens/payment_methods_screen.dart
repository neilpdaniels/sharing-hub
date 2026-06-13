import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart' as stripe;

import '../models/account_models.dart';
import '../services/account_repository.dart';

class PaymentMethodsScreen extends StatefulWidget {
  const PaymentMethodsScreen({
    super.key,
    required this.accessToken,
    required this.accountRepository,
  });

  final String accessToken;
  final AccountRepository accountRepository;

  @override
  State<PaymentMethodsScreen> createState() => _PaymentMethodsScreenState();
}

class _PaymentMethodsScreenState extends State<PaymentMethodsScreen> {
  List<PaymentMethodSummary> _paymentMethods = const [];
  bool _loading = true;
  bool _showOnlyDefaultHint = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
    });

    try {
      final paymentMethods = await widget.accountRepository.fetchPaymentMethods(
        accessToken: widget.accessToken,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _paymentMethods = paymentMethods;
      });
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

  Future<void> _setDefault(PaymentMethodSummary method) async {
    await widget.accountRepository.setDefaultPaymentMethod(
      accessToken: widget.accessToken,
      paymentMethodId: method.id,
    );
    await _load();
  }

  Future<void> _delete(PaymentMethodSummary method) async {
    await widget.accountRepository.deletePaymentMethod(
      accessToken: widget.accessToken,
      paymentMethodId: method.id,
    );
    await _load();
  }

  Future<void> _confirmDelete(PaymentMethodSummary method) async {
    final shouldDelete = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Delete card?'),
          content: Text(
            '${method.cardBrand} ****${method.cardLast4} will be removed from your saved payment methods.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Delete'),
            ),
          ],
        );
      },
    );

    if (shouldDelete == true) {
      await _delete(method);
    }
  }

  Future<void> _addCard() async {
    setState(() {
      _loading = true;
    });

    try {
      final publishableKey = (await widget.accountRepository.fetchStripePublishableKey(
        accessToken: widget.accessToken,
      ))
          .trim();
      if (publishableKey.isEmpty) {
        throw Exception('Stripe publishable key is not configured.');
      }

      final session = await widget.accountRepository.createPaymentMethodSetupIntent(
        accessToken: widget.accessToken,
      );
      if (session.provider.toLowerCase() != 'stripe') {
        throw Exception('Cannot connect to Stripe right now.');
      }
      if (session.clientSecret.trim().isEmpty) {
        throw Exception('Stripe setup session is missing client secret.');
      }

      stripe.Stripe.publishableKey = publishableKey;
      await stripe.Stripe.instance.applySettings();
      await stripe.Stripe.instance.initPaymentSheet(
        paymentSheetParameters: stripe.SetupPaymentSheetParameters(
          setupIntentClientSecret: session.clientSecret,
          merchantDisplayName: 'rentalution',
        ),
      );
      try {
        await stripe.Stripe.instance.presentPaymentSheet();
      } on stripe.StripeException catch (e) {
        if (e.error.code == stripe.FailureCode.Canceled) {
          return;
        }
        rethrow;
      }

      final setupIntent = await stripe.Stripe.instance.retrieveSetupIntent(
        session.clientSecret,
      );
      final paymentMethodId = setupIntent.paymentMethodId.trim();
      final setupIntentId = setupIntent.id.trim();
      if (paymentMethodId.isEmpty || setupIntentId.isEmpty) {
        throw Exception('Stripe did not return a saved payment method.');
      }

      await widget.accountRepository.confirmPaymentMethodSetup(
        accessToken: widget.accessToken,
        setupIntentId: setupIntentId,
        paymentMethodId: paymentMethodId,
      );

      await _load();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Card saved successfully.')),
      );
    } on stripe.StripeException catch (e) {
      if (e.error.code == stripe.FailureCode.Canceled) {
        return;
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString())),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString())),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment methods')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  FilledButton.icon(
                    onPressed: _addCard,
                    icon: const Icon(Icons.add_card_outlined),
                    label: const Text('Add card'),
                  ),
                  const SizedBox(height: 12),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 4),
                    child: Text(
                      'These saved cards can be used for payments. For long rentals, the deposit card must be Visa or Mastercard credit card, and it can be different from the payment card.',
                    ),
                  ),
                  const SizedBox(height: 12),
                  Card(
                    color: const Color(0xFFF4FBFA),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Saved cards',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'These are the payment methods you have already saved for deposits and future rentals.',
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    value: _showOnlyDefaultHint,
                    onChanged: (value) {
                      setState(() {
                        _showOnlyDefaultHint = value;
                      });
                    },
                    title: const Text('Highlight default only'),
                    subtitle: const Text('Hides extra detail and keeps the list compact'),
                  ),
                  const SizedBox(height: 12),
                  if (_paymentMethods.isEmpty)
                    const Card(
                      child: Padding(
                        padding: EdgeInsets.all(16),
                        child: Text('No saved cards yet. Add one during a deposit setup.'),
                      ),
                    )
                  else
                    ..._paymentMethods.map(
                      (method) => Card(
                        child: ListTile(
                          leading: CircleAvatar(
                            backgroundColor: method.isDefault
                                ? const Color(0xFF2EC4B6)
                                : Theme.of(context).colorScheme.surfaceContainerHighest,
                            foregroundColor: method.isDefault
                                ? Colors.white
                                : Theme.of(context).colorScheme.onSurfaceVariant,
                            child: const Icon(Icons.credit_card_outlined),
                          ),
                          title: Row(
                            children: [
                              Expanded(
                                child: Text('${method.cardBrand} ****${method.cardLast4}'),
                              ),
                              if (method.isDefault)
                                const Padding(
                                  padding: EdgeInsets.only(left: 8),
                                  child: Chip(
                                    label: Text('Default'),
                                    visualDensity: VisualDensity.compact,
                                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                  ),
                                ),
                            ],
                          ),
                          subtitle: Text(
                            method.isDefault
                                ? 'Used by default for new deposit card setups'
                                : _showOnlyDefaultHint
                                    ? 'Tap the menu to make this the default'
                                    : 'Tap the menu to set default or delete',
                          ),
                          trailing: PopupMenuButton<String>(
                            onSelected: (value) {
                              if (value == 'default') {
                                _setDefault(method);
                              } else if (value == 'delete') {
                                _confirmDelete(method);
                              }
                            },
                            itemBuilder: (context) => [
                              if (!method.isDefault)
                                const PopupMenuItem(
                                  value: 'default',
                                  child: Text('Set default'),
                                ),
                              const PopupMenuItem(
                                value: 'delete',
                                child: Text('Delete'),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
    );
  }
}
