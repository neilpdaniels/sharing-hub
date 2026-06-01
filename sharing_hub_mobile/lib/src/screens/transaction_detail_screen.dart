import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart' as stripe;
import 'package:image_picker/image_picker.dart';

import '../config.dart';
import '../models/account_models.dart';
import '../models/transaction_models.dart';
import '../services/transaction_repository.dart';
import 'qr_display_screen.dart';
import 'qr_scanner_screen.dart';

class TransactionDetailScreen extends StatefulWidget {
  const TransactionDetailScreen({
    super.key,
    required this.transactionReference,
    required this.accessToken,
    required this.repository,
  });

  final String transactionReference;
  final String accessToken;
  final TransactionRepository repository;

  @override
  State<TransactionDetailScreen> createState() =>
      _TransactionDetailScreenState();
}

class _TransactionDetailScreenState extends State<TransactionDetailScreen> {
  final _messageController = TextEditingController();
  final _pinController = TextEditingController();
  final List<File> _images = [];
  final List<File> _videos = [];
  File? _evidenceVideoFile;
  String? _evidenceVideoUrl;

  TransactionDetail? _detail;
  TransactionCodes? _codes;
  List<TransactionMessage> _messages = const [];
  bool _loading = true;
  bool _busy = false;
  String? _error;
  Timer? _livePollTimer;
  String _lastLiveSignature = '';

  @override
  void initState() {
    super.initState();
    _refresh();
    _startLivePolling();
  }

  @override
  void dispose() {
    _livePollTimer?.cancel();
    _messageController.dispose();
    _pinController.dispose();
    super.dispose();
  }

  void _startLivePolling() {
    _livePollTimer?.cancel();
    final pollSeconds = AppConfig.transactionLivePollSeconds < 1
        ? 1
        : AppConfig.transactionLivePollSeconds;
    _livePollTimer = Timer.periodic(Duration(seconds: pollSeconds), (_) {
      if (!mounted || _loading || _busy) {
        return;
      }
      _refreshSilently();
    });
  }

