import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:video_compress/video_compress.dart';

/// Compress before sending; keep the user's recording untouched.
class VideoUpload {
  static Future<File> prepare(File original) async {
    if (![
      TargetPlatform.android,
      TargetPlatform.iOS,
      TargetPlatform.macOS,
    ].contains(defaultTargetPlatform)) {
      throw Exception(
        'Video compression is supported on Android and iOS. Use the website on this device.',
      );
    }
    final info = await VideoCompress.compressVideo(
      original.path,
      quality: VideoQuality.Res1920x1080Quality,
      frameRate: 30,
      includeAudio: true,
      deleteOrigin: false,
    );
    final result = info?.file;
    if (result == null || !await result.exists()) {
      throw Exception(
        'Unable to prepare this video. Please try a different recording.',
      );
    }
    if (await result.length() > 50 * 1024 * 1024) {
      if (result.path != original.path) await result.delete();
      throw Exception(
        'The compressed video is over 50 MB. Please use a shorter recording.',
      );
    }
    return result;
  }
}
