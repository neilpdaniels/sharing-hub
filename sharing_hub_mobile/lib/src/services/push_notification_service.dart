import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';

class NotificationPreferences {
  const NotificationPreferences({
    required this.transactionEnquiry,
    required this.transactionMessages,
    required this.inAppAlerts,
  });

  final bool transactionEnquiry;
  final bool transactionMessages;
  final bool inAppAlerts;

  static const defaults = NotificationPreferences(
    transactionEnquiry: true,
    transactionMessages: true,
    inAppAlerts: true,
  );

  Map<String, dynamic> toJson() {
    return {
      'notify_transaction_enquiry': transactionEnquiry,
      'notify_transaction_messages': transactionMessages,
      'notify_in_app_alerts': inAppAlerts,
    };
  }

  factory NotificationPreferences.fromJson(Map<String, dynamic> json) {
    return NotificationPreferences(
      transactionEnquiry: json['notify_transaction_enquiry'] as bool? ?? true,
      transactionMessages: json['notify_transaction_messages'] as bool? ?? true,
      inAppAlerts: json['notify_in_app_alerts'] as bool? ?? true,
    );
  }

  NotificationPreferences copyWith({
    bool? transactionEnquiry,
    bool? transactionMessages,
    bool? inAppAlerts,
  }) {
    return NotificationPreferences(
      transactionEnquiry: transactionEnquiry ?? this.transactionEnquiry,
      transactionMessages: transactionMessages ?? this.transactionMessages,
      inAppAlerts: inAppAlerts ?? this.inAppAlerts,
    );
  }
}

class ForegroundPushAlert {
  const ForegroundPushAlert({
    required this.title,
    required this.body,
    required this.notificationType,
    required this.transactionReference,
  });

  final String title;
  final String body;
  final String notificationType;
  final String transactionReference;
}

@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  try {
    await Firebase.initializeApp();
  } catch (_) {
    // App may not be fully configured for Firebase in local development.
  }
}

class PushNotificationService {
  PushNotificationService({required ApiClient apiClient})
    : _apiClient = apiClient;

  final ApiClient _apiClient;
  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;
  String? _lastRegisteredToken;
  String? _accessToken;
  NotificationPreferences _preferences = NotificationPreferences.defaults;
  Future<void> Function(ForegroundPushAlert alert)? _foregroundAlertHandler;

  static const _prefTxnEnquiryKey = 'notify_transaction_enquiry';
  static const _prefTxnMessagesKey = 'notify_transaction_messages';
  static const _prefInAppAlertsKey = 'notify_in_app_alerts';

  Future<void> initialize() async {
    if (_initialized) {
      return;
    }

    try {
      await Firebase.initializeApp();
    } catch (error) {
      debugPrint('Firebase init skipped: $error');
      return;
    }

    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings();
    const initSettings = InitializationSettings(
      android: androidInit,
      iOS: iosInit,
    );
    await _localNotifications.initialize(initSettings);

    const channel = AndroidNotificationChannel(
      'sharing_hub_messages',
      'Message alerts',
      description: 'Notifications for new messages',
      importance: Importance.high,
    );

    final androidPlugin = _localNotifications
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >();
    await androidPlugin?.createNotificationChannel(channel);

    final messaging = FirebaseMessaging.instance;
    await messaging.requestPermission(alert: true, badge: true, sound: true);

    FirebaseMessaging.onMessage.listen((message) async {
      final notificationType = _notificationType(message);
      final preferences = await getPreferences();

      if (!_isNotificationEnabled(preferences, notificationType)) {
        return;
      }

      final notification = message.notification;
      if (notification == null) {
        return;
      }

      await _localNotifications.show(
        message.hashCode,
        notification.title ?? 'New message',
        notification.body ?? 'You have a new message.',
        const NotificationDetails(
          android: AndroidNotificationDetails(
            'sharing_hub_messages',
            'Message alerts',
            channelDescription: 'Notifications for new messages',
            importance: Importance.high,
            priority: Priority.high,
          ),
          iOS: DarwinNotificationDetails(),
        ),
      );

      if (preferences.inAppAlerts) {
        final handler = _foregroundAlertHandler;
        if (handler != null) {
          await handler(
            ForegroundPushAlert(
              title: notification.title ?? 'New alert',
              body: notification.body ?? 'You have a new notification.',
              notificationType: notificationType,
              transactionReference:
                  message.data['transaction_reference'] as String? ?? '',
            ),
          );
        }
      }
    });

    messaging.onTokenRefresh.listen((token) {
      final accessToken = _accessToken;
      if (accessToken == null || accessToken.isEmpty) {
        return;
      }
      _registerToken(accessToken: accessToken, token: token);
    });

    _initialized = true;
  }

