import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import 'jarvis_api.dart';

/// Background isolate handler — must be top-level. Fires when a data/
/// notification message arrives while the app is killed/backgrounded.
@pragma('vm:entry-point')
Future<void> _onBackgroundMessage(RemoteMessage message) async {
  // We don't do work here — the system tray handles display when the FCM
  // payload includes a `notification` block. This stub just keeps the
  // isolate alive so Flutter doesn't drop the message.
}

class PushService {
  PushService._();
  static final PushService instance = PushService._();

  final FlutterLocalNotificationsPlugin _local =
      FlutterLocalNotificationsPlugin();
  bool _initialized = false;
  bool _firebaseReady = false;

  /// Exposed so lite-mode reminders can schedule via this same plug-in.
  FlutterLocalNotificationsPlugin get notifications => _local;

  Future<void> initialize() async {
    if (_initialized) return;

    try {
      tzdata.initializeTimeZones();
      final tzName = await FlutterTimezone.getLocalTimezone();
      tz.setLocalLocation(tz.getLocation(tzName));
    } catch (e) {
      debugPrint('PushService: timezone init failed — $e');
    }

    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings();
    await _local.initialize(
      const InitializationSettings(android: androidInit, iOS: iosInit),
    );

    const channel = AndroidNotificationChannel(
      'jarvis_reminders',
      'Reminders',
      description: 'Reminders + push from the PC',
      importance: Importance.high,
    );
    await _local
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);

    try {
      await Firebase.initializeApp();
      _firebaseReady = true;
      FirebaseMessaging.onBackgroundMessage(_onBackgroundMessage);

      // Foreground messages — surface via local notification so the user
      // sees the drawer even when the app is open.
      FirebaseMessaging.onMessage.listen((msg) {
        final n = msg.notification;
        if (n == null) return;
        _local.show(
          n.hashCode,
          n.title ?? 'Jarvis',
          n.body ?? '',
          const NotificationDetails(
            android: AndroidNotificationDetails(
              'jarvis_reminders',
              'Reminders',
              importance: Importance.high,
              priority: Priority.high,
            ),
            iOS: DarwinNotificationDetails(),
          ),
        );
      });
    } catch (e) {
      debugPrint('PushService: Firebase init skipped — $e');
      _firebaseReady = false;
    }

    _initialized = true;
  }

  /// Request notification permission and register the FCM token with the PC.
  Future<void> registerWith(JarvisApi api) async {
    if (!_firebaseReady) return;
    if (api.isLiteOnly) return;

    try {
      final fm = FirebaseMessaging.instance;
      await fm.requestPermission(alert: true, badge: true, sound: true);

      final token = await fm.getToken();
      if (token == null || token.isEmpty) {
        debugPrint('PushService: no FCM token yet');
        return;
      }
      await api.registerDevice(
        token: token,
        platform: defaultTargetPlatform.name,
      );

      // Re-register on rotation so the PC always has a live token.
      fm.onTokenRefresh.listen((newToken) async {
        try {
          await api.registerDevice(
            token: newToken,
            platform: defaultTargetPlatform.name,
          );
        } catch (e) {
          debugPrint('PushService: token refresh register failed — $e');
        }
      });
    } catch (e) {
      debugPrint('PushService: registerWith failed — $e');
    }
  }

  Future<void> unregister(JarvisApi api) async {
    if (!_firebaseReady) return;
    try {
      final token = await FirebaseMessaging.instance.getToken();
      if (token != null) await api.unregisterDevice(token);
    } catch (e) {
      debugPrint('PushService: unregister failed — $e');
    }
  }
}
