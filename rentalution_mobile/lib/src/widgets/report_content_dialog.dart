import 'package:flutter/material.dart';

class ReportContentInput {
  const ReportContentInput({required this.reason, required this.details});

  final String reason;
  final String details;
}

const Map<String, String> reportReasonLabels = {
  'sexual_content': 'Sexual or nudity content',
  'child_safety': 'Child safety concern',
  'threat_or_harassment': 'Threats, harassment or bullying',
  'graphic_violence': 'Graphic violence',
  'illegal_or_unsafe_item': 'Illegal or unsafe item/content',
  'hate_or_discrimination': 'Hate or discrimination',
  'scam_or_fraud': 'Scam or fraud',
  'other': 'Other objectionable content',
};

Future<ReportContentInput?> showReportContentDialog(
  BuildContext context, {
  required String label,
}) async {
  String? selectedReason;
  final detailsController = TextEditingController();
  final result = await showDialog<ReportContentInput>(
    context: context,
    builder: (dialogContext) => StatefulBuilder(
      builder: (context, setDialogState) => AlertDialog(
        title: Text('Report $label'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Reports are reviewed by Rentalution. Please only report content that breaks our rules.',
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                initialValue: selectedReason,
                decoration: const InputDecoration(labelText: 'Reason'),
                items: reportReasonLabels.entries
                    .map(
                      (entry) => DropdownMenuItem(
                        value: entry.key,
                        child: Text(entry.value),
                      ),
                    )
                    .toList(growable: false),
                onChanged: (value) =>
                    setDialogState(() => selectedReason = value),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: detailsController,
                maxLength: 1500,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: 'Details (optional)',
                  alignLabelWithHint: true,
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
            onPressed: selectedReason == null
                ? null
                : () => Navigator.pop(
                    dialogContext,
                    ReportContentInput(
                      reason: selectedReason!,
                      details: detailsController.text.trim(),
                    ),
                  ),
            child: const Text('Send report'),
          ),
        ],
      ),
    ),
  );
  detailsController.dispose();
  return result;
}
