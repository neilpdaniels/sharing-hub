import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart' as stripe;
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config.dart';
import '../models/account_models.dart';
import '../models/transaction_models.dart';
import '../services/friends_repository.dart';
import '../services/transaction_repository.dart';
import 'qr_display_screen.dart';
import 'qr_scanner_screen.dart';

class TransactionDetailScreen extends StatefulWidget {
  const TransactionDetailScreen({
    super.key,
    required this.transactionReference,
    required this.accessToken,
    required this.repository,
    required this.friendsRepository,
  });

  final String transactionReference;
  final String accessToken;
  final TransactionRepository repository;
  final FriendsRepository friendsRepository;

  @override
  State<TransactionDetailScreen> createState() =>
      _TransactionDetailScreenState();
}

class _TransactionDetailScreenState extends State<TransactionDetailScreen> {
  final _messageController = TextEditingController();
  final _pinController = TextEditingController();
  final _messageFocusNode = FocusNode();
  final List<File> _images = [];
  final List<File> _videos = [];
  File? _evidenceVideoFile;
  String? _evidenceVideoUrl;
  bool _addingCounterparty = false;

  TransactionDetail? _detail;
  TransactionCodes? _codes;
  List<PaymentMethodSummary> _paymentMethods = const [];
  List<TransactionMessage> _messages = const [];
  bool _loading = true;
  bool _busy = false;
  bool _downloadInProgress = false;
  double? _uploadProgress;
  String? _uploadPhase;
  String? _error;
  Timer? _livePollTimer;
  Timer? _countdownTimer;
  String _lastLiveSignature = '';

  @override
  void initState() {
    super.initState();
    _refresh();
    _startLivePolling();
  }

