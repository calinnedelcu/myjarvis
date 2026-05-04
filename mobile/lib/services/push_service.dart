import 'dart:io' show Platform;

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'jarvis_api.dart';

/// Background message handler — must be a top-level function for FCM.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  // System tray will display the notification automatically.
}

class PushService {
  PushService._();
  static final PushService instance = PushService._();

  final FlutterLocalNotificationsPlugin _local =
      FlutterLocalNotificationsPlugin();
  bool _initialized = false;
  String? _currentToken;

  Future<void> initialize() async {
    if (_initialized) return;
    try {
      await Firebase.initializeApp();
    } catch (e) {
      debugPrint('PushService: Firebase init skipped — $e');
      return;
    }

    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

    final messaging = FirebaseMessaging.instance;
    final settings = await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
    if (settings.authorizationStatus == AuthorizationStatus.denied) {
      debugPrint('PushService: notification permission denied');
      return;
    }

    // Local notifications channel for foreground display on Android.
    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings();
    await _local.initialize(
      const InitializationSettings(android: androidInit, iOS: iosInit),
    );

    const channel = AndroidNotificationChannel(
      'jarvis_default',
      'Jarvis notifications',
      description: 'Email, calendar, and Claude Code alerts',
      importance: Importance.high,
    );
    await _local
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);

    FirebaseMessaging.onMessage.listen((msg) {
      final n = msg.notification;
      if (n == null) return;
      _local.show(
        n.hashCode,
        n.title,
        n.body,
        const NotificationDetails(
          android: AndroidNotificationDetails(
            'jarvis_default',
            'Jarvis notifications',
            importance: Importance.high,
            priority: Priority.high,
          ),
          iOS: DarwinNotificationDetails(),
        ),
      );
    });

    _initialized = true;
  }

  /// Fetch the current FCM token and register it on the PC backend.
  Future<void> registerWith(JarvisApi api) async {
    if (!_initialized) return;
    try {
      final token = await FirebaseMessaging.instance.getToken();
      if (token == null || token.isEmpty) return;
      _currentToken = token;
      final platform = Platform.isAndroid
          ? 'android'
          : Platform.isIOS
              ? 'ios'
              : 'other';
      await api.registerDevice(token: token, platform: platform);
      debugPrint('PushService: registered token ${token.substring(0, 12)}…');

      FirebaseMessaging.instance.onTokenRefresh.listen((newToken) async {
        _currentToken = newToken;
        try {
          await api.registerDevice(token: newToken, platform: platform);
        } catch (e) {
          debugPrint('PushService: refresh registration failed — $e');
        }
      });
    } catch (e) {
      debugPrint('PushService: register failed — $e');
    }
  }

  Future<void> unregister(JarvisApi api) async {
    final t = _currentToken;
    if (t == null) return;
    try {
      await api.unregisterDevice(t);
    } catch (_) {}
  }
}
