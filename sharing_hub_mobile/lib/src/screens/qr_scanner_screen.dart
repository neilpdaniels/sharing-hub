import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class QrScannerScreen extends StatefulWidget {
  const QrScannerScreen({super.key});

  @override
  State<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends State<QrScannerScreen> {
  bool _handled = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan QR Code')),
      body: MobileScanner(
        onDetect: (capture) {
          if (_handled) {
            return;
          }
          final code = capture.barcodes.isNotEmpty ? capture.barcodes.first.rawValue : null;
          if (code == null || code.isEmpty) {
            return;
          }
          _handled = true;
          Navigator.of(context).pop(code);
        },
      ),
    );
  }
}
