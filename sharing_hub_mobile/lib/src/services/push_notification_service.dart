import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'api_client.dart';

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
}
