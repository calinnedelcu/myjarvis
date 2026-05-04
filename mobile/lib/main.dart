import 'package:flutter/material.dart';

import 'screens/dashboard_screen.dart';
import 'screens/setup_screen.dart';
import 'services/push_service.dart';
import 'services/storage.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Initialize FCM up front; safe no-op if Firebase isn't configured yet.
  await PushService.instance.initialize();
  final creds = await CredentialStore.instance.read();
  runApp(JarvisApp(hasCredentials: creds != null));
}

class JarvisApp extends StatelessWidget {
  const JarvisApp({super.key, required this.hasCredentials});
  final bool hasCredentials;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'J.A.R.V.I.S.',
      debugShowCheckedModeBanner: false,
      theme: jarvisTheme(),
      home: hasCredentials ? const DashboardScreen() : const SetupScreen(),
    );
  }
}
