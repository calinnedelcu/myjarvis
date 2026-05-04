import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import 'jarvis_api.dart';

/// Orchestrates a press-and-hold voice turn:
///   record WAV → POST /transcribe → POST /ask (collect text) →
///   POST /synthesize → play on phone speaker.
class VoicePipeline {
  VoicePipeline(this._api);
  final JarvisApi _api;

  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();

  String? _path;
  bool _recording = false;

  Future<bool> ensurePermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  Future<void> startRecording() async {
    if (_recording) return;
    if (!await ensurePermission()) {
      throw Exception('Microphone permission denied.');
    }
    final dir = await getTemporaryDirectory();
    _path =
        '${dir.path}/jarvis_${DateTime.now().millisecondsSinceEpoch}.wav';
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.wav,
        sampleRate: 16000,
        numChannels: 1,
      ),
      path: _path!,
    );
    _recording = true;
  }

  /// Stops recording and returns the captured WAV file (or null if too short).
  Future<File?> stopRecording() async {
    if (!_recording) return null;
    final path = await _recorder.stop();
    _recording = false;
    if (path == null) return null;
    final file = File(path);
    if (!await file.exists()) return null;
    final size = await file.length();
    // Tiny clips are usually accidental taps — discard.
    if (size < 4096) {
      try {
        await file.delete();
      } catch (_) {}
      return null;
    }
    return file;
  }

  Future<void> cancel() async {
    if (_recording) {
      try {
        await _recorder.stop();
      } catch (_) {}
      _recording = false;
    }
    if (_path != null) {
      try {
        await File(_path!).delete();
      } catch (_) {}
      _path = null;
    }
  }

  /// Run the full pipeline. Calls back at each phase so UI can update.
  Future<void> runTurn({
    required File wavFile,
    required String language,
    required bool playOnPc,
    required void Function(String transcript) onTranscript,
    required void Function(String chunk) onReplyChunk,
    required void Function() onReplyDone,
    required void Function(Uint8List wav) onAudioReady,
  }) async {
    final t = await _api.transcribe(wavFile: wavFile, language: language);
    onTranscript(t.text);
    if (t.text.isEmpty) {
      onReplyDone();
      return;
    }

    final replyBuf = StringBuffer();
    await for (final ev in _api.ask(
      text: t.text,
      language: t.language,
      playOnPc: playOnPc,
    )) {
      if (ev.type == AskEventType.chunk) {
        replyBuf.write(ev.text ?? '');
        onReplyChunk(ev.text ?? '');
      } else if (ev.type == AskEventType.error) {
        onReplyChunk('\n[error: ${ev.message}]');
        onReplyDone();
        return;
      }
    }
    onReplyDone();

    final reply = replyBuf.toString().trim();
    if (reply.isEmpty) return;

    final wav = await _api.synthesize(text: reply, language: t.language);
    if (wav.isNotEmpty) {
      onAudioReady(wav);
      await _playWav(wav);
    }
  }

  Future<void> _playWav(Uint8List wav) async {
    final dir = await getTemporaryDirectory();
    final outPath =
        '${dir.path}/jarvis_reply_${DateTime.now().millisecondsSinceEpoch}.wav';
    final file = File(outPath);
    await file.writeAsBytes(wav, flush: true);
    await _player.setFilePath(outPath);
    await _player.play();
  }

  Future<void> dispose() async {
    await cancel();
    await _player.dispose();
    await _recorder.dispose();
  }
}
