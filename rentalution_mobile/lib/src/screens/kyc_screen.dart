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
  String? _error;
  KycStatus? _status;

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
      if (!mounted) {
        return;
      }
      setState(() {
        _status = status;
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
                              : 'KYC is still being configured on the web flow, but these checks already matter for rentals that need extra trust.',
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
                  child: ListTile(
                    leading: const Icon(Icons.open_in_browser),
                    title: const Text('Open web verification'),
                    subtitle: const Text('Continue in the existing web KYC page'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: status?.webUrl == null || status!.webUrl.isEmpty
                        ? null
                        : () {},
                  ),
                ),
              ],
            ),
    );
  }
}
