import 'package:flutter/material.dart';

import 'config.dart';
import 'models/auth_models.dart';
import 'models/transaction_models.dart';
import 'screens/home_screen.dart';
import 'screens/transaction_detail_screen.dart';
import 'services/api_client.dart';
import 'services/account_repository.dart';
import 'services/auth_repository.dart';
import 'services/biometric_auth_service.dart';
import 'services/catalog_repository.dart';
import 'services/order_repository.dart';
import 'services/push_notification_service.dart';
import 'services/theme_service.dart';
import 'services/transaction_repository.dart';
import 'storage/token_store.dart';
import 'theme.dart';

void runSharingHubMobile() {
  final apiClient = ApiClient(baseUrl: AppConfig.baseUrl);
  final tokenStore = TokenStore();
  final authRepository = AuthRepository(
    apiClient: apiClient,
    tokenStore: tokenStore,
  );
  final accountRepository = AccountRepository(apiClient: apiClient);
  final transactionRepository = TransactionRepository(apiClient: apiClient);
  final pushNotificationService = PushNotificationService(apiClient: apiClient);
  final orderRepository = OrderRepository(apiClient: apiClient);
  final catalogRepository = CatalogRepository(apiClient: apiClient);

  runApp(
    SharingHubMobileApp(
      authRepository: authRepository,
      biometricAuthService: BiometricAuthService(),
      tokenStore: tokenStore,
      accountRepository: accountRepository,
      transactionRepository: transactionRepository,
      pushNotificationService: pushNotificationService,
      orderRepository: orderRepository,
      catalogRepository: catalogRepository,
    ),
  );
}

class SharingHubMobileApp extends StatefulWidget {
  const SharingHubMobileApp({
    super.key,
    required this.authRepository,
    required this.biometricAuthService,
    required this.tokenStore,
    required this.accountRepository,
    required this.transactionRepository,
    required this.pushNotificationService,
    required this.orderRepository,
    required this.catalogRepository,
  });

  final AuthRepository authRepository;
  final BiometricAuthService biometricAuthService;
  final TokenStore tokenStore;
  final AccountRepository accountRepository;
  final TransactionRepository transactionRepository;
  final PushNotificationService pushNotificationService;
  final OrderRepository orderRepository;
  final CatalogRepository catalogRepository;

  @override
  State<SharingHubMobileApp> createState() => _SharingHubMobileAppState();
}

class _SharingHubMobileAppState extends State<SharingHubMobileApp> {
  final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();
  final ThemeService _themeService = ThemeService();
  AuthSession? _session;
  List<TransactionSummary> _transactions = const [];
  bool _authBusy = false;
  bool _transactionBusy = false;
  bool _initializing = true;
  bool _privacyNoticeAccepted = false;
  bool _hasSavedSession = false;
  bool _deviceBiometricsAvailable = false;
  bool _biometricUnlockEnabled = false;
  bool _biometricPreferenceSet = false;
  bool _isDarkMode = false;
  bool _showingTxnNotices = false;
  bool _showingForegroundAlert = false;
  NotificationPreferences _notificationPreferences =
      NotificationPreferences.defaults;

  @override
  void initState() {
    super.initState();
    widget.pushNotificationService.setForegroundAlertHandler(
      _handleForegroundPushAlert,
    );
    _restoreSession();
  }

  @override
  void dispose() {
    widget.pushNotificationService.setForegroundAlertHandler(null);
    super.dispose();
  }

  Future<void> _restoreSession() async {
    final hasSavedSession = await widget.tokenStore.hasSavedSession();
    final privacyNoticeAccepted = await widget.tokenStore
        .isPrivacyNoticeAccepted();
    final deviceBiometricsAvailable = await widget.biometricAuthService
        .isAvailable();
    final biometricUnlockEnabled = await widget.tokenStore
        .isBiometricUnlockEnabled();
    final biometricPreferenceSet = await widget.tokenStore
        .isBiometricUnlockPreferenceSet();
    final isDarkMode = await _themeService.isDarkMode();
    if (!mounted) {
      return;
    }

    setState(() {
      _hasSavedSession = hasSavedSession;
      _privacyNoticeAccepted = privacyNoticeAccepted;
      _deviceBiometricsAvailable = deviceBiometricsAvailable;
      _biometricUnlockEnabled = biometricUnlockEnabled;
      _biometricPreferenceSet = biometricPreferenceSet;
      _isDarkMode = isDarkMode;
      _initializing = false;
    });
  }