  Future<void> _addCounterpartyAsFriend(TransactionDetail detail) async {
    final counterpartyId = detail.counterparty.id;
    if (counterpartyId <= 0 || _addingCounterparty) {
      return;
    }

    setState(() {
      _addingCounterparty = true;
      _error = null;
    });

    try {
      final message = await widget.friendsRepository.sendFriendRequest(
        accessToken: widget.accessToken,
        userId: counterpartyId,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
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
          _addingCounterparty = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _livePollTimer?.cancel();
    _countdownTimer?.cancel();
    _messageController.dispose();
    _pinController.dispose();
    _messageFocusNode.dispose();
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

  void _startCountdownTimer() {
    _countdownTimer?.cancel();
    if (_detail?.status != 'RAGR' || _detail?.renterAgreedAt != null) {
      return;
    }
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) {
        setState(() {
          // Trigger rebuild to update countdown display
        });
      }
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
      detail.evidenceItems.map((e) => '${e.id}:${e.previewStatus}').join(','),
      messages
          .expand((m) => m.attachments)
          .map((a) => '${a.id}:${a.previewStatus}')
          .join(','),
      detail.status,
      detail.workflowPayload.message,
      detail.workflowPayload.allowedActions.join(','),
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
      final paymentMethods = await widget.repository.fetchPaymentMethods(
        accessToken: widget.accessToken,
      );
      if (!mounted) {
        return;
      }
      final canSubmitVideoEvidence = detail.canSubmitVideoEvidence;
      setState(() {
        _detail = detail;
        _messages = messages;
        _codes = codes;
        _paymentMethods = paymentMethods;
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
      _startCountdownTimer();
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
      final paymentMethods = await widget.repository.fetchPaymentMethods(
        accessToken: widget.accessToken,
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
        _paymentMethods = paymentMethods;
        _lastLiveSignature = signature;
        if (!canSubmitVideoEvidence) {
          _evidenceVideoFile = null;
          _evidenceVideoUrl = null;
        }
      });
      _startCountdownTimer();
    } catch (_) {
      // Keep polling quiet; user can still manually refresh via actions.
    }
  }

  void _showActionConfirmation(
    Map<String, dynamic> result, {
    String fallback = 'Booking updated.',
  }) {
    if (!mounted) return;
    final message = (result['message'] as String?)?.trim();
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message?.isNotEmpty == true ? message! : fallback),
          duration: const Duration(seconds: 8),
          showCloseIcon: true,
        ),
      );
  }

  void _updateUploadProgress(int sentBytes, int totalBytes) {
    if (!mounted) return;
    setState(() {
      _uploadPhase = 'Uploading video…';
      _uploadProgress = totalBytes > 0
          ? (sentBytes / totalBytes).clamp(0.0, 1.0)
          : null;
    });
  }

  Widget _videoUploadProgress() {
    final progress = _uploadProgress;
    final label = progress == null
        ? (_uploadPhase ?? 'Preparing video…')
        : '${_uploadPhase ?? 'Uploading video…'} ${(progress * 100).round()}%';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 10),
            LinearProgressIndicator(value: progress),
            const SizedBox(height: 8),
            Text(
              progress == null
                  ? 'Compressing the recording on your device before upload.'
                  : 'Keep the app open until the upload completes.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
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
      final result = await widget.repository.performAction(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
        action: action,
        fields: fields,
      );
      if (action == 'verify_checkout_handover_pin' ||
          action == 'verify_return_handover_pin') {
        _pinController.clear();
      }
      await _refresh();
      _showActionConfirmation(result);
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
      _uploadProgress = null;
      _uploadPhase = 'Preparing video…';
    });

    try {
      final selectedFile = _evidenceVideoFile;
      final videoUrl = _evidenceVideoUrl ?? '';
      final capturedAt = DateTime.now().toUtc().toIso8601String();
      final fields = <String, dynamic>{'captured_at': capturedAt};
      if (videoUrl.isNotEmpty) {
        fields[fieldName] = videoUrl;
      }

      final Map<String, dynamic> result;
      if (selectedFile != null) {
        result = await widget.repository.performActionWithFiles(
          accessToken: widget.accessToken,
          transactionReference: widget.transactionReference,
          action: action,
          fields: fields,
          videoFiles: [selectedFile],
          onUploadProgress: _updateUploadProgress,
        );
      } else if (videoUrl.isNotEmpty) {
        result = await widget.repository.performAction(
          accessToken: widget.accessToken,
          transactionReference: widget.transactionReference,
          action: action,
          fields: fields,
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
      _showActionConfirmation(
        result,
        fallback: 'Video evidence submitted successfully.',
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
          _uploadProgress = null;
          _uploadPhase = null;
        });
      }
    }
  }

  Future<bool> _showRentalTermsConfirmation() async {
    final agreed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Confirm rental agreement'),
          content: const Text(
            'Please review the rental terms shown below before confirming. By continuing, you agree to complete the handover, follow the agreed rental period, care for the item, and use the transaction flow to report any issue.',
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

  Widget _rentalTermsCard(TransactionDetail detail) {
    final rentalEnd = _friendlyDate(detail.rentalEndDate);
    final deposit = '£${detail.deposit.toStringAsFixed(2)}';
    final terms = [
      (
        'Condition on collection',
        'Inspect the item at collection and raise any existing damage or faults through the transaction before accepting it.',
      ),
      (
        'Use and care',
        'Use the item only for its intended purpose and take reasonable care of it throughout the rental.',
      ),
      (
        'Normal wear and tear',
        'Minor surface scratches, dust marks, fading, and other small cosmetic changes from ordinary use are accepted.',
      ),
      (
        'Damage beyond normal wear',
        'You are responsible for damage caused by misuse, neglect, accident, or any damage beyond normal wear and tear.',
      ),
      (
        'Return condition',
        'Return the item in the same condition as received, allowing for normal wear and tear.',
      ),
      (
        'Return date and location',
        'Return the item on or before $rentalEnd, to the location agreed with the lender. Late returns may incur additional charges.',
      ),
      (
        'Deposit',
        'A deposit of $deposit may be held during the rental as security against damage, loss, theft, or other amounts allowed by the rental agreement.',
      ),
      (
        'Deposit return',
        'The deposit is returned after the item is checked. If damage or another valid claim is identified, some or all of the deposit may be retained while the matter is reviewed.',
      ),
      (
        'Loss, theft, and insurance',
        'The borrower is responsible for loss or theft during the rental. Appropriate insurance is recommended.',
      ),
      (
        'Disputes',
        'Condition, handover, missing rental, missing return, and deposit disputes are handled first through the transaction flow and may be escalated for review.',
      ),
      (
        'Platform responsibilities',
        'Rentalution provides the transaction workflow, messaging, evidence record, and payment/deposit handling. The lender and borrower remain responsible for the agreed rental and handover.',
      ),
    ];

    return Card(
      child: ExpansionTile(
        initiallyExpanded: false,
        leading: const Icon(Icons.gavel_outlined),
        title: const Text('Rental terms and conditions'),
        subtitle: const Text('Review these terms before confirming'),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'These terms apply to this rental. By confirming, both parties agree to follow them and the booking workflow.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 12),
                ...terms.map(
                  (term) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: RichText(
                      text: TextSpan(
                        style: Theme.of(context).textTheme.bodyMedium,
                        children: [
                          TextSpan(
                            text: '${term.$1}: ',
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                          TextSpan(text: term.$2),
                        ],
                      ),
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Theme.of(
                      context,
                    ).colorScheme.primary.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Text(
                    'Important: confirming this rental creates a binding agreement. Keep all communication and evidence in the booking so any issue can be reviewed fairly.',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  DateTime? _contractDeadline(TransactionDetail detail) {
    return detail.workflowPayload.contractDeadline;
  }

  String _formatDuration(Duration duration) {
    final safe = duration.isNegative ? Duration.zero : duration;
    final hours = safe.inHours;
    final minutes = safe.inMinutes.remainder(60);
    final seconds = safe.inSeconds.remainder(60);
    return '${hours.toString().padLeft(2, '0')}:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }

  Duration? _contractTimeRemaining(TransactionDetail detail) {
    if (detail.renterAgreedAt != null) {
      return null;
    }
    final deadline = _contractDeadline(detail);
    if (deadline == null) {
      return null;
    }
    final remaining = deadline.difference(DateTime.now());
    return remaining.isNegative ? Duration.zero : remaining;
  }

  Duration? _disputeStatementTimeRemaining(TransactionDetail detail) {
    final deadline = detail.disputeFinalStatementDeadline;
    if (deadline == null) {
      return null;
    }
    final remaining = deadline.difference(DateTime.now());
    return remaining.isNegative ? Duration.zero : remaining;
  }

  void _scrollToMessages() {
    _messageFocusNode.requestFocus();
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
      _uploadProgress = null;
      _uploadPhase = _videos.isEmpty ? null : 'Preparing video…';
    });

    try {
      await widget.repository.sendMessageWithAttachments(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
        messageBody: body,
        imageFiles: _images,
        videoFiles: _videos,
        onUploadProgress: _videos.isEmpty ? null : _updateUploadProgress,
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
          _uploadProgress = null;
          _uploadPhase = null;
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
      return 'You are lending';
    }
    if (detail.meIsRenter) {
      return 'You are borrowing';
    }
    return 'Participant';
  }

  String _opposingPartyLabel(TransactionDetail detail) {
    if (detail.meIsLender) {
      return 'Borrower';
    }
    if (detail.meIsRenter) {
      return 'Lender';
    }
    return 'Counterparty';
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

  String _evidenceStateText({
    required TransactionDetail detail,
    required bool isCheckout,
  }) {
    final status = detail.status.trim().toUpperCase();
    final hasEvidence = isCheckout
        ? detail.checkoutConditionVideoUrl.isNotEmpty
        : detail.returnConditionVideoUrl.isNotEmpty;
    final isVerified = isCheckout
        ? detail.checkoutHandoverVerifiedAt != null
        : detail.returnHandoverVerifiedAt != null;

    if (isVerified) {
      return 'verified';
    }

    if (isCheckout) {
      if (status == 'RENQ') {
        return 'not yet due';
      }
      if (status == 'RAGR' || status == 'RDAYAWV' || status == 'RONG') {
        return hasEvidence ? 'captured' : 'pending';
      }
      return hasEvidence ? 'verified' : 'pending';
    }

    if (status == 'RENQ' ||
        status == 'RAGR' ||
        status == 'RDAYAWV' ||
        status == 'RONG') {
      return 'not yet due';
    }
    if (status == 'RRTDAYAWV' || status == 'RRTDPEND' || status == 'RRTDCON') {
      return hasEvidence ? 'captured' : 'pending';
    }
    return hasEvidence ? 'verified' : 'pending';
  }

  bool _hasEvidenceForStage(
    TransactionDetail detail, {
    required bool checkout,
  }) {
    final hasVideo = checkout
        ? detail.checkoutConditionVideoUrl.trim().isNotEmpty ||
              detail.checkoutBorrowerVideoUrl.trim().isNotEmpty
        : detail.returnConditionVideoUrl.trim().isNotEmpty ||
              detail.returnBorrowerVideoUrl.trim().isNotEmpty ||
              detail.returnLenderVideoUrl.trim().isNotEmpty;
    if (hasVideo) {
      return true;
    }
    final prefix = checkout ? 'checkout' : 'return';
    return detail.evidenceItems.any(
      (item) => item.evidenceStage.trim().toLowerCase().startsWith(prefix),
    );
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
    final day = value.day;
    final month = months[value.month - 1];
    final suffix = (day >= 11 && day <= 13)
        ? 'th'
        : day % 10 == 1
        ? 'st'
        : day % 10 == 2
        ? 'nd'
        : day % 10 == 3
        ? 'rd'
        : 'th';
    final year = (value.year % 100).toString().padLeft(2, '0');
    return '$day$suffix $month $year';
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
    return detail.deposit > 0 &&
        (detail.status == 'RRTDPEND' ||
            detail.status == 'RRTDCON' ||
            detail.status == 'DREQ');
  }

  int _depositProposalIterationCount(TransactionDetail detail) {
    final count = detail.depositProposalIterationCount;
    return count < 0 ? 0 : count;
  }

  int _depositProposalIterationLimit(TransactionDetail detail) {
    final limit = detail.depositProposalIterationLimit;
    return limit < 1 ? 5 : limit;
  }

  Widget _partyDetailsTile(TransactionDetail detail) {
    final counterparty = detail.counterparty;
    final theme = Theme.of(context);
    final avatarUrl = counterparty.avatarUrl.trim();
    final address = counterparty.addressDisplay.trim().isNotEmpty
        ? counterparty.addressDisplay.trim()
        : [
            counterparty.addressLine1,
            counterparty.addressLine2,
            [
              counterparty.town,
              counterparty.county,
            ].where((part) => part.trim().isNotEmpty).join(', '),
            counterparty.postcode,
          ].where((part) => part.trim().isNotEmpty).join('\n');

    return Card(
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        initiallyExpanded: false,
        leading: CircleAvatar(
          radius: 22,
          backgroundColor: theme.colorScheme.surfaceContainerHighest,
          backgroundImage: avatarUrl.isNotEmpty
              ? NetworkImage(avatarUrl)
              : null,
          child: avatarUrl.isEmpty
              ? Text(
                  counterparty.displayName.isNotEmpty
                      ? counterparty.displayName[0].toUpperCase()
                      : '?',
                )
              : null,
        ),
        title: Text(
          _opposingPartyLabel(detail),
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w800,
          ),
        ),
        subtitle: Text(
          counterparty.displayName.isNotEmpty
              ? counterparty.displayName
              : 'View contact details',
        ),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (counterparty.username.isNotEmpty)
                  Text('@${counterparty.username}'),
                if (counterparty.mobileNumber.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(counterparty.mobileNumber),
                ],
                if (address.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surfaceContainerHighest
                          .withOpacity(0.55),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Text(address, style: theme.textTheme.bodyMedium),
                  ),
                ],
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _summaryChip(
                      label: 'Rating',
                      value: counterparty.rating > 0
                          ? '${counterparty.rating.toStringAsFixed(1)} / 5'
                          : 'N/A',
                      icon: Icons.star_outline,
                      accent: const Color(0xFFB45309),
                    ),
                    _summaryChip(
                      label: 'Completed',
                      value: counterparty.successfulTxns.toString(),
                      icon: Icons.check_circle_outline,
                      accent: const Color(0xFF2E7D6B),
                    ),
                    _summaryChip(
                      label: 'Address',
                      value: counterparty.addressVerified
                          ? 'Verified'
                          : 'Unverified',
                      icon: Icons.verified_outlined,
                      accent: const Color(0xFF7C3AED),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton.tonalIcon(
                    onPressed: _addingCounterparty
                        ? null
                        : () => _addCounterpartyAsFriend(detail),
                    icon: _addingCounterparty
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.person_add_alt_1_outlined),
                    label: const Text('Add as friend'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
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

  Widget _summaryTile({
    required String label,
    required String value,
    required IconData icon,
    Color? accent,
    int flex = 1,
  }) {
    final theme = Theme.of(context);
    final color = accent ?? theme.colorScheme.primary;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.14)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: theme.textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: theme.colorScheme.onSurface,
                  ),
                  maxLines: 4,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _summaryChip({
    required String label,
    required String value,
    required IconData icon,
    Color? accent,
  }) {
    final theme = Theme.of(context);
    final color = accent ?? theme.colorScheme.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.16)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              '$label: $value',
              style: theme.textTheme.labelMedium?.copyWith(
                fontWeight: FontWeight.w700,
                color: theme.colorScheme.onSurfaceVariant,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
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
    try {
      final value = await showDialog<String>(
        context: context,
        barrierDismissible: true,
        builder: (dialogContext) {
          return AlertDialog(
            title: Text(title),
            content: TextField(
              controller: controller,
              autofocus: false,
              minLines: 2,
              maxLines: 4,
              decoration: InputDecoration(labelText: label, hintText: hint),
            ),
            actions: [
              TextButton(
                onPressed: () {
                  FocusScope.of(dialogContext).unfocus();
                  if (Navigator.of(dialogContext).canPop()) {
                    Navigator.of(dialogContext).pop();
                  }
                },
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () {
                  final text = controller.text.trim();
                  if (required && text.isEmpty) {
                    return;
                  }
                  FocusScope.of(dialogContext).unfocus();
                  final navigator = Navigator.of(dialogContext);
                  if (!navigator.canPop()) {
                    return;
                  }
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (navigator.canPop()) {
                      navigator.pop(text);
                    }
                  });
                },
                child: const Text('Continue'),
              ),
            ],
          );
        },
      );
      return value;
    } finally {
      controller.dispose();
    }
  }

  Future<Map<String, dynamic>?> _promptForDepositProposal(
    TransactionDetail detail,
  ) async {
    final initialAmount = detail.deposit;
    double returnAmount = initialAmount;
    final notesController = TextEditingController(
      text: detail.depositResolutionNotes,
    );

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setStateDialog) {
            final reasonRequired = returnAmount < detail.deposit - 0.0001;
            final returnPercent = detail.deposit <= 0
                ? 100
                : ((returnAmount / detail.deposit) * 100).round().clamp(0, 100);

            return AlertDialog(
              title: const Text('Propose Deposit Return'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Return to borrower',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '£${returnAmount.toStringAsFixed(2)} of £${detail.deposit.toStringAsFixed(2)} (${returnPercent}%)',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Slider(
                      value: returnAmount.clamp(0, detail.deposit),
                      min: 0,
                      max: detail.deposit <= 0 ? 0 : detail.deposit,
                      divisions: detail.deposit <= 0
                          ? null
                          : (detail.deposit * 100).round().clamp(1, 10000),
                      label: '£${returnAmount.toStringAsFixed(2)}',
                      onChanged: detail.deposit <= 0
                          ? null
                          : (value) {
                              setStateDialog(() {
                                returnAmount = value;
                              });
                            },
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: notesController,
                      minLines: 2,
                      maxLines: 4,
                      decoration: InputDecoration(
                        labelText: reasonRequired
                            ? 'Reason for partial return'
                            : 'Notes (optional)',
                        hintText: reasonRequired
                            ? 'Explain why you are returning less than 100%'
                            : 'Optional notes for the borrower',
                      ),
                    ),
                    if (reasonRequired) ...[
                      const SizedBox(height: 8),
                      Text(
                        'A reason is required if you return less than the full deposit.',
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                          fontWeight: FontWeight.w600,
                        ),
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
                    if (detail.deposit > 0 && returnAmount < detail.deposit) {
                      final notes = notesController.text.trim();
                      if (notes.isEmpty) {
                        return;
                      }
                    }
                    Navigator.pop(dialogContext, {
                      'deposit_proposed_return_amount': returnAmount,
                      'deposit_resolution_notes': notesController.text.trim(),
                    });
                  },
                  child: const Text('Send Proposal'),
                ),
              ],
            );
          },
        );
      },
    );

    notesController.dispose();
    return result;
  }

  Future<Map<String, dynamic>?> _promptForFeedback() async {
    final comment = TextEditingController();
    var communicationRating = 0;
    var deliveryReturnRating = 0;
    var overallRating = 0;

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setStateDialog) {
            return AlertDialog(
              title: const Text('Submit Feedback'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _buildStarRatingField(
                      label: 'Comms',
                      value: communicationRating,
                      onChanged: (value) {
                        setStateDialog(() {
                          communicationRating = value;
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    _buildStarRatingField(
                      label: 'Delivery / return',
                      value: deliveryReturnRating,
                      onChanged: (value) {
                        setStateDialog(() {
                          deliveryReturnRating = value;
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    _buildStarRatingField(
                      label: 'Overall',
                      value: overallRating,
                      onChanged: (value) {
                        setStateDialog(() {
                          overallRating = value;
                        });
                      },
                    ),
                    const SizedBox(height: 12),
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
                  onPressed:
                      communicationRating == 0 ||
                          deliveryReturnRating == 0 ||
                          overallRating == 0
                      ? null
                      : () {
                          Navigator.pop(dialogContext, {
                            'communication_rating': communicationRating,
                            'delivery_return_rating': deliveryReturnRating,
                            'overall_rating': overallRating,
                            'feedback_comment': comment.text.trim(),
                          });
                        },
                  child: const Text('Submit'),
                ),
              ],
            );
          },
        );
      },
    );

    comment.dispose();
    return result;
  }

  Widget _buildStarRatingField({
    required String label,
    required int value,
    required ValueChanged<int> onChanged,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label),
        const SizedBox(height: 4),
        Row(
          mainAxisAlignment: MainAxisAlignment.start,
          children: List.generate(5, (index) {
            final rating = index + 1;
            final selected = rating <= value;
            return IconButton(
              visualDensity: VisualDensity.compact,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
              onPressed: () => onChanged(rating),
              icon: Icon(
                selected ? Icons.star : Icons.star_border,
                color: Colors.amber,
              ),
              tooltip: '$rating out of 5',
            );
          }),
        ),
      ],
    );
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
      if (setupIntentId.isEmpty || paymentMethodId.isEmpty) {
        throw Exception('Stripe did not return a saved payment method.');
      }

      await widget.repository.performAction(
        accessToken: widget.accessToken,
        transactionReference: widget.transactionReference,
        action: 'confirm_stripe_card',
        fields: {
          'payment_method_id': paymentMethodId,
          'setup_intent_id': setupIntentId,
        },
      );

      await _refresh();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Deposit card setup submitted.')),
      );
    } on stripe.StripeException catch (e) {
      if (e.error.code == stripe.FailureCode.Canceled) {
        return;
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString();
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

  Widget _workflowCard(TransactionDetail detail) {
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
                ...detail.workflowTimeline.map((entry) {
                  final step = entry.step;
                  final active = entry.current;
                  final done = entry.done;

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
                              entry.label,
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
        if (detail.workflowStage > 6) ...[
          const SizedBox(height: 16),
          _checkoutCheckInSection(detail),
        ],
      ],
    );
  }

  String _cancellationSummary(TransactionDetail detail) =>
      detail.depositResolutionNotes.contains('[NO_COLLECTION_CONFIRMED]')
      ? 'This booking was cancelled because collection did not happen.'
      : 'This booking has been cancelled.';

  Widget _currentWorkflowCard(TransactionDetail detail) {
    final currentStep = detail.workflowTimeline
        .where((entry) => entry.current)
        .firstOrNull;
    final cancelled = detail.status == 'CACK';
    final label = cancelled
        ? 'Cancelled'
        : currentStep?.label.trim().isNotEmpty == true
        ? currentStep!.label
        : detail.workflowStageLabel;
    final helpText = cancelled
        ? _cancellationSummary(detail)
        : currentStep?.helpText.trim() ?? '';

    return Card(
      color: Theme.of(context).colorScheme.primary.withOpacity(0.08),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              Icons.flag_outlined,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    cancelled ? 'Booking status' : 'Current step',
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: Theme.of(context).colorScheme.primary,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    label.isNotEmpty
                        ? label
                        : 'Workflow step ${detail.workflowStage}',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  if (helpText.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      helpText,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _watchVideo(String url) async {
    try {
      final uri = Uri.tryParse(url.trim());
      if (uri == null ||
          !uri.hasAuthority ||
          (uri.scheme != 'https' && uri.scheme != 'http')) {
        throw const FormatException('Invalid video URL');
      }
      if (await launchUrl(uri, mode: LaunchMode.externalApplication)) return;
    } catch (_) {
      // Keep storage/plugin errors out of the user-facing message.
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Unable to open this video. Please try again or view it on the website.',
        ),
      ),
    );
  }

  Future<void> _downloadVideo(String url) async {
    final uri = Uri.tryParse(url.trim());
    if (uri == null ||
        !uri.hasAuthority ||
        (uri.scheme != 'https' && uri.scheme != 'http')) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unable to download this video.')),
        );
      }
      return;
    }

    setState(() => _downloadInProgress = true);
    try {
      final response = await http.get(uri);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw HttpException('Download failed with ${response.statusCode}');
      }
      final directory = await getApplicationDocumentsDirectory();
      final filename =
          'rentalution-evidence-${DateTime.now().millisecondsSinceEpoch}.mp4';
      await File(
        '${directory.path}/$filename',
      ).writeAsBytes(response.bodyBytes, flush: true);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Full-quality video downloaded to the app files.'),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Unable to download this video. Please try again.'),
        ),
      );
    } finally {
      if (mounted) setState(() => _downloadInProgress = false);
    }
  }

  Widget _checkoutCheckInSection(TransactionDetail detail) {
    final current = detail.workflowStage;
    final isCheckout = current == 5;
    final title = isCheckout
        ? 'Checkout Handover Evidence'
        : 'Return Handover Evidence';
    final stagePrefix = isCheckout ? 'checkout' : 'return';
    final evidenceItems = _evidenceItemsForStage(detail, stagePrefix);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              'Saved proof for this stage is shown here with the capture time.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Saved evidence',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            if (evidenceItems.isEmpty)
              Text(
                'No evidence has been uploaded yet.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              )
            else
              ...evidenceItems.map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Theme.of(
                        context,
                      ).colorScheme.surfaceContainerHighest.withOpacity(0.7),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.verified_outlined),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _evidenceStageLabel(item.evidenceStage),
                                style: Theme.of(context).textTheme.bodyMedium
                                    ?.copyWith(fontWeight: FontWeight.w600),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Captured ${_formatEvidenceTimestamp(item.capturedAt ?? item.uploadedAt)}'
                                '${item.captureDevice.trim().isNotEmpty ? ' · ${item.captureDevice}' : ''}',
                                style: Theme.of(context).textTheme.bodySmall
                                    ?.copyWith(
                                      color: Theme.of(
                                        context,
                                      ).colorScheme.onSurfaceVariant,
                                    ),
                              ),
                              if (item.previewUrl.isNotEmpty)
                                TextButton.icon(
                                  onPressed: () => _watchVideo(item.previewUrl),
                                  icon: const Icon(Icons.play_circle_outline),
                                  label: const Text('Watch preview'),
                                )
                              else if (item.externalVideoUrl.isNotEmpty)
                                TextButton(
                                  onPressed: () =>
                                      _watchVideo(item.externalVideoUrl),
                                  child: const Text('Open external video'),
                                )
                              else
                                Text(
                                  item.previewStatus == 'failed'
                                      ? 'Preview unavailable. You can still download the uploaded video.'
                                      : 'Preparing smaller preview…',
                                ),
                              if (item.downloadUrl.isNotEmpty)
                                TextButton.icon(
                                  onPressed: _downloadInProgress
                                      ? null
                                      : () => _downloadVideo(item.downloadUrl),
                                  icon: const Icon(Icons.download_outlined),
                                  label: const Text(
                                    'Download full uploaded quality',
                                  ),
                                ),
                            ],
                          ),
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

  String? _evidenceSubmissionAction(TransactionDetail detail) {
    final status = detail.status.trim().toUpperCase();
    if (detail.meIsLender && status == 'RAGR') {
      return 'initiate_rental';
    }
    if (detail.meIsRenter && status == 'RDAYAWV') {
      return 'submit_checkout_borrower_evidence';
    }
    if (detail.meIsRenter && (status == 'RONG' || status == 'RRTDAYAWV')) {
      return 'submit_return_borrower_evidence';
    }
    if (detail.meIsLender && status == 'RRTDAYAWV') {
      return 'submit_lender_return_evidence';
    }
    return null;
  }

  String _evidenceSubmissionFieldName(TransactionDetail detail) {
    final status = detail.status.trim().toUpperCase();
    if (detail.meIsLender && status == 'RAGR') {
      return 'checkout_video_url';
    }
    if (detail.meIsRenter && status == 'RDAYAWV') {
      return 'checkout_borrower_video_url';
    }
    if (detail.meIsRenter && (status == 'RONG' || status == 'RRTDAYAWV')) {
      return 'return_video_url';
    }
    return 'lender_return_video_url';
  }

  String _evidenceSubmissionLabel(TransactionDetail detail) {
    final status = detail.status.trim().toUpperCase();
    if (detail.meIsLender && status == 'RAGR') {
      return 'initiate rental';
    }
    if (detail.meIsRenter && status == 'RDAYAWV') {
      return 'checkout borrower evidence';
    }
    return detail.meIsRenter ? 'return evidence' : 'lender return evidence';
  }

  List<TransactionEvidenceItem> _evidenceItemsForStage(
    TransactionDetail detail,
    String stagePrefix,
  ) {
    return detail.evidenceItems
        .where(
          (item) =>
              item.evidenceStage.trim().toLowerCase().startsWith(stagePrefix),
        )
        .toList(growable: false);
  }

  String _evidenceStageLabel(String stage) {
    switch (stage.trim().toLowerCase()) {
      case 'checkout_lender':
        return 'Checkout evidence by lender';
      case 'checkout_borrower':
        return 'Checkout counter-evidence by renter';
      case 'return_borrower':
        return 'Return evidence by renter';
      case 'return_lender':
        return 'Return counter-evidence by lender';
      default:
        return stage.replaceAll('_', ' ');
    }
  }

  String _formatEvidenceTimestamp(DateTime? value) {
    if (value == null) {
      return 'unknown time';
    }
    final local = value.toLocal();
    final month = local.month.toString().padLeft(2, '0');
    final day = local.day.toString().padLeft(2, '0');
    final hour = local.hour.toString().padLeft(2, '0');
    final minute = local.minute.toString().padLeft(2, '0');
    return '${local.year}-$month-$day $hour:$minute';
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
                  if (detail.workflowPayload.overdueKind.isNotEmpty)
                    Card(
                      color: Theme.of(context).brightness == Brightness.dark
                          ? const Color(0xFF3D3218)
                          : Colors.amber.shade100,
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Booking needs attention',
                              style: TextStyle(fontWeight: FontWeight.bold),
                            ),
                            Text(detail.workflowPayload.message),
                            if (detail.workflowPayload.allowedActions.contains(
                              'confirm_no_collection',
                            ))
                              _actionButton(
                                'Confirm collection did not happen',
                                () => _performAction('confirm_no_collection'),
                              ),
                            if (detail.workflowPayload.allowedActions.contains(
                              'report_missing_return',
                            ))
                              _actionButton(
                                'No, the item was not returned — start non-return review',
                                () => _performAction('report_missing_return'),
                              ),
                          ],
                        ),
                      ),
                    ),
                  if (_uploadPhase != null) ...[
                    const SizedBox(height: 16),
                    _videoUploadProgress(),
                  ],
                  _currentWorkflowCard(detail),
                  if ((detail.workflowStage == 5 && detail.meIsLender) ||
                      detail.workflowStage == 6) ...[
                    const SizedBox(height: 16),
                    _checkoutCheckInSection(detail),
                  ],
                  const SizedBox(height: 16),
                  _actionsCard(detail),
                  const SizedBox(height: 16),
                  _messageComposerCard(),
                  const SizedBox(height: 16),
                  _summaryCard(detail),
                  if (_showDepositProposalProgress(detail)) ...[
                    const SizedBox(height: 16),
                    _depositProposalProgressCard(detail),
                  ],
                  const SizedBox(height: 16),
                  if (detail.status != 'CACK') _workflowCard(detail),
                  const SizedBox(height: 16),
                  _rentalTermsCard(detail),
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
    final theme = Theme.of(context);
    final contractRemaining = _contractTimeRemaining(detail);
    final hasCheckoutEvidence = _hasEvidenceForStage(detail, checkout: true);
    final hasReturnEvidence = _hasEvidenceForStage(detail, checkout: false);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        detail.itemName.isNotEmpty
                            ? detail.itemName
                            : 'Rental booking',
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          _summaryChip(
                            label: 'Status',
                            value: detail.status == 'CACK'
                                ? 'Cancelled'
                                : detail.statusDisplay.trim().isNotEmpty
                                ? detail.statusDisplay
                                : _transactionStatusText(detail.status),
                            icon: Icons.schedule_outlined,
                            accent: const Color(0xFF2E7D6B),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                if (visualUrls.isNotEmpty) ...[
                  const SizedBox(width: 12),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: SizedBox(
                      width: 84,
                      height: 84,
                      child: Image.network(
                        visualUrls.first,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) => Container(
                          color: theme.colorScheme.surfaceContainerHighest,
                          child: Icon(
                            Icons.inventory_2_outlined,
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 16),
            _partyDetailsTile(detail),
            const SizedBox(height: 12),
            if (contractRemaining != null)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: contractRemaining == Duration.zero
                      ? Colors.red.withOpacity(0.08)
                      : const Color(0xFF2E7D6B).withOpacity(0.08),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: contractRemaining == Duration.zero
                        ? Colors.red.withOpacity(0.18)
                        : const Color(0xFF2E7D6B).withOpacity(0.18),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      contractRemaining == Duration.zero
                          ? Icons.error_outline
                          : Icons.hourglass_bottom,
                      size: 18,
                      color: contractRemaining == Duration.zero
                          ? Colors.red.shade700
                          : const Color(0xFF2E7D6B),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        contractRemaining == Duration.zero
                            ? 'Confirmation window expired'
                            : 'Confirmation window ${_formatDuration(contractRemaining)} remaining',
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: contractRemaining == Duration.zero
                              ? Colors.red.shade700
                              : const Color(0xFF2E7D6B),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            const SizedBox(height: 16),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisSpacing: 10,
              mainAxisSpacing: 10,
              mainAxisExtent: 128,
              children: [
                _summaryTile(
                  label: 'Dates',
                  value:
                      '${_friendlyDate(detail.rentalStartDate)}'
                      ' - ${_friendlyDate(detail.rentalEndDate)}',
                  icon: Icons.event_available_outlined,
                  accent: const Color(0xFF0F766E),
                ),
                _summaryTile(
                  label: 'Rental days',
                  value: rentalDays != null ? '$rentalDays' : 'Pending',
                  icon: Icons.date_range_outlined,
                  accent: const Color(0xFF1D4ED8),
                ),
              ],
            ),
            const SizedBox(height: 12),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisSpacing: 10,
              mainAxisSpacing: 10,
              mainAxisExtent: 176,
              children: [
                _summaryTile(
                  label: 'Price / day',
                  value: [
                    '£${detail.price.toStringAsFixed(2)} / day',
                    'Total ${estimatedRentalTotal != null ? '£${estimatedRentalTotal.toStringAsFixed(2)}' : 'Pending'}',
                  ].join('\n'),
                  icon: Icons.sell_outlined,
                  accent: const Color(0xFFB45309),
                ),
                _summaryTile(
                  label: 'Payment',
                  value: _paymentStatusText(detail.paymentStatus),
                  icon: Icons.payments_outlined,
                  accent: const Color(0xFF2E7D6B),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _summaryTile(
              label: 'Deposit',
              value:
                  '£${detail.deposit.toStringAsFixed(2)}\n${_depositStatusText(detail.depositStatus)}',
              icon: Icons.account_balance_wallet_outlined,
              accent: const Color(0xFFB45309),
            ),
            if (hasCheckoutEvidence || hasReturnEvidence) ...[
              const SizedBox(height: 12),
              _summaryTile(
                label: 'Evidence',
                value: [
                  if (hasCheckoutEvidence)
                    'Checkout: ${_evidenceStateText(detail: detail, isCheckout: true)}',
                  if (hasReturnEvidence)
                    'Return: ${_evidenceStateText(detail: detail, isCheckout: false)}',
                ].join('\n'),
                icon: Icons.photo_library_outlined,
                accent: const Color(0xFF5B5FC7),
              ),
            ],
            const SizedBox(height: 12),
            if (detail.depositProposedByLenderAt != null) ...[
              const SizedBox(height: 12),
              _summaryTile(
                label: 'Current deposit proposal',
                value:
                    '£${detail.depositProposedReturnAmount.toStringAsFixed(2)}',
                icon: Icons.price_change_outlined,
                accent: const Color(0xFFB45309),
              ),
            ],
            if (detail.depositResolutionNotes.trim().isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainerHighest.withOpacity(
                    0.55,
                  ),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(
                  detail.depositResolutionNotes,
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _actionsCard(TransactionDetail detail) {
    final actions = <Widget>[];
    final codes = _codes;
    bool can(String action) =>
        detail.workflowPayload.allowedActions.contains(action);
    final contractRemaining = _contractTimeRemaining(detail);
    final disputeRemaining = _disputeStatementTimeRemaining(detail);
    final needsCardSetup =
        can('add_deposit_card') &&
        (detail.depositCardSetupStatus != 'READY' ||
            detail.depositTestHoldStatus != 'SUCCESS');
    final nativeStripeConfigured = AppConfig.stripePublishableKey
        .trim()
        .isNotEmpty;
    final hasSavedPaymentMethods = _paymentMethods.isNotEmpty;
    final proposalIterationCount = _depositProposalIterationCount(detail);
    final proposalIterationLimit = _depositProposalIterationLimit(detail);
    final proposalMaxReached = proposalIterationCount >= proposalIterationLimit;

    if (detail.status == 'RAGR' &&
        detail.renterAgreedAt == null &&
        contractRemaining != null) {
      actions.add(
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: contractRemaining == Duration.zero
                ? Colors.red.withOpacity(0.1)
                : Colors.amber.withOpacity(0.1),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: contractRemaining == Duration.zero
                  ? Colors.red.withOpacity(0.3)
                  : Colors.amber.withOpacity(0.3),
            ),
          ),
          child: Text(
            contractRemaining == Duration.zero
                ? 'Contract confirmation window has expired.'
                : 'Contract confirmation window remaining: ${_formatDuration(contractRemaining)}',
            style: TextStyle(
              fontWeight: FontWeight.w600,
              color: contractRemaining == Duration.zero
                  ? Colors.red[700]
                  : Colors.orange[700],
            ),
          ),
        ),
      );
      actions.add(const SizedBox(height: 8));
    }

    if (detail.activeDisputeCase != null &&
        detail.disputeFinalStatementOpen &&
        disputeRemaining != null) {
      actions.add(
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: disputeRemaining == Duration.zero
                ? Colors.red.withOpacity(0.1)
                : const Color(0xFF2E7D6B).withOpacity(0.08),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: disputeRemaining == Duration.zero
                  ? Colors.red.withOpacity(0.3)
                  : const Color(0xFF2E7D6B).withOpacity(0.18),
            ),
          ),
          child: Row(
            children: [
              Icon(
                disputeRemaining == Duration.zero
                    ? Icons.error_outline
                    : Icons.hourglass_bottom,
                size: 18,
                color: disputeRemaining == Duration.zero
                    ? Colors.red.shade700
                    : const Color(0xFF2E7D6B),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  disputeRemaining == Duration.zero
                      ? 'Final dispute statement window expired'
                      : 'Final dispute statement ${_formatDuration(disputeRemaining)} remaining',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    color: disputeRemaining == Duration.zero
                        ? Colors.red.shade700
                        : const Color(0xFF2E7D6B),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
      actions.add(const SizedBox(height: 8));
    }

    if (can('agree_rental')) {
      actions.add(
        _actionButton('Agree Rental', () => _performAction('agree_rental')),
      );
      actions.add(
        _actionButton('Reject Enquiry', () => _performAction('reject_enquiry')),
      );
    }

    if (can('request_cancellation')) {
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

    if (can('confirm_lender_contract')) {
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

    if (can('reinitiate_lender_contract')) {
      actions.add(
        _actionButton(
          'Re-send Confirmation Request',
          () => _performAction('reinitiate_lender_contract'),
        ),
      );
    }

    if (detail.status == 'RAGR' &&
        detail.meIsRenter &&
        detail.lenderAgreedAt != null &&
        detail.renterAgreedAt == null) {
      // Only show confirm/reject buttons if contract window is still open
      if (can('confirm_renter_contract')) {
        actions.add(
          _actionButton('Confirm Renter Contract', () async {
            final agreed = await _showRentalTermsConfirmation();
            if (!agreed) {
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
      } else {
        // Contract window has expired - suggest messaging lender
        actions.add(
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Contract confirmation window has expired',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Please contact the lender to request an extension of the confirmation deadline.',
                    ),
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: _scrollToMessages,
                        icon: const Icon(Icons.message),
                        label: const Text('Send Message'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      }
    }

    if (detail.workflowPayload.message.isNotEmpty) {
      actions.add(
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Text(detail.workflowPayload.message),
        ),
      );
    }

    if (can('initiate_rental')) {
      actions.add(
        _evidenceCapturePanel(
          title: 'Collection evidence (lender)',
          body:
              'Record the item condition before collection. The borrower will review this evidence. Rental payment and the deposit hold are processed when you submit.',
          submitLabel: 'Submit Checkout Evidence',
          action: 'initiate_rental',
          actionLabel: 'checkout lender evidence',
          fieldName: 'checkout_video_url',
          onChooseVideo: () => _pickEvidenceVideo(source: ImageSource.gallery),
          onRecordVideo: () => _pickEvidenceVideo(source: ImageSource.camera),
        ),
      );
    }
    if (can('confirm_checkout_evidence')) {
      actions.add(
        _actionButton(
          'Accept Condition & Show Collection Code',
          () => _performAction('confirm_checkout_evidence'),
        ),
      );
    }
    if (can('submit_checkout_borrower_evidence')) {
      actions.add(
        _evidenceCapturePanel(
          title: 'Collection counter-evidence (borrower)',
          body:
              'Review the lender video in Evidence. If you disagree, submit your own condition video.',
          submitLabel: 'Submit Counter-Evidence',
          action: 'submit_checkout_borrower_evidence',
          actionLabel: 'checkout borrower evidence',
          fieldName: 'checkout_borrower_video_url',
          onChooseVideo: () => _pickEvidenceVideo(source: ImageSource.gallery),
          onRecordVideo: () => _pickEvidenceVideo(source: ImageSource.camera),
        ),
      );
    }
    if (detail.status == 'RDAYAWV' &&
        detail.meIsRenter &&
        codes?.checkoutPin.isNotEmpty == true) {
      actions.add(
        _handoverCodePanel(
          title: 'Collection code',
          body:
              'Your condition acceptance is recorded. Show this code to the lender to complete collection.',
          pin: codes!.checkoutPin,
          qrPayload: codes.checkoutQrPayload,
          buttonLabel: 'Show Collection Code',
        ),
      );
    }
    if (can('verify_checkout_handover_pin')) {
      actions.add(
        _handoverVerificationPanel(
          title: 'Verify collection',
          body: 'Ask the borrower for their collection code.',
          action: 'verify_checkout_handover_pin',
          submitLabel: 'Collection confirmed',
        ),
      );
    }
    if (can('collect_deposit') && !can('initiate_rental')) {
      actions.add(
        _actionButton(
          'Collect / Retry Deposit Hold',
          () => _performAction('collect_deposit'),
        ),
      );
    }
    if (can('submit_return_borrower_evidence')) {
      actions.add(
        _evidenceCapturePanel(
          title: 'Return evidence (borrower)',
          body: 'Record the item condition at return for the lender to review.',
          submitLabel: 'Submit / Update Return Evidence',
          action: 'submit_return_borrower_evidence',
          actionLabel: 'return evidence',
          fieldName: 'return_video_url',
          onChooseVideo: () => _pickEvidenceVideo(source: ImageSource.gallery),
          onRecordVideo: () => _pickEvidenceVideo(source: ImageSource.camera),
        ),
      );
    }
    if (can('confirm_return_evidence')) {
      actions.add(
        _actionButton(
          'Accept Condition & Show Return Code',
          () => _performAction('confirm_return_evidence'),
        ),
      );
    }
    if (can('submit_lender_return_evidence')) {
      actions.add(
        _evidenceCapturePanel(
          title: 'Return counter-evidence (lender)',
          body:
              'Review the borrower video in Evidence. If you disagree, submit your own return video.',
          submitLabel: 'Submit Return Counter-Evidence',
          action: 'submit_lender_return_evidence',
          actionLabel: 'lender return evidence',
          fieldName: 'lender_return_video_url',
          onChooseVideo: () => _pickEvidenceVideo(source: ImageSource.gallery),
          onRecordVideo: () => _pickEvidenceVideo(source: ImageSource.camera),
        ),
      );
    }
    if (detail.status == 'RRTDAYAWV' &&
        detail.meIsLender &&
        codes?.returnPin.isNotEmpty == true) {
      actions.add(
        _handoverCodePanel(
          title: 'Return code',
          body:
              'Your condition acceptance is recorded. Show this code to the borrower to complete the return.',
          pin: codes!.returnPin,
          qrPayload: codes.returnQrPayload,
          buttonLabel: 'Show Return Code',
        ),
      );
    }
    if (can('verify_return_handover_pin')) {
      actions.add(
        _handoverVerificationPanel(
          title: 'Verify return',
          body: 'Ask the lender for their return code.',
          action: 'verify_return_handover_pin',
          submitLabel: 'Verify Return & Continue',
        ),
      );
    }

    if (can('report_missing_rental')) {
      actions.add(const SizedBox(height: 4));
      actions.add(
        _actionButton('Report Missing Rental', () async {
          if (!mounted) {
            return;
          }
          final reason = await _promptForText(
            title: 'Report Missing Rental',
            label: 'Reason',
            hint: 'Explain what happened',
          );
          if (!mounted || reason == null || reason.trim().isEmpty) {
            return;
          }
          await _performAction(
            'report_missing_rental',
            fields: {'reason': reason},
          );
        }),
      );
    }

    if (needsCardSetup) {
      actions.add(
        Text(
          'Deposit card status: ${_depositCardStatusText(detail.depositCardSetupStatus)}',
        ),
      );
      if (_transactionDurationDays(detail) >= 7) {
        actions.add(const SizedBox(height: 6));
        actions.add(
          const Text(
            'Rentals from 7 to 30 days require a Visa credit card or Mastercard credit card for the deposit. You can still use a different card for payment.',
          ),
        );
      }
      actions.add(const SizedBox(height: 8));
      if (nativeStripeConfigured) {
        actions.add(
          _actionButton(
            'Add Deposit Card (Stripe)',
            _setupDepositCardWithStripe,
          ),
        );
      } else {
        actions.add(const Text('Cannot connect to Stripe right now.'));
      }
      if (nativeStripeConfigured) {
        actions.add(
          const Text(
            'Secure Stripe card entry is enabled on this mobile build.',
          ),
        );
      }
      if (hasSavedPaymentMethods) {
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
    }

    if (can('report_missing_return')) {
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

    if (detail.status == 'RRTDPEND' && can('propose_deposit_return')) {
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

    if (detail.status == 'RRTDCON' && detail.meIsLender && detail.deposit > 0) {
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

    if (detail.status != 'RRTDCON' && can('secure_dispute_funds')) {
      actions.add(
        _actionButton(
          'Secure Dispute Funds',
          () => _performAction('secure_dispute_funds'),
        ),
      );
    }

    if (can('agree_deposit_return')) {
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

    if (can('raise_deposit_dispute_admin')) {
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

    if (can('submit_feedback') && !detail.feedbackLeftByMe) {
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

    if (actions.isEmpty) {
      actions.add(
        Text(
          detail.status == 'CACK'
              ? _cancellationSummary(detail)
              : detail.statusDisplay.trim().isNotEmpty &&
                    detail.statusDisplay.startsWith(
                      'All required steps complete',
                    )
              ? 'All required steps complete, awaiting rental day.'
              : 'No direct actions available right now. Use messages to coordinate the next step.',
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

  Widget _actionSection({
    required String title,
    required String body,
    required List<Widget> children,
    required Color accent,
    required IconData icon,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: accent.withOpacity(0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: accent),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            body,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 10),
          ...children,
        ],
      ),
    );
  }

  Widget _evidenceCapturePanel({
    required String title,
    required String body,
    required String submitLabel,
    required String action,
    required String actionLabel,
    required String fieldName,
    required Future<void> Function() onChooseVideo,
    required Future<void> Function() onRecordVideo,
  }) {
    return _actionSection(
      title: title,
      body:
          '$body Videos are compressed before upload. A smaller preview and the full uploaded download will be available.',
      accent: const Color(0xFF5B5FC7),
      icon: Icons.video_library_outlined,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed: _busy ? null : () => onChooseVideo(),
              icon: const Icon(Icons.video_library_outlined),
              label: const Text('Choose Video'),
            ),
            OutlinedButton.icon(
              onPressed: _busy ? null : () => onRecordVideo(),
              icon: const Icon(Icons.videocam_outlined),
              label: const Text('Record'),
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
        if (_evidenceVideoFile != null) ...[
          const SizedBox(height: 8),
          Text(
            'Selected video: ${_evidenceVideoFile!.path.split('/').last}',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
        if (_busy && _uploadPhase != null) ...[
          const SizedBox(height: 10),
          _videoUploadProgress(),
        ],
        const SizedBox(height: 10),
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: _busy
                ? null
                : () => _performVideoEvidenceAction(
                    action: action,
                    fieldName: fieldName,
                    actionLabel: actionLabel,
                  ),
            icon: const Icon(Icons.cloud_upload_outlined),
            label: Text(_busy ? 'Preparing and uploading…' : submitLabel),
          ),
        ),
      ],
    );
  }

  Widget _handoverCodePanel({
    required String title,
    required String body,
    required String pin,
    required String qrPayload,
    required String buttonLabel,
  }) {
    return _actionSection(
      title: title,
      body: body,
      accent: const Color(0xFF0F766E),
      icon: Icons.qr_code_2_outlined,
      children: [
        SelectableText(
          'PIN: $pin',
          style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => QrDisplayScreen(
                  title: title,
                  qrPayload: qrPayload,
                  pin: pin,
                ),
              ),
            ),
            icon: const Icon(Icons.qr_code_2),
            label: Text(buttonLabel),
          ),
        ),
      ],
    );
  }

  Widget _handoverVerificationPanel({
    required String title,
    required String body,
    required String action,
    required String submitLabel,
  }) {
    return _actionSection(
      title: title,
      body: body,
      accent: const Color(0xFF0F766E),
      icon: Icons.qr_code_scanner,
      children: [
        TextField(
          controller: _pinController,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(labelText: 'PIN'),
        ),
        _actionButton(
          submitLabel,
          () => _performAction(
            action,
            fields: {'pin': _pinController.text.trim()},
          ),
        ),
        _actionButton('Scan QR Code', () => _scanAndVerify(action)),
      ],
    );
  }

  int _transactionDurationDays(TransactionDetail detail) {
    final start = detail.rentalStartDate;
    final end = detail.rentalEndDate;
    if (start == null || end == null) {
      return 0;
    }
    return end.difference(start).inDays + 1;
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
              focusNode: _messageFocusNode,
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
            if (_messages
                .where((message) => !message.isSystemGenerated)
                .isEmpty)
              const Text('No messages yet.')
            else
              ..._messages
                  .where((message) => !message.isSystemGenerated)
                  .map(
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
                                              (
                                                context,
                                                error,
                                                stackTrace,
                                              ) => Container(
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
                                      return Column(
                                        children: [
                                          if (a.previewUrl.isNotEmpty)
                                            TextButton.icon(
                                              onPressed: () =>
                                                  _watchVideo(a.previewUrl),
                                              icon: const Icon(
                                                Icons.play_circle_outline,
                                              ),
                                              label: const Text(
                                                'Watch preview',
                                              ),
                                            )
                                          else
                                            Text(
                                              a.previewStatus == 'failed'
                                                  ? 'Preview unavailable'
                                                  : 'Preparing preview…',
                                            ),
                                          if (a.downloadUrl.isNotEmpty)
                                            TextButton.icon(
                                              onPressed: _downloadInProgress
                                                  ? null
                                                  : () => _downloadVideo(
                                                      a.downloadUrl,
                                                    ),
                                              icon: const Icon(
                                                Icons.download_outlined,
                                              ),
                                              label: const Text(
                                                'Download full uploaded quality',
                                              ),
                                            ),
                                        ],
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
