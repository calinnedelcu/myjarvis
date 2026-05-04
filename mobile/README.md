# J.A.R.V.I.S. Mobile (Phase 1 — Flutter)

Companion app: dashboard + remote text control over Tailscale.

## First-time setup

1. **Install Flutter** on your dev machine: <https://docs.flutter.dev/get-started/install>
2. **Generate platform folders** (this directory ships only Dart sources + `pubspec.yaml`):

   ```bash
   cd mobile
   flutter create . --project-name jarvis_mobile --platforms=android,ios
   flutter pub get
   ```

3. **Install Tailscale** on your PC (`https://tailscale.com/download/windows`) and on your phone (Play Store / App Store). Join the same tailnet. Note the PC's Tailscale IP (e.g. `100.x.x.x`).

4. **Generate a mobile API key** on the PC:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   Paste it into `config.yaml`:

   ```yaml
   apis:
     mobile:
       api_key: "PASTE_HERE"
   ```

   Restart Jarvis (`python main.py`).

5. **Smoke test from a terminal** before launching the app:

   ```bash
   curl http://100.x.x.x:9000/api/mobile/health
   curl -H "Authorization: Bearer YOUR_KEY" \
        http://100.x.x.x:9000/api/mobile/dashboard
   ```

6. **Run the app** on a connected phone:

   ```bash
   flutter run
   ```

   On first launch enter `http://100.x.x.x:9000` and the API key. Credentials are stored in the device keychain.

## What works

**Phase 1 — text remote**
- Live dashboard cards (system, weather, calendar, emails, Spotify, lights), 30s refresh + pull-to-refresh
- "Ask" screen — text in → SSE-streamed brain reply, optional `Speak on PC` toggle
- EN ↔ RO language switch
- Tailscale-only connectivity (no port forwarding required)

**Phase 2 — voice on phone**
- Hold-to-talk mic FAB on the dashboard → `Voice` screen
- Records 16 kHz mono WAV on the phone
- Pipeline: `/api/mobile/transcribe` → `/api/mobile/ask` (SSE) → `/api/mobile/synthesize` → playback on phone speaker
- Optional `Also speak on PC` toggle

### Required permissions

After running `flutter create .`, add these once:

**Android** — `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
```

If your PC server uses plain HTTP (Tailscale magic IP, no TLS), also add to the `<application>` tag:

```xml
android:usesCleartextTraffic="true"
```

**iOS** — `ios/Runner/Info.plist`:

```xml
<key>NSMicrophoneUsageDescription</key>
<string>Jarvis needs the microphone to capture voice commands.</string>
<key>NSAppTransportSecurity</key>
<dict>
  <key>NSAllowsArbitraryLoads</key>
  <true/>
</dict>
```

## Coming next

- Phase 3: FCM push notifications
- Phase 4: standalone (lite) mode when PC offline
