import 'package:flutter/material.dart';

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment Methods')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_paymentMethods.isEmpty)
                    const Card(
                      child: Padding(
                        padding: EdgeInsets.all(16),
                        child: Text('No payment methods found.'),
                      ),
                    )
                  else
                    ..._paymentMethods.map(
                      (method) => Card(
                        child: ListTile(
                          leading: const Icon(Icons.credit_card_outlined),
                          title: Text('${method.cardBrand} ****${method.cardLast4}'),
                          subtitle: Text(method.isDefault ? 'Default' : 'Tap to set default'),
                          trailing: PopupMenuButton<String>(
                            onSelected: (value) {
                              if (value == 'default') {
                                _setDefault(method);
                              } else if (value == 'delete') {
                                _delete(method);
                              }
                            },
                            itemBuilder: (context) => [
                              const PopupMenuItem(value: 'default', child: Text('Set default')),
                              const PopupMenuItem(value: 'delete', child: Text('Delete')),
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
