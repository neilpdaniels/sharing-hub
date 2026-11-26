import 'package:flutter/material.dart';

class LegalAcceptanceScreen extends StatefulWidget {
  const LegalAcceptanceScreen({super.key, required this.onAccept});

  final Future<void> Function() onAccept;

  @override
  State<LegalAcceptanceScreen> createState() => _LegalAcceptanceScreenState();
}

class _LegalAcceptanceScreenState extends State<LegalAcceptanceScreen> {
  final ScrollController _scrollController = ScrollController();
  bool _reachedEnd = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_checkScrollPosition);
  }

  @override
  void dispose() {
    _scrollController
      ..removeListener(_checkScrollPosition)
      ..dispose();
    super.dispose();
  }

  void _checkScrollPosition() {
    if (!_reachedEnd &&
        _scrollController.position.extentAfter <= 24 &&
        mounted) {
      setState(() => _reachedEnd = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: false,
        title: const Text('Terms & conditions'),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                controller: _scrollController,
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
                children: [
                  Text(
                    'Please read these terms and our privacy and cookie information before using Rentalution.',
                    style: textTheme.bodyLarge,
                  ),
                  const SizedBox(height: 24),
                  _sectionTitle(context, 'Terms and conditions'),
                  _subsection(context, '1. Using Rentalution',
                      'By using the app, you agree to act honestly, keep your account details accurate, and follow the rules that apply to each booking or listing. You must not use Rentalution for anything unlawful, misleading, abusive, or harmful to another user.'),
                  _subsection(context, '2. Bookings',
                      'A booking becomes a live transaction once both parties confirm the rental steps. Dates, messages, and evidence are tracked through the booking workflow.'),
                  _subsection(context, '3. Deposits and payments',
                      'Fees are shown before you complete a relevant action. Where a deposit hold is required, you authorise the platform or its payment partner to place and later release or collect that hold according to the booking outcome and transaction workflow. After a rental is settled, Rentalution transfers the lender amount to the lender’s Stripe Express balance. Stripe pays eligible available funds to the lender’s nominated bank account on its payout schedule. Rentalution does not promise a particular banking rail, instant payout, or guaranteed arrival time.'),
                  _subsection(context, '4. Responsibilities',
                      'Provide accurate information for listings, enquiries, and transactions. Keep rental items in the described condition apart from fair wear and tear. Respond promptly to booking steps, messages, and evidence requests. Return items on time and in the agreed condition. Use the platform respectfully and keep communication professional.'),
                  _subsection(context, '5. Cancellations and disputes',
                      'Some bookings can only be cancelled if both parties agree, or when the transaction reaches a stage where the booking rules allow it. Disagreements about handover, condition, or deposit return may move to mediation or dispute review. Where a dispute cannot be resolved through the normal transaction flow, Rentalution may keep a deposit hold in place, pause a lender payout, and escalate the matter for review. Feedback should be honest, fair, and based on the booking experience.'),
                  _subsection(context, '6. Content and safety',
                      'Listings, profiles, messages, images, videos, and other content must be lawful, accurate, and suitable for a general marketplace. Do not upload or send threats, harassment, hate, exploitation, scams, illegal or unsafe items, malicious code, or content that infringes another person’s rights. Rentalution may hide or remove reported content, preserve evidence, restrict accounts, and refer suspected illegal activity to the appropriate authorities. Reports must be made honestly.'),
                  _subsection(context, '7. Contact',
                      'For help understanding these terms or reporting a concern, contact admin@rentalution.co.uk.'),
                  const Divider(height: 36),
                  _sectionTitle(context, 'Privacy information'),
                  _subsection(context, 'Data we collect and use',
                      'We collect account and sign-in details; profile and listing data; messages, booking details, and reviews; photos, videos, and condition evidence; location information you choose to share; device, app, notification, and security information; payment and payout references; and safety reports and moderation records. We use this information to provide accounts, listings, messaging, and transactions; protect users and prevent fraud or abuse; review reports; support customers; improve reliability; and meet legal obligations.'),
                  _subsection(context, 'How we handle and share data',
                      'Rentalution is the data controller for personal data processed through the platform. We rely on contract, legitimate interests, legal obligations, and consent where required. We share data as needed with providers including Google and Firebase, Stripe, Cloudflare, hosting and infrastructure providers, and communications providers. We may also share it where required by law or to protect users, prevent fraud, resolve disputes, or enforce our terms. We do not sell personal data. Some providers may process data outside the UK; appropriate safeguards are used where required.'),
                  _subsection(context, 'Retention and your rights',
                      'We keep personal data only as long as needed for service delivery, legal obligations, safety, payment, accounting, and dispute resolution. Payment, payout, tax, and transaction records may be kept for six years after the relevant financial year. Routine safety records may be kept for three years; serious safety, fraud, restriction, dispute, or claim records may be kept for six years. Routine condition media is removed from the live service after 90 days, archived for a further 90 days, then deleted. Following a verified deletion request, ordinary account data is erased or anonymised within 30 days unless an open booking or other legal reason requires retention. Subject to legal limits, you may request access, correction, deletion, restriction, objection, and data portability, and withdraw consent where processing relies on consent. Contact support for privacy requests; you may also complain to the UK ICO.'),
                  const Divider(height: 36),
                  _sectionTitle(context, 'Cookie information'),
                  _subsection(context, 'Cookies and your choices',
                      'Cookies are small files that help websites work and remember preferences. Strictly necessary cookies support login, security, and sessions. Preference cookies remember choices; analytics cookies help us understand service use. Non-essential cookies can be accepted or rejected from the website cookie banner. Necessary cookies remain active so the service can work, and you can clear cookies in your browser settings.'),
                  const SizedBox(height: 16),
                  Text(
                    'You can review the full policies at rentalution.co.uk. By accepting, you agree to the Terms and acknowledge the Privacy and Cookie information above.',
                    style: textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (!_reachedEnd)
                    const Padding(
                      padding: EdgeInsets.only(bottom: 8),
                      child: Text(
                        'Scroll to the end to accept.',
                        textAlign: TextAlign.center,
                      ),
                    ),
                  FilledButton(
                    onPressed: _reachedEnd ? widget.onAccept : null,
                    child: const Text('Agree and continue'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(BuildContext context, String title) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Text(title, style: Theme.of(context).textTheme.titleLarge),
      );

  Widget _subsection(BuildContext context, String title, String body) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(body, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
      );
}
