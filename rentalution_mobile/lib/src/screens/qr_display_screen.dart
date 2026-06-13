import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

class QrDisplayScreen extends StatelessWidget {
  const QrDisplayScreen({
    super.key,
    required this.title,
    required this.qrPayload,
    required this.pin,
  });

  final String title;
  final String qrPayload;
  final String pin;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              QrImageView(
                data: qrPayload,
                version: QrVersions.auto,
                size: 260,
              ),
              const SizedBox(height: 16),
              Text(
                'PIN: $pin',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