  Future<void> syncForSession({required String accessToken}) async {
    await initialize();
    _accessToken = accessToken;
    await _hydratePreferencesFromLocal();

    try {
      final serverPreferences = await _apiClient.getJsonObject(
        '/notifications/preferences/',
        accessToken: accessToken,
      );
      _preferences = NotificationPreferences.fromJson(serverPreferences);
      await _persistPreferencesLocal(_preferences);
    } catch (_) {
      // Keep local preferences when server settings are unavailable.
    }

    if (!_initialized) {
      return;
    }

    final token = await FirebaseMessaging.instance.getToken();
    if (token == null || token.isEmpty) {
      return;
    }

    await _registerToken(accessToken: accessToken, token: token);
  }

  Future<void> unregisterForSession({required String accessToken}) async {
    _accessToken = null;
    if (!_initialized) {
      return;
    }

    final token =
        _lastRegisteredToken ?? await FirebaseMessaging.instance.getToken();
    if (token == null || token.isEmpty) {
      return;
    }

    try {
      await _apiClient.postJson('/devices/unregister/', {
        'token': token,
      }, accessToken: accessToken);
    } catch (error) {
      debugPrint('Failed to unregister push token: $error');
    }
  }

  Future<void> _registerToken({
    required String accessToken,
    required String token,
  }) async {
    final platform = _platformName();
    try {
      await _apiClient.postJson('/devices/register/', {
        'token': token,
        'platform': platform,
        ..._preferences.toJson(),
      }, accessToken: accessToken);
      _lastRegisteredToken = token;
    } catch (error) {
      debugPrint('Failed to register push token: $error');
    }
  }

  String _platformName() {
    if (kIsWeb) {
      return 'web';
    }
    if (Platform.isAndroid) {
      return 'android';
    }
    if (Platform.isIOS) {
      return 'ios';
    }
    return 'other';
  }

  Future<NotificationPreferences> getPreferences() async {
    await _hydratePreferencesFromLocal();
    return _preferences;
  }

  Future<NotificationPreferences> updatePreferences({
    required NotificationPreferences preferences,
    String? accessToken,
  }) async {
    _preferences = preferences;
    await _persistPreferencesLocal(preferences);

    final token = accessToken ?? _accessToken;
    if (token != null && token.isNotEmpty) {
      try {
        final response = await _apiClient.patchJson(
          '/notifications/preferences/',
          preferences.toJson(),
          accessToken: token,
        );
        _preferences = NotificationPreferences.fromJson(response);
        await _persistPreferencesLocal(_preferences);
      } catch (error) {
        debugPrint('Failed to sync notification preferences: $error');
      }
    }

    final refreshedToken = _lastRegisteredToken;
    if (token != null &&
        token.isNotEmpty &&
        refreshedToken != null &&
        refreshedToken.isNotEmpty) {
      await _registerToken(accessToken: token, token: refreshedToken);
    }

    return _preferences;
  }

  void setForegroundAlertHandler(
    Future<void> Function(ForegroundPushAlert alert)? handler,
  ) {
    _foregroundAlertHandler = handler;
  }

  String _notificationType(RemoteMessage message) {
    final value = message.data['notification_type'] ?? message.data['type'];
    return (value as String? ?? '').trim().toLowerCase();
  }

  bool _isNotificationEnabled(
    NotificationPreferences preferences,
    String notificationType,
  ) {
    if (notificationType == 'transaction_enquiry') {
      return preferences.transactionEnquiry;
    }
    if (notificationType == 'transaction_message') {
      return preferences.transactionMessages;
    }
    return true;
  }

  Future<void> _hydratePreferencesFromLocal() async {
    final prefs = await SharedPreferences.getInstance();
    _preferences = NotificationPreferences(
      transactionEnquiry:
          prefs.getBool(_prefTxnEnquiryKey) ?? _preferences.transactionEnquiry,
      transactionMessages:
          prefs.getBool(_prefTxnMessagesKey) ??
          _preferences.transactionMessages,
      inAppAlerts:
          prefs.getBool(_prefInAppAlertsKey) ?? _preferences.inAppAlerts,
    );
  }

  Future<void> _persistPreferencesLocal(
    NotificationPreferences preferences,
  ) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_prefTxnEnquiryKey, preferences.transactionEnquiry);
    await prefs.setBool(_prefTxnMessagesKey, preferences.transactionMessages);
    await prefs.setBool(_prefInAppAlertsKey, preferences.inAppAlerts);
  }
}
