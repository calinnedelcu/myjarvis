// Demo build stub — the cloud APK strips firebase_core / firebase_messaging
// so it builds without needing google-services.json. Local notifications
// (used by lite-mode reminders) still work via flutter_local_notifications.
//
// The full FCM pipeline lives at this path in master once you restore
// firebase_core + firebase_messaging in pubspec.yaml on the dev machine.

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import 'jarvis_api.dart';

class PushService {
  PushService._();
  static final PushService instance = PushService._();

  final FlutterLocalNotificationsPlugin _local =
      FlutterLocalNotificationsPlugin();
  bool _initialized = false;

  /// Exposed so lite-mode reminders can schedule via this same plug-in.
  FlutterLocalNotificationsPlugin get notifications => _local;

  Future<void> initialize() async {
    if (_initialized) return;

    // Set local timezone so zonedSchedule fires at the right moment.
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
      description: 'Local reminders set in lite mode',
      importance: Importance.high,
    );
    await _local
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);

    _initialized = true;
  }

  /// FCM is disabled in this build. Kept as a no-op so callers don't crash.
  Future<void> registerWith(JarvisApi api) async {}

  Future<void> unregister(JarvisApi api) async {}
}
