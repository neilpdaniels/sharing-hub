import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:video_compress/video_compress.dart';
import 'package:rentalution_mobile/src/services/video_upload.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('video_compress');
  late Directory directory;
  late File original;
  late File compressed;

  setUp(() async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    directory = await Directory.systemTemp.createTemp('rental-video-test');
    original = await File(
      '${directory.path}/original.mp4',
    ).writeAsString('original recording');
    compressed = await File(
      '${directory.path}/compressed.mp4',
    ).writeAsString('compressed upload');
  });
  tearDown(() async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
    VideoCompress.dispose();
    debugDefaultTargetPlatformOverride = null;
    await directory.delete(recursive: true);
  });

  test(
    'uses native 1080p compression with audio and preserves the recording',
    () async {
      Map<dynamic, dynamic>? arguments;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            arguments = call.arguments as Map<dynamic, dynamic>;
            return jsonEncode({'path': compressed.path});
          });
      final file = await VideoUpload.prepare(original);
      expect(await file.readAsString(), 'compressed upload');
      expect(await original.readAsString(), 'original recording');
      expect(arguments!['quality'], VideoQuality.Res1920x1080Quality.index);
      expect(arguments!['includeAudio'], true);
      expect(arguments!['deleteOrigin'], false);
      expect(arguments!['frameRate'], 30);
    },
  );

  test(
    'does not silently upload the original when compression fails',
    () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async => null);
      await expectLater(VideoUpload.prepare(original), throwsException);
      expect(await original.exists(), true);
    },
  );
}
