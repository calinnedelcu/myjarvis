// Demo build stub — the cloud APK strips `record`, `just_audio` and
// `path_provider` so the build doesn't depend on plugins with broken
// gradle bindings. The full pipeline lives at this path in master once
// you `flutter pub get` on the dev machine with those packages restored.

import 'dart:io';
import 'dart:typed_data';

import 'jarvis_api.dart';

class VoicePipeline {
  VoicePipeline(this._api);
  // ignore: unused_field
  final JarvisApi _api;

  Future<bool> ensurePermission() async => false;

  Future<void> startRecording() async {
    throw _stubError();
  }

  Future<File?> stopRecording() async => null;

  Future<void> cancel() async {}

  Future<void> runTurn({
    required File wavFile,
    required String language,
    required bool playOnPc,
    required void Function(String transcript) onTranscript,
    required void Function(String chunk) onReplyChunk,
    required void Function() onReplyDone,
    required void Function(Uint8List wav) onAudioReady,
  }) async {
    onReplyChunk(_stubError().toString());
    onReplyDone();
  }

  Future<void> dispose() async {}

  Exception _stubError() => Exception(
        'Voice not built into this APK. Restore record + just_audio in '
        'pubspec.yaml and rebuild on the dev machine.',
      );
}
