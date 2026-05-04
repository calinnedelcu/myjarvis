import 'dart:io' show Platform;

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

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
  bool _localOnly = false;
  String? _currentToken;

  /// Exposed so Phase 4 lite-mode reminders can schedule via the same plug-in.
  FlutterLocalNotificationsPlugin get notifications => _local;

  Future<void> initialize() async {
    if (_initialized) return;

    // Local notifications + timezone always init (lite-mode reminders depend
    // on them even when Firebase isn't configured).
    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );
    await _local.initialize(
      const InitializationSettings(android: androidInit, iOS: iosInit),
    );

    const remindersChannel = AndroidNotificationChannel(
      'jarvis_reminders',
      'Reminders',
      description: 'Local reminders set in lite mode',
      importance: Importance.high,
    );
    const defaultChannel = AndroidNotificationChannel(
      'jarvis_default',
      'Jarvis notifications',
      description: 'Email, calendar, and Claude Code alerts',
      importance: Importance.high,
    );
    final androidImpl = _local
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
    await androidImpl?.createNotificationChannel(remindersChannel);
    await androidImpl?.createNotificationChannel(defaultChannel);

    try {
      tzdata.initializeTimeZones();
      final localName = await FlutterTimezone.getLocalTimezone();
      tz.setLocalLocation(tz.getLocation(localName));
    } catch (e) {
      debugPrint('PushService: timezone init skipped — $e');
    }

    try {
      await Firebase.initializeApp();
    } catch (e) {
      debugPrint('PushService: Firebase init skipped — $e (lite mode only)');
      _localOnly = true;
      _initialized = true;
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
      _initialized = true;
      return;
    }

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
    if (!_initialized || _localOnly) return;
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