  String _buildLiveSignature({
    required TransactionDetail detail,
    required List<TransactionMessage> messages,
    required TransactionCodes codes,
  }) {
    final latestMessage = messages.isEmpty ? null : messages.first;
    final latestMessageStamp = latestMessage == null
        ? ''
        : '${latestMessage.id}:${latestMessage.created?.toIso8601String() ?? ''}';

    return [
      detail.reference,
      detail.status,
      detail.paymentStatus,
      detail.depositStatus,
      detail.productStatus,
      detail.updatedAt?.toIso8601String() ?? '',
      messages.length.toString(),
      latestMessageStamp,
      codes.checkoutPin,
      codes.returnPin,
    ].join('|');
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final detail = await widget.repository.fetchTransactionDetail(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
      );
      final messages = await widget.repository.fetchMessages(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
      );
      final codes = await widget.repository.fetchCodes(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
      );
      if (!mounted) {
        return;
      }
      final canSubmitVideoEvidence = detail.canSubmitVideoEvidence;
      setState(() {
        _detail = detail;
        _messages = messages;
        _codes = codes;
        _lastLiveSignature = _buildLiveSignature(
          detail: detail,
          messages: messages,
          codes: codes,
        );
        if (!canSubmitVideoEvidence) {
          _evidenceVideoFile = null;
          _evidenceVideoUrl = null;
        }
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

  Future<void> _refreshSilently() async {
    try {
      final detail = await widget.repository.fetchTransactionDetail(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
      );
      final messages = await widget.repository.fetchMessages(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
      );
      final codes = await widget.repository.fetchCodes(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
      );

      if (!mounted) {
        return;
      }

      final signature = _buildLiveSignature(
        detail: detail,
        messages: messages,
        codes: codes,
      );
      if (signature == _lastLiveSignature) {
        return;
      }

      final canSubmitVideoEvidence = detail.canSubmitVideoEvidence;
      setState(() {
        _detail = detail;
        _messages = messages;
        _codes = codes;
        _lastLiveSignature = signature;
        if (!canSubmitVideoEvidence) {
          _evidenceVideoFile = null;
          _evidenceVideoUrl = null;
        }
      });
    } catch (_) {
      // Keep polling quiet; user can still manually refresh via actions.
    }
  }

  Future<void> _performAction(
    String action, {
    Map<String, dynamic> fields = const {},
  }) async {
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await widget.repository.performAction(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
        action: action,
        fields: fields,
      );
      await _refresh();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Action completed: $action')));
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
          _busy = false;
        });
      }
    }
  }

  Future<void> _pickImage() async {
    final picker = ImagePicker();
    final file = await picker.pickImage(source: ImageSource.gallery);
    if (file == null) {
      return;
    }
    setState(() {
      _images.add(File(file.path));
    });
  }

  Future<void> _pickVideo() async {
    final picker = ImagePicker();
    final file = await picker.pickVideo(source: ImageSource.gallery);
    if (file == null) {
      return;
    }
    setState(() {
      _videos.add(File(file.path));
    });
  }

  Future<void> _recordVideo() async {
    final picker = ImagePicker();
    final file = await picker.pickVideo(source: ImageSource.camera);
    if (file == null) {
      return;
    }
    setState(() {
      _videos.add(File(file.path));
    });
  }

  Future<void> _pickEvidenceVideo({required ImageSource source}) async {
    final picker = ImagePicker();
    final file = await picker.pickVideo(source: source);
    if (file == null) {
      return;
    }

    setState(() {
      _evidenceVideoFile = File(file.path);
      _evidenceVideoUrl = null;
    });
  }

  Future<void> _performVideoEvidenceAction({
    required String action,
    required String fieldName,
    required String actionLabel,
  }) async {
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final selectedFile = _evidenceVideoFile;
      final videoUrl = _evidenceVideoUrl ?? '';

      if (selectedFile != null) {
        await widget.repository.performActionWithFiles(
          accessToken: widget.accessToken,
          transactionReference: widget.transactionReference,
          action: action,
          fields: videoUrl.isNotEmpty ? {fieldName: videoUrl} : const {},
          videoFiles: [selectedFile],
        );
      } else if (videoUrl.isNotEmpty) {
        await widget.repository.performAction(
          accessToken: widget.accessToken,
          transactionReference: widget.transactionReference,
          action: action,
          fields: {fieldName: videoUrl},
        );
      } else {
        throw Exception(
          'Please choose or record a video first for $actionLabel.',
        );
      }

      if (mounted) {
        setState(() {
          _evidenceVideoFile = null;
          _evidenceVideoUrl = null;
        });
      }
      await _refresh();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Action completed: $action')));
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
          _busy = false;
        });
      }
    }
  }

  Future<bool> _showRentalTermsConfirmation() async {
    final agreed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Rental terms and conditions'),
          content: ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 420),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: const [
                  Text(
                    'Before confirming, please review the rental terms on the web version as they apply here as well. By continuing you agree to complete the handover, follow the agreed rental period, and raise any issues immediately through the transaction flow.',
                  ),
                  SizedBox(height: 12),
                  Text(
                    'This confirmation starts the same contract process used on the website. The booking can expire if it is not confirmed before the deadline.',
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('I Agree'),
            ),
          ],
        );
      },
    );
    return agreed ?? false;
  }

  DateTime? _contractDeadline(TransactionDetail detail) {
    final lenderAgreedAt = detail.lenderAgreedAt;
    if (lenderAgreedAt == null) {
      return null;
    }

    final deadlineByTime = lenderAgreedAt.add(const Duration(hours: 24));
    final rentalStartDate = detail.rentalStartDate;
    if (rentalStartDate == null) {
      return deadlineByTime;
    }

    final startOfDay = DateTime(
      rentalStartDate.year,
      rentalStartDate.month,
      rentalStartDate.day,
    );
    return deadlineByTime.isBefore(startOfDay) ? deadlineByTime : startOfDay;
  }

  String _formatDuration(Duration duration) {
    final safe = duration.isNegative ? Duration.zero : duration;
    final hours = safe.inHours;
    final minutes = safe.inMinutes.remainder(60);
    final seconds = safe.inSeconds.remainder(60);
    return '${hours.toString().padLeft(2, '0')}:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }

  Duration? _contractTimeRemaining(TransactionDetail detail) {
    final deadline = _contractDeadline(detail);
    if (deadline == null) {
      return null;
    }
    final remaining = deadline.difference(DateTime.now());
    return remaining.isNegative ? Duration.zero : remaining;
  }

  Future<void> _sendMessage() async {
    final body = _messageController.text.trim();
    if (body.isEmpty && _images.isEmpty && _videos.isEmpty) {
      setState(() {
        _error = 'Add message text or attachments before sending.';
      });
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await widget.repository.sendMessageWithAttachments(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
        messageBody: body,
        imageFiles: _images,
        videoFiles: _videos,
      );
      _messageController.clear();
      _images.clear();
      _videos.clear();
      await _refresh();
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  Future<void> _scanAndVerify(String action) async {
    final scanned = await Navigator.of(
      context,
    ).push<String>(MaterialPageRoute(builder: (_) => const QrScannerScreen()));
    if (scanned == null || scanned.isEmpty) {
      return;
    }
    await _performAction(action, fields: {'qr_payload': scanned});
  }

  String _displaySubject(String subject) {
    final value = subject.trim();
    if (value.isEmpty) {
      return 'Message';
    }
    if (value.startsWith('Transaction ')) {
      return 'Conversation update';
    }
    final cleaned = value
        .replaceAll(widget.transactionReference, '')
        .replaceAll('  ', ' ')
        .trim();
    return cleaned.isEmpty ? 'Conversation update' : cleaned;
  }

  String _roleText(TransactionDetail detail) {
    if (detail.meIsLender) {
      return 'Lender';
    }
    if (detail.meIsRenter) {
      return 'Borrower';
    }
    return 'Participant';
  }

  String _transactionStatusText(String code) {
    switch (code.trim().toUpperCase()) {
      case 'RENQ':
        return 'Rental discussion';
      case 'RAGR':
        return 'Rental agreed';
      case 'RDAYAWV':
        return 'Checkout day awaiting verification';
      case 'RONG':
        return 'Rental in progress';
      case 'RRTDAYAWV':
        return 'Return day awaiting verification';
      case 'RRTDPEND':
        return 'Deposit return pending';
      case 'RRTDRET':
        return 'Deposit returned';
      case 'RRTDCON':
        return 'Deposit return contested';
      case 'AWFB':
        return 'Awaiting feedback';
      case 'RCOMP':
        return 'Completed';
      case 'CREQ':
        return 'Cancellation requested';
      case 'CACK':
        return 'Cancelled';
      case 'DREQ':
        return 'Dispute requested';
      default:
        return code.trim().isEmpty ? '-' : code;
    }
  }

  String _paymentStatusText(String code) {
    switch (code.trim().toUpperCase()) {
      case 'PAYPEND':
        return 'Pending';
      case 'PAYCAP':
        return 'Captured';
      case 'PAYNA':
        return 'Not required';
      default:
        return code.trim().isEmpty ? '-' : code;
    }
  }

  String _depositStatusText(String code) {
    switch (code.trim().toUpperCase()) {
      case 'DEPPEND':
        return 'Pending hold';
      case 'DEPHOLD':
        return 'Held';
      case 'DEPRETF':
        return 'Returned in full';
      case 'DEPRETR':
        return 'Returned with reduction';
      case 'DEPMED':
        return 'Mediation required';
      default:
        return code.trim().isEmpty ? '-' : code;
    }
  }

  String _productStatusText(String code) {
    switch (code.trim().toUpperCase()) {
      case 'CONDPEND':
        return 'Condition evidence pending';
      case 'CHKVID':
        return 'Checkout evidence uploaded';
      case 'RTNVID':
        return 'Return evidence uploaded';
      default:
        return code.trim().isEmpty ? '-' : code;
    }
  }

  String _friendlyDate(DateTime? value) {
    if (value == null) {
      return '-';
    }
    final months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    final day = value.day.toString().padLeft(2, '0');
    final month = months[value.month - 1];
    final year = value.year.toString();
    return '$day $month $year';
  }

  int? _rentalDays(TransactionDetail detail) {
    final start = detail.rentalStartDate;
    final end = detail.rentalEndDate;
    if (start == null || end == null) {
      return null;
    }
    final normalizedStart = DateTime(start.year, start.month, start.day);
    final normalizedEnd = DateTime(end.year, end.month, end.day);
    final days = normalizedEnd.difference(normalizedStart).inDays + 1;
    if (days <= 0) {
      return null;
    }
    return days;
  }

  bool _showDepositProposalProgress(TransactionDetail detail) {
    return detail.status == 'RRTDPEND' ||
        detail.status == 'RRTDCON' ||
        detail.status == 'DREQ';
  }

  int _depositProposalIterationCount(TransactionDetail detail) {
    final count = detail.depositProposalIterationCount;
    return count < 0 ? 0 : count;
  }

  int _depositProposalIterationLimit(TransactionDetail detail) {
    final limit = detail.depositProposalIterationLimit;
    return limit < 1 ? 5 : limit;
  }

  String _depositProposalWarningText(TransactionDetail detail) {
    final serializerWarning = detail.depositProposalWarningMessage.trim();
    if (serializerWarning.isNotEmpty) {
      return serializerWarning;
    }
    final count = _depositProposalIterationCount(detail);
    final limit = _depositProposalIterationLimit(detail);
    if (count < 3) {
      return '';
    }
    return 'Iteration $count/$limit: if you do not reach agreement, this will be escalated to a dispute and may incur a fee.';
  }

  Widget _depositProposalProgressCard(TransactionDetail detail) {
    final count = _depositProposalIterationCount(detail);
    final limit = _depositProposalIterationLimit(detail);
    final warningText = _depositProposalWarningText(detail);
    final progress = (count / limit).clamp(0.0, 1.0);
    final progressColor = count >= limit
        ? Colors.red.shade700
        : count >= 3
        ? Colors.orange.shade700
        : const Color(0xFF2E7D6B);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Deposit proposal progress',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Iteration: $count/$limit',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                minHeight: 10,
                value: progress,
                color: progressColor,
                backgroundColor: Colors.grey.shade300,
              ),
            ),
            if (warningText.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: count >= limit
                      ? Colors.red.shade50
                      : Colors.orange.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: count >= limit
                        ? Colors.red.shade200
                        : Colors.orange.shade300,
                  ),
                ),
                child: Text(
                  warningText,
                  style: TextStyle(
                    color: count >= limit
                        ? Colors.red.shade800
                        : Colors.orange.shade900,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _summaryItem(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: RichText(
        text: TextSpan(
          style: Theme.of(context).textTheme.bodyMedium,
          children: [
            TextSpan(
              text: '$label: ',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            TextSpan(text: value),
          ],
        ),
      ),
    );
  }

  List<String> _listingVisualUrls(TransactionDetail detail) {
    if (detail.listingImageUrls.isNotEmpty) {
      return detail.listingImageUrls;
    }
    if (detail.listingImageUrl.trim().isNotEmpty) {
      return [detail.listingImageUrl];
    }
    return const [];
  }

  Future<String?> _promptForText({
    required String title,
    required String label,
    String initialValue = '',
    String? hint,
    bool required = true,
  }) async {
    final controller = TextEditingController(text: initialValue);
    final value = await showDialog<String>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: Text(title),
          content: TextField(
            controller: controller,
            autofocus: true,
            minLines: 2,
            maxLines: 4,
            decoration: InputDecoration(labelText: label, hintText: hint),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final text = controller.text.trim();
                if (required && text.isEmpty) {
                  return;
                }
                Navigator.pop(dialogContext, text);
              },
              child: const Text('Continue'),
            ),
          ],
        );
      },
    );
    controller.dispose();
    return value;
  }

  Future<Map<String, dynamic>?> _promptForDepositProposal(
    TransactionDetail detail,
  ) async {
    final amountController = TextEditingController(
      text:
          (detail.depositProposedReturnAmount > 0
                  ? detail.depositProposedReturnAmount
                  : detail.deposit)
              .toStringAsFixed(2),
    );
    final notesController = TextEditingController(
      text: detail.depositResolutionNotes,
    );

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Propose Deposit Return'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: amountController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: InputDecoration(
                  labelText:
                      'Amount to return (max £${detail.deposit.toStringAsFixed(2)})',
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: notesController,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: 'Notes (optional)',
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final parsed = double.tryParse(amountController.text.trim());
                if (parsed == null) {
                  return;
                }
                Navigator.pop(dialogContext, {
                  'deposit_proposed_return_amount': parsed,
                  'deposit_resolution_notes': notesController.text.trim(),
                });
              },
              child: const Text('Send Proposal'),
            ),
          ],
        );
      },
    );

    amountController.dispose();
    notesController.dispose();
    return result;
  }

  Future<Map<String, dynamic>?> _promptForFeedback() async {
    final comms = TextEditingController();
    final delivery = TextEditingController();
    final overall = TextEditingController();
    final comment = TextEditingController();

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Submit Feedback'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: comms,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Comms (0-5)'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: delivery,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Delivery/Return (0-5)',
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: overall,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Overall (0-5)'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: comment,
                  minLines: 2,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    labelText: 'Comment (optional)',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final commsScore = int.tryParse(comms.text.trim());
                final deliveryScore = int.tryParse(delivery.text.trim());
                final overallScore = int.tryParse(overall.text.trim());
                if (commsScore == null ||
                    deliveryScore == null ||
                    overallScore == null) {
                  return;
                }
                Navigator.pop(dialogContext, {
                  'communication_rating': commsScore,
                  'delivery_return_rating': deliveryScore,
                  'overall_rating': overallScore,
                  'feedback_comment': comment.text.trim(),
                });
              },
              child: const Text('Submit'),
            ),
          ],
        );
      },
    );

    comms.dispose();
    delivery.dispose();
    overall.dispose();
    comment.dispose();
    return result;
  }

  Future<Map<String, dynamic>?> _promptForCardDetails() async {
    final cardholderNameController = TextEditingController();
    final cardBrandController = TextEditingController();
    final cardLast4Controller = TextEditingController();

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Add deposit card details'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: cardholderNameController,
                  decoration: const InputDecoration(
                    labelText: 'Cardholder name',
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: cardBrandController,
                  decoration: const InputDecoration(
                    labelText: 'Card brand',
                    hintText: 'e.g. Visa, Mastercard',
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: cardLast4Controller,
                  keyboardType: TextInputType.number,
                  maxLength: 4,
                  decoration: const InputDecoration(labelText: 'Last 4 digits'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final name = cardholderNameController.text.trim();
                final brand = cardBrandController.text.trim();
                final last4 = cardLast4Controller.text.trim();
                if (name.isEmpty ||
                    last4.length != 4 ||
                    int.tryParse(last4) == null) {
                  return;
                }
                Navigator.pop(dialogContext, {
                  'cardholder_name': name,
                  'card_brand': brand,
                  'card_last4': last4,
                });
              },
              child: const Text('Save card'),
            ),
          ],
        );
      },
    );

    cardholderNameController.dispose();
    cardBrandController.dispose();
    cardLast4Controller.dispose();
    return result;
  }

  Future<stripe.PaymentMethodParams?>
  _promptForStripePaymentMethodParams() async {
    final cardholderNameController = TextEditingController();
    var cardComplete = false;
    String? inlineError;

    final params = await showDialog<stripe.PaymentMethodParams>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (dialogBuildContext, setDialogState) {
            return AlertDialog(
              title: const Text('Add deposit card (Stripe)'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: cardholderNameController,
                      decoration: const InputDecoration(
                        labelText: 'Cardholder name (optional)',
                      ),
                    ),
                    const SizedBox(height: 10),
                    stripe.CardField(
                      enablePostalCode: true,
                      onCardChanged: (card) {
                        setDialogState(() {
                          cardComplete = card?.complete ?? false;
                          if (cardComplete) {
                            inlineError = null;
                          }
                        });
                      },
                    ),
                    if (inlineError != null) ...[
                      const SizedBox(height: 10),
                      Text(
                        inlineError!,
                        style: const TextStyle(color: Colors.red),
                      ),
                    ],
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () {
                    if (!cardComplete) {
                      setDialogState(() {
                        inlineError = 'Please enter complete card details.';
                      });
                      return;
                    }

                    final name = cardholderNameController.text.trim();
                    Navigator.pop(
                      dialogContext,
                      stripe.PaymentMethodParams.card(
                        paymentMethodData: stripe.PaymentMethodData(
                          billingDetails: stripe.BillingDetails(
                            name: name.isEmpty ? null : name,
                          ),
                        ),
                      ),
                    );
                  },
                  child: const Text('Confirm card'),
                ),
              ],
            );
          },
        );
      },
    );

    cardholderNameController.dispose();
    return params;
  }

  Future<void> _setupDepositCardWithStripe() async {
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final publishableKey = AppConfig.stripePublishableKey.trim();
      if (publishableKey.isEmpty) {
        throw Exception(
          'Stripe publishable key is not configured for mobile. Provide STRIPE_PUBLISHABLE_KEY.',
        );
      }

      final session = await widget.repository.createStripeSetupIntent(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
      );

      if (session.provider.toLowerCase() != 'stripe') {
        if (session.provider.toLowerCase() == 'placeholder') {
          final fields = await _promptForCardDetails();
          if (fields == null) {
            return;
          }
          await widget.repository.performAction(
            accessToken: widget.accessToken,
            transactionReference: widget.transactionReference,
            action: 'add_deposit_card',
            fields: fields,
          );
          await _refresh();
          if (!mounted) {
            return;
          }
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Stripe is unavailable for this environment. Manual card setup submitted instead.',
              ),
            ),
          );
          return;
        }
        throw Exception(
          'Native Stripe entry is unavailable in ${session.provider.isEmpty ? 'current' : session.provider} mode.',
        );
      }
      if (session.clientSecret.trim().isEmpty) {
        throw Exception('Stripe setup session is missing client secret.');
      }

      stripe.Stripe.publishableKey = publishableKey;
      await stripe.Stripe.instance.applySettings();

      final paymentMethodParams = await _promptForStripePaymentMethodParams();
      if (paymentMethodParams == null) {
        return;
      }

      final setupIntent = await stripe.Stripe.instance.confirmSetupIntent(
        paymentIntentClientSecret: session.clientSecret,
        params: paymentMethodParams,
      );

      final paymentMethodId = setupIntent.paymentMethodId.trim();
      final setupIntentId = setupIntent.id.trim();
      if (paymentMethodId.isEmpty) {
        throw Exception('Stripe did not return a payment method id.');
      }

      await widget.repository.performAction(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
        action: 'confirm_stripe_card',
        fields: {
          'payment_method_id': paymentMethodId,
          if (setupIntentId.isNotEmpty) 'setup_intent_id': setupIntentId,
        },
      );

      await _refresh();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Deposit card setup submitted.')),
      );
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
          _busy = false;
        });
      }
    }
  }

  Future<PaymentMethodSummary?> _promptForExistingPaymentMethod() async {
    final methods = await widget.repository.fetchPaymentMethods(
      accessToken: widget.accessToken,
    );
    if (methods.isEmpty) {
      if (!mounted) {
        return null;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No saved payment methods found.')),
      );
      return null;
    }

    return showDialog<PaymentMethodSummary>(
      context: context,
      builder: (dialogContext) {
        return SimpleDialog(
          title: const Text('Use existing card'),
          children: methods
              .map(
                (method) => SimpleDialogOption(
                  onPressed: () => Navigator.pop(dialogContext, method),
                  child: Text(
                    '${method.cardBrand} ****${method.cardLast4}${method.isDefault ? ' (default)' : ''}',
                  ),
                ),
              )
              .toList(growable: false),
        );
      },
    );
  }

  String _depositCardStatusText(String status) {
    if (status == 'READY') {
      return 'Deposit card ready';
    }
    if (status == 'FAILED') {
      return 'Deposit card setup failed';
    }
    return 'No deposit card on file';
  }

  int _workflowStep(TransactionDetail detail) {
    final status = detail.status;
    final missingRentalVoided =
        status == 'CACK' &&
        detail.depositResolutionNotes.contains('[MISSING_RENTAL_VOIDED]');
    if (status == 'RENQ') return 1;
    if (status == 'RAGR') {
      if (detail.renterAgreedAt != null) return 4;
      if (detail.lenderAgreedAt != null) return 3;
      return 2;
    }
    if (status == 'RDAYAWV' || status == 'RONG') return 5;
    if (status == 'RRTDAYAWV' ||
        status == 'RRTDPEND' ||
        status == 'RRTDCON' ||
        status == 'DREQ' ||
        status == 'RRTDRET') {
      return 6;
    }
    if (status == 'AWFB' || status == 'RCOMP' || missingRentalVoided) return 7;
    return 1;
  }

  Widget _workflowCard(TransactionDetail detail) {
    final current = _workflowStep(detail);
    const labels = [
      '1. Rental discussion',
      '2. Lender confirms contract',
      '3. Borrower confirms contract',
      '4. Borrower card setup',
      '5. Checkout evidence + confirmation/counter + borrower PIN to lender',
      '6. Return evidence + confirmation/counter + deposit proposal cycle + lender PIN to borrower',
      '7. Feedback (both parties): star ratings + commentary',
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Workflow Timeline',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                ...labels.asMap().entries.map((entry) {
                  final step = entry.key + 1;
                  final active = step == current;
                  final done = step < current;

                  Color statusColor = done
                      ? Colors.green.shade700
                      : active
                      ? const Color(0xFF2E7D6B)
                      : Colors.grey.shade400;

                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: active
                            ? const Color(0xFFF0FAF8)
                            : done
                            ? Colors.green.shade50
                            : Colors.grey.shade50,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: active
                              ? const Color(0xFF2E7D6B)
                              : done
                              ? Colors.green.shade200
                              : Colors.grey.shade200,
                          width: active ? 2 : 1,
                        ),
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 28,
                            height: 28,
                            decoration: BoxDecoration(
                              color: statusColor,
                              shape: BoxShape.circle,
                            ),
                            child: Center(
                              child: done
                                  ? const Icon(
                                      Icons.check,
                                      color: Colors.white,
                                      size: 16,
                                    )
                                  : Text(
                                      step.toString(),
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontWeight: FontWeight.bold,
                                        fontSize: 12,
                                      ),
                                    ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              entry.value,
                              style: TextStyle(
                                fontWeight: active
                                    ? FontWeight.w700
                                    : FontWeight.w500,
                                color: done
                                    ? Colors.green.shade700
                                    : active
                                    ? const Color(0xFF2E7D6B)
                                    : Colors.grey.shade700,
                              ),
                            ),
                          ),
                          if (done)
                            Icon(
                              Icons.check_circle,
                              color: Colors.green.shade700,
                              size: 20,
                            )
                          else if (active)
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 4,
                              ),
                              decoration: BoxDecoration(
                                color: const Color(0xFFFF69B4),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: const Text(
                                'Current',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  );
                }),
              ],
            ),
          ),
        ),
        if (current >= 5) ...[
          const SizedBox(height: 16),
          _checkoutCheckInSection(detail),
        ],
      ],
    );
  }

  Widget _checkoutCheckInSection(TransactionDetail detail) {
    final current = _workflowStep(detail);
    final isCheckout = current == 5;
    final title = isCheckout
        ? 'Checkout Handover Evidence'
        : 'Return Handover Evidence';
    final isPastCheckout = current > 5;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.amber.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.amber.shade200),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.info_outline,
                    color: Colors.amber.shade700,
                    size: 20,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Placeholder - features coming soon',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.amber.shade700,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            // Show verification code section if PIN is available or at checkout stage
            if (isCheckout ||
                (isPastCheckout &&
                    detail.checkoutHandoverPinGeneratedAt != null))
              _pinSection('Verification Code'),
            if (!isCheckout ||
                (isPastCheckout && detail.returnHandoverPinGeneratedAt != null))
              _pinSection('Return Code'),
            const SizedBox(height: 16),
            // Show condition evidence section
            _conditionEvidenceSection(detail, isCheckout),
          ],
        ),
      ),
    );
  }

  Widget _pinSection(String label) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: Colors.grey.shade50,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.grey.shade300),
          ),
          child: Row(
            children: [
              Icon(Icons.qr_code_2, color: Colors.grey.shade400),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'PIN verification will appear here',
                  style: TextStyle(color: Colors.grey, fontSize: 13),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
      ],
    );
  }

  Widget _conditionEvidenceSection(TransactionDetail detail, bool isCheckout) {
    final hasCheckoutEvidence = detail.checkoutConditionVideoUrl.isNotEmpty;
    final hasReturnEvidence = detail.returnConditionVideoUrl.isNotEmpty;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              'Condition Evidence',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(width: 8),
            if (hasCheckoutEvidence && isCheckout)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.green.shade100,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  'Uploaded',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: Colors.green.shade700,
                  ),
                ),
              )
            else if (hasReturnEvidence && !isCheckout)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.green.shade100,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  'Uploaded',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: Colors.green.shade700,
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.grey.shade50,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.grey.shade300),
          ),
          child: Column(
            children: [
              Icon(
                Icons.videocam_outlined,
                size: 32,
                color: Colors.grey.shade400,
              ),
              const SizedBox(height: 8),
              Text(
                'Video upload placeholder',
                style: TextStyle(color: Colors.grey.shade500, fontSize: 12),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  OutlinedButton.icon(
                    onPressed: null,
                    icon: const Icon(Icons.video_library_outlined),
                    label: const Text('Choose Video'),
                  ),
                  const SizedBox(width: 8),
                  OutlinedButton.icon(
                    onPressed: null,
                    icon: const Icon(Icons.videocam_outlined),
                    label: const Text('Record'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final detail = _detail;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rental booking'),
        actions: [
          IconButton(
            onPressed: _loading || _busy ? null : _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : detail == null
          ? Center(child: Text(_error ?? 'Unable to load booking.'))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _summaryCard(detail),
                  if (_showDepositProposalProgress(detail)) ...[
                    const SizedBox(height: 16),
                    _depositProposalProgressCard(detail),
                  ],
                  const SizedBox(height: 16),
                  _workflowCard(detail),
                  const SizedBox(height: 16),
                  _actionsCard(detail),
                  const SizedBox(height: 16),
                  _codesCard(),
                  const SizedBox(height: 16),
                  _messageComposerCard(),
                  const SizedBox(height: 16),
                  _messagesCard(),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(_error!, style: const TextStyle(color: Colors.red)),
                  ],
                ],
              ),
            ),
    );
  }

  Widget _summaryCard(TransactionDetail detail) {
    final visualUrls = _listingVisualUrls(detail);
    final rentalDays = _rentalDays(detail);
    final estimatedRentalTotal = rentalDays != null
        ? detail.price * rentalDays
        : null;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (visualUrls.isNotEmpty) ...[
              SizedBox(
                height: 180,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: visualUrls.length,
                  separatorBuilder: (context, index) =>
                      const SizedBox(width: 10),
                  itemBuilder: (context, index) {
                    final visualUrl = visualUrls[index];
                    return ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: AspectRatio(
                        aspectRatio: 1.25,
                        child: Image.network(
                          visualUrl,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) =>
                              const SizedBox.shrink(),
                        ),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 12),
            ],
            Text(
              'Transaction summary',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            _summaryItem('Status', _transactionStatusText(detail.status)),
            _summaryItem('Role', _roleText(detail)),
            _summaryItem('Payment', _paymentStatusText(detail.paymentStatus)),
            _summaryItem('Deposit', _depositStatusText(detail.depositStatus)),
            _summaryItem(
              'Evidence status',
              _productStatusText(detail.productStatus),
            ),
            _summaryItem(
              'Price per day',
              '£${detail.price.toStringAsFixed(2)}',
            ),
            if (rentalDays != null)
              _summaryItem('Rental length', '$rentalDays day(s)'),
            if (estimatedRentalTotal != null)
              _summaryItem(
                'Estimated rental total (price per day x days)',
                '£${estimatedRentalTotal.toStringAsFixed(2)}',
              ),
            _summaryItem(
              'Deposit amount',
              '£${detail.deposit.toStringAsFixed(2)}',
            ),
            if (detail.rentalStartDate != null || detail.rentalEndDate != null)
              _summaryItem(
                'Dates',
                '${_friendlyDate(detail.rentalStartDate)} to ${_friendlyDate(detail.rentalEndDate)}',
              ),
            if (estimatedRentalTotal == null)
              Padding(
                padding: const EdgeInsets.only(top: 2, bottom: 6),
                child: Text(
                  'Total is shown once both rental start and end dates are available.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            if (detail.depositProposedByLenderAt != null)
              _summaryItem(
                'Current deposit proposal',
                '£${detail.depositProposedReturnAmount.toStringAsFixed(2)}',
              ),
            if (detail.depositResolutionNotes.trim().isNotEmpty)
              _summaryItem('Deposit notes', detail.depositResolutionNotes),
            if (detail.checkoutConditionVideoUrl.isNotEmpty)
              _summaryItem('Checkout evidence', 'Uploaded'),
            if (detail.returnConditionVideoUrl.isNotEmpty)
              _summaryItem('Return evidence', 'Uploaded'),
          ],
        ),
      ),
    );
  }

  Widget _actionsCard(TransactionDetail detail) {
    final actions = <Widget>[];
    final contractRemaining = _contractTimeRemaining(detail);
    final needsCardSetup =
        detail.meIsRenter &&
        (detail.status == 'RENQ' || detail.status == 'RAGR') &&
        detail.depositCardSetupStatus != 'READY';
    final nativeStripeConfigured = AppConfig.stripePublishableKey
        .trim()
        .isNotEmpty;
    final canSubmitVideoEvidence = detail.canSubmitVideoEvidence;
    final proposalIterationCount = _depositProposalIterationCount(detail);
    final proposalIterationLimit = _depositProposalIterationLimit(detail);
    final proposalMaxReached = proposalIterationCount >= proposalIterationLimit;

    if (detail.status == 'RAGR' && contractRemaining != null) {
      actions.add(
        Text(
          contractRemaining == Duration.zero
              ? 'Contract confirmation window has expired.'
              : 'Contract confirmation window remaining: ${_formatDuration(contractRemaining)}',
        ),
      );
      actions.add(const SizedBox(height: 8));
    }

    if (detail.status == 'RENQ' && detail.meIsLender) {
      actions.add(
        _actionButton('Agree Rental', () => _performAction('agree_rental')),
      );
      actions.add(
        _actionButton('Reject Enquiry', () => _performAction('reject_enquiry')),
      );
    }

    if (detail.status == 'RENQ') {
      actions.add(
        _actionButton('Request Cancellation', () async {
          final reason = await _promptForText(
            title: 'Request Cancellation',
            label: 'Reason',
            hint: 'Explain why you need to cancel',
          );
          if (reason == null || reason.isEmpty) {
            return;
          }
          await _performAction(
            'request_cancellation',
            fields: {'reason': reason},
          );
        }),
      );
    }

    if (detail.status == 'RAGR' &&
        detail.meIsLender &&
        detail.lenderAgreedAt == null) {
      actions.add(
        _actionButton('Confirm Lender Contract', () async {
          final agreed = await _showRentalTermsConfirmation();
          if (!agreed) {
            return;
          }
          await _performAction('confirm_lender_contract');
        }),
      );
    }

    if (detail.status == 'RAGR' &&
        detail.meIsLender &&
        detail.lenderAgreedAt != null &&
        detail.renterAgreedAt == null) {
      actions.add(
        _actionButton(
          'Re-send Confirmation Request',
          () => _performAction('reinitiate_lender_contract'),
        ),
      );
    }

    if (detail.status == 'RAGR' &&
        detail.meIsRenter &&
        detail.renterAgreedAt == null) {
      actions.add(
        _actionButton('Confirm Renter Contract', () async {
          final agreed = await _showRentalTermsConfirmation();
          if (!agreed) {
            return;
          }
          if (contractRemaining == Duration.zero) {
            if (!mounted) {
              return;
            }
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text(
                  'Contract confirmation window has expired. This rental can no longer be confirmed.',
                ),
              ),
            );
            return;
          }
          await _performAction('confirm_renter_contract');
        }),
      );
      actions.add(
        _actionButton(
          'Reject Agreement',
          () => _performAction('reject_rental_agreement'),
        ),
      );
    }

    if ((detail.status == 'RENQ' || detail.status == 'RAGR') &&
        detail.meIsRenter &&
        detail.rentalStartDate != null &&
        DateTime.now().isAfter(
          DateTime(
            detail.rentalStartDate!.year,
            detail.rentalStartDate!.month,
            detail.rentalStartDate!.day,
            23,
            59,
            59,
          ),
        ) &&
        detail.checkoutHandoverVerifiedAt == null) {
      actions.add(
        _actionButton('Report Missing Rental', () async {
          final reason = await _promptForText(
            title: 'Report Missing Rental',
            label: 'Reason',
            hint: 'Explain what happened',
          );
          if (reason == null || reason.isEmpty) {
            return;
          }
          await _performAction(
            'report_missing_rental',
            fields: {'reason': reason},
          );
        }),
      );
    }

    if (detail.status == 'RAGR' && detail.meIsLender) {
      actions.add(
        _actionButton(
          'Initiate Rental',
          () => _performVideoEvidenceAction(
            action: 'initiate_rental',
            fieldName: 'checkout_video_url',
            actionLabel: 'initiate_rental',
          ),
        ),
      );
    }

    if (needsCardSetup) {
      actions.add(
        Text(
          'Deposit card status: ${_depositCardStatusText(detail.depositCardSetupStatus)}',
        ),
      );
      actions.add(const SizedBox(height: 8));
      actions.add(
        nativeStripeConfigured
            ? _actionButton(
                'Add Deposit Card (Stripe)',
                _setupDepositCardWithStripe,
              )
            : _actionButton('Add Deposit Card', () async {
                final fields = await _promptForCardDetails();
                if (fields == null) {
                  return;
                }
                await _performAction('add_deposit_card', fields: fields);
              }),
      );
      if (nativeStripeConfigured) {
        actions.add(
          const Text(
            'Secure Stripe card entry is enabled on this mobile build.',
          ),
        );
      }
      actions.add(
        _actionButton('Use Existing Saved Card', () async {
          final method = await _promptForExistingPaymentMethod();
          if (method == null) {
            return;
          }
          await _performAction(
            'use_existing_card',
            fields: {'payment_method_id': method.id},
          );
        }),
      );
    }

    if (detail.status == 'RDAYAWV' && detail.meIsRenter) {
      actions.add(
        _actionButton(
          'Confirm Checkout Evidence',
          () => _performAction('confirm_checkout_evidence'),
        ),
      );
      actions.add(
        _actionButton(
          'Submit Borrower Checkout Evidence',
          () => _performVideoEvidenceAction(
            action: 'submit_checkout_borrower_evidence',
            fieldName: 'checkout_borrower_video_url',
            actionLabel: 'submit_checkout_borrower_evidence',
          ),
        ),
      );
      actions.add(
        _actionButton(
          'Verify Checkout via QR Scan',
          () => _scanAndVerify('verify_checkout_handover_pin'),
        ),
      );
      actions.add(
        _actionButton(
          'Verify Checkout via PIN',
          () => _performAction(
            'verify_checkout_handover_pin',
            fields: {'pin': _pinController.text.trim()},
          ),
        ),
      );
    }

    if (detail.status == 'RDAYAWV' && detail.meIsLender) {
      actions.add(
        _actionButton(
          'Verify Checkout via QR Scan',
          () => _scanAndVerify('verify_checkout_handover_pin'),
        ),
      );
      actions.add(
        _actionButton(
          'Verify Checkout via PIN',
          () => _performAction(
            'verify_checkout_handover_pin',
            fields: {'pin': _pinController.text.trim()},
          ),
        ),
      );
    }

    if ((detail.status == 'RDAYAWV' ||
            detail.status == 'RONG' ||
            detail.status == 'RRTDAYAWV') &&
        detail.meIsRenter) {
      actions.add(
        _actionButton(
          'Submit Return Evidence',
          () => _performVideoEvidenceAction(
            action: 'submit_return_borrower_evidence',
            fieldName: 'return_video_url',
            actionLabel: 'submit_return_borrower_evidence',
          ),
        ),
      );
    }

    if (detail.status == 'RRTDAYAWV' && detail.meIsLender) {
      actions.add(
        _actionButton(
          'Confirm Return Evidence',
          () => _performAction('confirm_return_evidence'),
        ),
      );
      actions.add(
        _actionButton(
          'Submit Lender Return Evidence',
          () => _performVideoEvidenceAction(
            action: 'submit_lender_return_evidence',
            fieldName: 'lender_return_video_url',
            actionLabel: 'submit_lender_return_evidence',
          ),
        ),
      );
    }

    if (detail.status == 'RRTDAYAWV' && detail.meIsRenter) {
      actions.add(
        _actionButton(
          'Verify Return via QR Scan',
          () => _scanAndVerify('verify_return_handover_pin'),
        ),
      );
      actions.add(
        _actionButton(
          'Verify Return via PIN',
          () => _performAction(
            'verify_return_handover_pin',
            fields: {'pin': _pinController.text.trim()},
          ),
        ),
      );
    }

    if ((detail.status == 'RONG' || detail.status == 'RRTDAYAWV') &&
        detail.meIsLender &&
        detail.rentalEndDate != null &&
        DateTime.now().isAfter(
          DateTime(
            detail.rentalEndDate!.year,
            detail.rentalEndDate!.month,
            detail.rentalEndDate!.day,
            23,
            59,
            59,
          ),
        )) {
      actions.add(
        _actionButton('Report Missing Return', () async {
          final reason = await _promptForText(
            title: 'Report Missing Return',
            label: 'Reason',
            hint: 'Explain what happened',
          );
          if (reason == null || reason.isEmpty) {
            return;
          }
          await _performAction(
            'report_missing_return',
            fields: {'reason': reason},
          );
        }),
      );
    }

    if (detail.status == 'RRTDPEND' && detail.meIsLender) {
      if (proposalMaxReached) {
        actions.add(
          const Text(
            'Maximum proposal iterations reached (5/5). Raise dispute to continue; dispute handling may incur a fee.',
          ),
        );
      } else {
        actions.add(
          _actionButton('Propose Deposit Return', () async {
            final fields = await _promptForDepositProposal(detail);
            if (fields == null) {
              return;
            }
            await _performAction('propose_deposit_return', fields: fields);
          }),
        );
      }
    }

    if (detail.status == 'RRTDCON' && detail.meIsLender) {
      if (proposalMaxReached) {
        actions.add(
          const Text(
            'Maximum proposal iterations reached (5/5). Raise dispute to continue; dispute handling may incur a fee.',
          ),
        );
      } else {
        actions.add(
          _actionButton('Update Deposit Proposal', () async {
            final fields = await _promptForDepositProposal(detail);
            if (fields == null) {
              return;
            }
            await _performAction('propose_deposit_return', fields: fields);
          }),
        );
      }
      actions.add(
        _actionButton(
          'Secure Dispute Funds',
          () => _performAction('secure_dispute_funds'),
        ),
      );
    }

    if (detail.status == 'RRTDPEND' && detail.meIsRenter) {
      actions.add(
        _actionButton(
          'Agree Deposit Return',
          () => _performAction('agree_deposit_return'),
        ),
      );
      actions.add(
        _actionButton('Contest Deposit Return', () async {
          final notes = await _promptForText(
            title: 'Contest Deposit Proposal',
            label: 'Reason for contest',
            hint: 'Provide details for lender/admin review',
          );
          if (notes == null || notes.isEmpty) {
            return;
          }
          await _performAction(
            'contest_deposit_return',
            fields: {'deposit_resolution_notes': notes},
          );
        }),
      );
    }

    if ((detail.status == 'RRTDPEND' ||
            detail.status == 'RRTDCON' ||
            detail.status == 'DREQ') &&
        (detail.meIsLender || detail.meIsRenter)) {
      actions.add(
        _actionButton('Raise Deposit Dispute To Admin', () async {
          final notes = await _promptForText(
            title: 'Raise Admin Dispute',
            label: 'Dispute details',
            hint: 'Describe why admin review is needed',
          );
          if (notes == null || notes.isEmpty) {
            return;
          }
          await _performAction(
            'raise_deposit_dispute_admin',
            fields: {'deposit_resolution_notes': notes},
          );
        }),
      );
    }

    if ((detail.status == 'AWFB' ||
            detail.status == 'RRTDRET' ||
            detail.status == 'RCOMP' ||
            (detail.status == 'CACK' &&
                detail.meIsRenter &&
                detail.depositResolutionNotes.contains(
                  '[MISSING_RENTAL_VOIDED]',
                ))) &&
        (detail.meIsLender || detail.meIsRenter)) {
      actions.add(
        _actionButton('Submit Feedback', () async {
          final fields = await _promptForFeedback();
          if (fields == null) {
            return;
          }
          await _performAction('submit_feedback', fields: fields);
        }),
      );
    }

    if (canSubmitVideoEvidence) {
      actions.add(
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed: _busy
                  ? null
                  : () => _pickEvidenceVideo(source: ImageSource.gallery),
              icon: const Icon(Icons.video_library_outlined),
              label: const Text('Choose Video'),
            ),
            OutlinedButton.icon(
              onPressed: _busy
                  ? null
                  : () => _pickEvidenceVideo(source: ImageSource.camera),
              icon: const Icon(Icons.videocam_outlined),
              label: const Text('Record Video'),
            ),
            if (_evidenceVideoFile != null)
              TextButton(
                onPressed: _busy
                    ? null
                    : () {
                        setState(() {
                          _evidenceVideoFile = null;
                          _evidenceVideoUrl = null;
                        });
                      },
                child: const Text('Clear'),
              ),
          ],
        ),
      );
      if (_evidenceVideoFile != null) {
        actions.add(
          Text('Selected video: ${_evidenceVideoFile!.path.split('/').last}'),
        );
      }
      if (_evidenceVideoUrl != null && _evidenceVideoUrl!.isNotEmpty) {
        actions.add(const Text('Evidence uploaded and ready for action.'));
      }
    }
    actions.add(
      TextField(
        controller: _pinController,
        decoration: const InputDecoration(
          labelText: 'PIN (optional for PIN actions)',
        ),
      ),
    );

    if (actions.isEmpty) {
      actions.add(
        const Text(
          'No direct actions available right now. Use messages to coordinate the next step.',
        ),
      );
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Actions', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            ...actions,
          ],
        ),
      ),
    );
  }

  Widget _codesCard() {
    final codes = _codes;
    if (codes == null) {
      return const SizedBox.shrink();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Verification Codes',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            if (codes.checkoutPin.isNotEmpty)
              _actionButton(
                'Show Checkout QR/PIN',
                () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => QrDisplayScreen(
                      title: 'Checkout Code',
                      qrPayload: codes.checkoutQrPayload,
                      pin: codes.checkoutPin,
                    ),
                  ),
                ),
              ),
            if (codes.returnPin.isNotEmpty)
              _actionButton(
                'Show Return QR/PIN',
                () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => QrDisplayScreen(
                      title: 'Return Code',
                      qrPayload: codes.returnQrPayload,
                      pin: codes.returnPin,
                    ),
                  ),
                ),
              ),
            if (codes.checkoutPin.isEmpty && codes.returnPin.isEmpty)
              const Text('No active verification code available yet.'),
          ],
        ),
      ),
    );
  }

  Widget _messageComposerCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Send Message',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _messageController,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(labelText: 'Message'),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  onPressed: _busy ? null : _pickImage,
                  icon: const Icon(Icons.image),
                  label: Text('Image (${_images.length})'),
                ),
                OutlinedButton.icon(
                  onPressed: _busy ? null : _pickVideo,
                  icon: const Icon(Icons.videocam),
                  label: Text('Video (${_videos.length})'),
                ),
                OutlinedButton.icon(
                  onPressed: _busy ? null : _recordVideo,
                  icon: const Icon(Icons.videocam_outlined),
                  label: const Text('Record'),
                ),
                FilledButton.icon(
                  onPressed: _busy ? null : _sendMessage,
                  icon: const Icon(Icons.send),
                  label: const Text('Send'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _messagesCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Messages', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            if (_messages.isEmpty)
              const Text('No messages yet.')
            else
              ..._messages.map(
                (m) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(_displaySubject(m.subject)),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(m.description),
                      const SizedBox(height: 6),
                      if (m.attachments.isNotEmpty)
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: m.attachments
                              .map((a) {
                                if (a.imageUrl.isNotEmpty) {
                                  return ClipRRect(
                                    borderRadius: BorderRadius.circular(8),
                                    child: Image.network(
                                      a.imageUrl,
                                      width: 64,
                                      height: 64,
                                      fit: BoxFit.cover,
                                      errorBuilder:
                                          (context, error, stackTrace) =>
                                              Container(
                                                width: 64,
                                                height: 64,
                                                color: const Color(0x11000000),
                                                child: const Icon(
                                                  Icons.broken_image_outlined,
                                                ),
                                              ),
                                    ),
                                  );
                                }
                                if (a.videoUrl.isNotEmpty) {
                                  return Container(
                                    width: 64,
                                    height: 64,
                                    decoration: BoxDecoration(
                                      color: const Color(0x11000000),
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: const Icon(Icons.videocam_outlined),
                                  );
                                }
                                return const SizedBox.shrink();
                              })
                              .toList(growable: false),
                        ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _actionButton(String label, VoidCallback onPressed) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: FilledButton(
        onPressed: _busy ? null : onPressed,
        child: Text(label),
      ),
    );
  }
}
