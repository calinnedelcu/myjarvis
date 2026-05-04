import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import 'storage.dart';

/// Streamed event from /api/mobile/ask SSE endpoint.
class AskEvent {
  AskEvent.chunk(this.text)
      : type = AskEventType.chunk,
        message = null;
  AskEvent.done()
      : type = AskEventType.done,
        text = null,
        message = null;
  AskEvent.error(this.message)
      : type = AskEventType.error,
        text = null;

  final AskEventType type;
  final String? text;
  final String? message;
}

enum AskEventType { chunk, done, error }

class JarvisApi {
  JarvisApi(this._creds)
      : _dio = Dio(BaseOptions(
          baseUrl: _creds.baseUrl,
          connectTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 30),
          headers: {
            'Authorization': 'Bearer ${_creds.apiKey}',
            'Accept': 'application/json',
          },
        ));

  final JarvisCredentials _creds;
  final Dio _dio;

  /// Pings /api/mobile/health. Returns true on 200.
  Future<bool> health() async {
    try {
      final resp = await _dio.get(
        '/api/mobile/health',
        options: Options(
          headers: {'Authorization': null},
          validateStatus: (s) => s != null && s < 500,
        ),
      );
      return resp.statusCode == 200 && resp.data is Map && resp.data['ok'] == true;
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>> dashboard() async {
    final resp = await _dio.get<Map<String, dynamic>>('/api/mobile/dashboard');
    return resp.data ?? {};
  }

  /// Register an FCM token so the PC can push notifications to this device.
  Future<void> registerDevice({
    required String token,
    String platform = '',
    String label = '',
  }) async {
    await _dio.post(
      '/api/mobile/devices/register',
      data: {'token': token, 'platform': platform, 'label': label},
    );
  }

  Future<void> unregisterDevice(String token) async {
    await _dio.delete('/api/mobile/devices/$token');
  }

  /// Upload a WAV file and return Whisper transcript.
  Future<({String text, String language})> transcribe({
    required File wavFile,
    String language = 'en',
  }) async {
    final form = FormData.fromMap({
      'audio': await MultipartFile.fromFile(
        wavFile.path,
        filename: 'speech.wav',
        contentType: DioMediaType('audio', 'wav'),
      ),
      'language': language,
    });
    final resp = await _dio.post<Map<String, dynamic>>(
      '/api/mobile/transcribe',
      data: form,
      options: Options(
        sendTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 30),
      ),
    );
    final data = resp.data ?? {};
    return (
      text: (data['text'] as String? ?? '').trim(),
      language: data['language'] as String? ?? language,
    );
  }

  /// Render text via PC TTS, return WAV bytes ready for playback.
  Future<Uint8List> synthesize({
    required String text,
    String language = 'en',
  }) async {
    final resp = await _dio.post<List<int>>(
      '/api/mobile/synthesize',
      data: {'text': text, 'language': language},
      options: Options(
        responseType: ResponseType.bytes,
        receiveTimeout: const Duration(seconds: 30),
      ),
    );
    return Uint8List.fromList(resp.data ?? const []);
  }

  /// Stream brain reply token-by-token via SSE.
  Stream<AskEvent> ask({
    required String text,
    String language = 'en',
    bool playOnPc = false,
  }) async* {
    final controller = StreamController<AskEvent>();
    final cancelToken = CancelToken();

    unawaited(() async {
      try {
        final response = await _dio.post<ResponseBody>(
          '/api/mobile/ask',
          data: {'text': text, 'language': language, 'play_on_pc': playOnPc},
          options: Options(
            responseType: ResponseType.stream,
            headers: {'Accept': 'text/event-stream'},
          ),
          cancelToken: cancelToken,
        );

        final body = response.data;
        if (body == null) {
          controller.add(AskEvent.error('Empty response'));
          await controller.close();
          return;
        }

        final buffer = StringBuffer();
        await for (final chunk in body.stream) {
          buffer.write(utf8.decode(chunk, allowMalformed: true));
          while (true) {
            final raw = buffer.toString();
            final idx = raw.indexOf('\n\n');
            if (idx < 0) break;
            final event = raw.substring(0, idx).trim();
            buffer
              ..clear()
              ..write(raw.substring(idx + 2));
            if (!event.startsWith('data:')) continue;
            final payload = event.substring(5).trim();
            try {
              final json = jsonDecode(payload) as Map<String, dynamic>;
              switch (json['type']) {
                case 'chunk':
                  controller.add(AskEvent.chunk(json['text'] as String? ?? ''));
                  break;
                case 'done':
                  controller.add(AskEvent.done());
                  break;
                case 'error':
                  controller.add(
                    AskEvent.error(json['message'] as String? ?? 'unknown'),
                  );
                  break;
              }
            } catch (_) {
              // skip malformed event
            }
          }
        }
      } catch (e) {
        controller.add(AskEvent.error(e.toString()));
      } finally {
        await controller.close();
      }
    }());

    yield* controller.stream;
  }
}