  Future<void> _maybePromptEnableBiometricAfterLogin() async {
    if (!mounted || !_deviceBiometricsAvailable || _biometricPreferenceSet) {
      return;
    }

    final context = _navigatorKey.currentContext;
    if (context == null) {
      return;
    }

    final enableBiometric = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Enable biometric unlock?'),
          content: const Text(
            'Would you like to use Face ID or fingerprint to sign in next time?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Not now'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Enable'),
            ),
          ],
        );
      },
    );

    final enabled = enableBiometric == true;
    await widget.tokenStore.setBiometricUnlockEnabled(enabled);
    if (!mounted) {
      return;
    }
    setState(() {
      _biometricUnlockEnabled = enabled;
      _biometricPreferenceSet = true;
    });
  }

  Future<void> _acceptPrivacyNotice() async {
    await widget.tokenStore.setPrivacyNoticeAccepted(true);
    if (!mounted) {
      return;
    }
    setState(() {
      _privacyNoticeAccepted = true;
    });
  }

  Future<void> _restoreSavedSession() async {
    final session = await widget.authRepository.restoreSession();
    if (!mounted) {
      return;
    }

    setState(() {
      _session = session;
      _hasSavedSession = session != null;
    });

    if (session != null) {
      await widget.pushNotificationService.syncForSession(
        accessToken: session.accessToken,
      );
      _notificationPreferences = await widget.pushNotificationService
          .getPreferences();
      await _loadTransactions();
      await _showTransactionNotices(session.accessToken);
    }
  }

  Future<void> _login(String login, String password) async {
    setState(() {
      _authBusy = true;
    });

    try {
      final session = await widget.authRepository.login(
        login: login,
        password: password,
      );
      if (!mounted) {
        return;
      }

      setState(() {
        _session = session;
        _hasSavedSession = true;
      });

      _deviceBiometricsAvailable = await widget.biometricAuthService
          .isAvailable();

      await _maybePromptEnableBiometricAfterLogin();

      await widget.pushNotificationService.syncForSession(
        accessToken: session.accessToken,
      );
      _notificationPreferences = await widget.pushNotificationService
          .getPreferences();
      await _loadTransactions();
      await _showTransactionNotices(session.accessToken);
    } finally {
      if (mounted) {
        setState(() {
          _authBusy = false;
        });
      }
    }
  }

  Future<void> _onRegistered(AuthSession session) async {
    if (!mounted) {
      return;
    }

    setState(() {
      _session = session;
      _hasSavedSession = true;
    });

    _deviceBiometricsAvailable = await widget.biometricAuthService
        .isAvailable();
    await _maybePromptEnableBiometricAfterLogin();
    await widget.pushNotificationService.syncForSession(
      accessToken: session.accessToken,
    );
    _notificationPreferences = await widget.pushNotificationService
        .getPreferences();
    await _loadTransactions();
    await _showTransactionNotices(session.accessToken);
  }

  Future<void> _loadTransactions() async {
    final session = _session;
    if (session == null) {
      return;
    }

    setState(() {
      _transactionBusy = true;
    });

    try {
      final transactions = await widget.transactionRepository.fetchTransactions(
        accessToken: session.accessToken,
      );
      if (!mounted) {
        return;
      }

      setState(() {
        _transactions = transactions;
      });
    } finally {
      if (mounted) {
        setState(() {
          _transactionBusy = false;
        });
      }
    }
  }

  Future<void> _logout() async {
    final existingSession = _session;
    final preserveSessionForBiometric =
        _biometricUnlockEnabled && _hasSavedSession;

    if (existingSession != null) {
      await widget.pushNotificationService.unregisterForSession(
        accessToken: existingSession.accessToken,
      );
    }
    if (!preserveSessionForBiometric) {
      await widget.authRepository.logout();
    }
    if (!mounted) {
      return;
    }

    setState(() {
      _session = null;
      _transactions = const [];
      _hasSavedSession = preserveSessionForBiometric;
      _deviceBiometricsAvailable = preserveSessionForBiometric
          ? _deviceBiometricsAvailable
          : false;
      _notificationPreferences = NotificationPreferences.defaults;
    });
  }

  Future<void> _updateNotificationPreferences(
    NotificationPreferences preferences,
  ) async {
    final session = _session;
    if (session == null) {
      return;
    }

    final saved = await widget.pushNotificationService.updatePreferences(
      preferences: preferences,
      accessToken: session.accessToken,
    );

    if (!mounted) {
      return;
    }

    setState(() {
      _notificationPreferences = saved;
    });
  }

  Future<void> _handleForegroundPushAlert(ForegroundPushAlert alert) async {
    if (_showingForegroundAlert || !mounted) {
      return;
    }

    _showingForegroundAlert = true;
    try {
      final context = _navigatorKey.currentContext;
      if (context == null) {
        return;
      }

      await showDialog<void>(
        context: context,
        builder: (dialogContext) {
          return AlertDialog(
            title: Text(
              alert.notificationType == 'transaction_enquiry'
                  ? 'New transaction enquiry'
                  : alert.title,
            ),
            content: Text(alert.body),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Close'),
              ),
            ],
          );
        },
      );
    } finally {
      _showingForegroundAlert = false;
    }
  }

  Future<void> _setBiometricUnlockEnabled(bool enabled) async {
    await widget.tokenStore.setBiometricUnlockEnabled(enabled);
    if (!mounted) {
      return;
    }
    setState(() {
      _biometricUnlockEnabled = enabled;
      _biometricPreferenceSet = true;
    });
  }

  Future<void> _showTransactionNotices(String accessToken) async {
    if (_showingTxnNotices) {
      return;
    }

    _showingTxnNotices = true;
    try {
      final payload = await widget.transactionRepository
          .fetchTransactionNotifications(accessToken: accessToken);
      if (!mounted || payload.noticeCount <= 0) {
        return;
      }

      final navigator = _navigatorKey.currentState;
      if (navigator == null || !navigator.mounted) {
        return;
      }

      await showDialog<void>(
        context: navigator.context,
        barrierDismissible: true,
        builder: (dialogContext) {
          return AlertDialog(
            title: const Text('New booking alert'),
            content: SizedBox(
              width: double.maxFinite,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${payload.noticeCount} booking alert${payload.noticeCount == 1 ? '' : 's'} need your attention.',
                    ),
                    const SizedBox(height: 12),
                    ...payload.noticeItems.map(
                      (item) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(
                            Icons.notifications_active_outlined,
                          ),
                          title: Text(item.productName),
                          subtitle: Text(
                            '${item.dateLabel}\n${item.actionLabel}',
                          ),
                          isThreeLine: true,
                          onTap: () => Navigator.pop(dialogContext),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Later'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('View bookings'),
              ),
            ],
          );
        },
      );
    } finally {
      _showingTxnNotices = false;
    }
  }

  Future<void> _toggleDarkMode(bool isDark) async {
    await _themeService.setDarkMode(isDark);
    if (!mounted) {
      return;
    }
    setState(() {
      _isDarkMode = isDark;
    });
  }

  Future<void> _biometricLogin() async {
    if (_authBusy ||
        !_hasSavedSession ||
        !_deviceBiometricsAvailable ||
        !_biometricUnlockEnabled) {
      return;
    }

    setState(() {
      _authBusy = true;
    });

    try {
      final authenticated = await widget.biometricAuthService.authenticate();
      if (!authenticated) {
        return;
      }
      await _restoreSavedSession();
    } finally {
      if (mounted) {
        setState(() {
          _authBusy = false;
        });
      }
    }
  }

  Future<void> _openTransaction(TransactionSummary tx) async {
    final session = _session;
    if (session == null) {
      return;
    }

    final navigator = _navigatorKey.currentState;
    if (navigator == null) {
      return;
    }

    await navigator.push(
      MaterialPageRoute(
        builder: (_) => TransactionDetailScreen(
          transactionReference: tx.reference,
          accessToken: session.accessToken,
          repository: widget.transactionRepository,
        ),
      ),
    );

    await _loadTransactions();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: _navigatorKey,
      title: 'rentalution Mobile',
      theme: sharingHubLightTheme,
      darkTheme: sharingHubDarkTheme,
      themeMode: _isDarkMode ? ThemeMode.dark : ThemeMode.light,
      home: _buildHome(),
      // TODO: Add Nunito font to pubspec.yaml and use logo in AppBar or login screen
    );
  }

  Widget _buildHome() {
    if (_initializing) {
      return Scaffold(
        backgroundColor: const Color(0xFF2EC4B6), // Teal background
        body: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Expanded(
              child: Center(
                child: Image.asset(
                  'assets/images/app_icon_1024.png',
                  width: 280,
                  height: 280,
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(bottom: 60),
              child: SizedBox(
                width: 60,
                height: 60,
                child: CircularProgressIndicator(
                  strokeWidth: 5,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    Colors.white.withOpacity(0.9),
                  ),
                ),
              ),
            ),
          ],
        ),
      );
    }

    return HomeScreen(
      privacyNoticeAccepted: _privacyNoticeAccepted,
      onAcceptPrivacyNotice: _acceptPrivacyNotice,
      session: _session,
      transactions: _transactions,
      loading: _transactionBusy,
      onRefresh: _session != null ? _loadTransactions : null,
      onLogout: _session != null ? _logout : null,
      onOpenTransaction: _session != null ? _openTransaction : null,
      onLogin: _login,
      onBiometricLogin:
          _hasSavedSession &&
              _deviceBiometricsAvailable &&
              _biometricUnlockEnabled
          ? _biometricLogin
          : null,
      showBiometricLogin:
          _hasSavedSession &&
          _deviceBiometricsAvailable &&
          _biometricUnlockEnabled,
      biometricAvailable: _deviceBiometricsAvailable,
      biometricEnabled: _biometricUnlockEnabled,
      onBiometricToggle: _setBiometricUnlockEnabled,
      isDarkMode: _isDarkMode,
      onThemeToggle: _toggleDarkMode,
      authRepository: widget.authRepository,
      onRegistered: _onRegistered,
      authBusy: _authBusy,
      accessToken: _session?.accessToken,
      accountRepository: widget.accountRepository,
      orderRepository: widget.orderRepository,
      catalogRepository: widget.catalogRepository,
      transactionRepository: widget.transactionRepository,
      notificationPreferences: _notificationPreferences,
      onUpdateNotificationPreferences: _updateNotificationPreferences,
    );
  }
}
