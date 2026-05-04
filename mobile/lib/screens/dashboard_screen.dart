import 'dart:async';

import 'package:flutter/material.dart';

import '../services/jarvis_api.dart';
import '../services/push_service.dart';
import '../services/storage.dart';
import '../theme.dart';
import 'ask_screen.dart';
import 'setup_screen.dart';
import 'voice_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  JarvisApi? _api;
  Map<String, dynamic>? _data;
  String? _error;
  bool _loading = true;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    final creds = await CredentialStore.instance.read();
    if (creds == null) {
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const SetupScreen()),
      );
      return;
    }
    _api = JarvisApi(creds);
    // Register this phone for push notifications (no-op if Firebase missing).
    unawaited(PushService.instance.registerWith(_api!));
    await _refresh();
    _poll = Timer.periodic(const Duration(seconds: 30), (_) => _refresh());
  }

  Future<void> _refresh() async {
    if (_api == null) return;
    try {
      final data = await _api!.dashboard();
      if (!mounted) return;
      setState(() {
        _data = data;
        _error = null;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'PC unreachable: ${e.toString().substring(0, e.toString().length.clamp(0, 80))}';
        _loading = false;
      });
    }
  }

  Future<void> _logout() async {
    await CredentialStore.instance.clear();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const SetupScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('J.A.R.V.I.S.'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _refresh),
          IconButton(icon: const Icon(Icons.logout), onPressed: _logout),
        ],
      ),
      floatingActionButton: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          FloatingActionButton(
            heroTag: 'voice',
            backgroundColor: kBgPanel,
            foregroundColor: kAccent,
            shape: const CircleBorder(side: BorderSide(color: kAccent, width: 2)),
            onPressed: _api == null
                ? null
                : () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => VoiceScreen(api: _api!)),
                    ),
            child: const Icon(Icons.mic),
          ),
          const SizedBox(height: 12),
          FloatingActionButton.extended(
            heroTag: 'ask',
            backgroundColor: kAccent,
            foregroundColor: kBg,
            icon: const Icon(Icons.chat_bubble_outline),
            label: const Text('ASK'),
            onPressed: _api == null
                ? null
                : () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => AskScreen(api: _api!)),
                    ),
          ),
        ],
      ),
      body: RefreshIndicator(
        color: kAccent,
        onRefresh: _refresh,
        child: _loading
            ? const Center(child: CircularProgressIndicator(color: kAccent))
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null)
                    Card(
                      color: kDanger.withOpacity(0.15),
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Text(_error!, style: const TextStyle(color: kDanger)),
                      ),
                    ),
                  _SystemCard(_data?['system']),
                  _SimpleCard('WEATHER', _formatWeather(_data?['weather'])),
                  _SimpleCard('CALENDAR', _data?['calendar']?.toString()),
                  _SimpleCard('EMAILS', _data?['emails']?.toString()),
                  _SimpleCard('SPOTIFY', _data?['spotify']?.toString()),
                  _SimpleCard('LIGHTS', _data?['lights']?.toString()),
                  const SizedBox(height: 80),
                ],
              ),
      ),
    );
  }

  String? _formatWeather(dynamic w) {
    if (w is! Map) return null;
    return '${w['temp_c']}°C — ${w['description']}\n'
        'Feels ${w['feels_like']}°C · humidity ${w['humidity']}%';
  }
}

class _SystemCard extends StatelessWidget {
  const _SystemCard(this.sys);
  final dynamic sys;

  @override
  Widget build(BuildContext context) {
    if (sys is! Map) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('SYSTEM', style: TextStyle(color: kAccent, letterSpacing: 2)),
            const SizedBox(height: 8),
            Text(
              'CPU ${sys['cpu_percent']}%   ·   '
              'RAM ${sys['ram_used_gb']} / ${sys['ram_total_gb']} GB '
              '(${sys['ram_percent']}%)',
              style: const TextStyle(color: Colors.white),
            ),
            Text(
              'Uptime ${sys['uptime_hours']}h',
              style: const TextStyle(color: Colors.white70),
            ),
          ],
        ),
      ),
    );
  }
}

class _SimpleCard extends StatelessWidget {
  const _SimpleCard(this.title, this.body);
  final String title;
  final String? body;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(color: kAccent, letterSpacing: 2)),
            const SizedBox(height: 8),
            Text(
              body == null || body!.isEmpty ? '—' : body!,
              style: const TextStyle(color: Colors.white),
            ),
          ],
        ),
      ),
    );
  }
}
