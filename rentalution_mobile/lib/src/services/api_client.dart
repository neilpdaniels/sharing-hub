import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'video_upload.dart';

class _ProgressMultipartRequest extends http.MultipartRequest {
  _ProgressMultipartRequest(super.method, super.url, {this.onProgress});

  final void Function(int sentBytes, int totalBytes)? onProgress;

  @override
  http.ByteStream finalize() {
    final stream = super.finalize();
    final total = contentLength;
    var sent = 0;
    return http.ByteStream(
      stream.transform(
        StreamTransformer<List<int>, List<int>>.fromHandlers(
          handleData: (chunk, sink) {
            sent += chunk.length;
            onProgress?.call(sent, total);
            sink.add(chunk);
          },
        ),
      ),
    );
  }
}

class ApiClient {
  ApiClient({required this.baseUrl, http.Client? client})
    : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;
  static const Duration _requestTimeout = Duration(seconds: 20);
  // A dead local development server should not leave Browse spinning for 20s.
  // Keep the longer timeout for writes and video uploads.
  static const Duration _readRequestTimeout = Duration(seconds: 8);

  Uri _buildUri(String path, {Map<String, String>? queryParameters}) {
    final baseUri = Uri.parse('$baseUrl$path');
    if (queryParameters == null || queryParameters.isEmpty) {
      return baseUri;
    }
    return baseUri.replace(queryParameters: queryParameters);
  }

  Future<Map<String, dynamic>> postJson(
    String path,
    Map<String, dynamic> body, {
    String? accessToken,
    Map<String, String>? queryParameters,
  }) async {
    final response = await _client
        .post(
          _buildUri(path, queryParameters: queryParameters),
          headers: _headers(accessToken: accessToken),
          body: jsonEncode(body),
        )
        .timeout(_requestTimeout);
    return _decodeObject(response);
  }

  Future<Map<String, dynamic>> patchJson(
    String path,
    Map<String, dynamic> body, {
    String? accessToken,
    Map<String, String>? queryParameters,
  }) async {
    final response = await _client
        .patch(
          _buildUri(path, queryParameters: queryParameters),
          headers: _headers(accessToken: accessToken),
          body: jsonEncode(body),
        )
        .timeout(_requestTimeout);
    return _decodeObject(response);
  }

  Future<List<dynamic>> getJsonList(
    String path, {
    String? accessToken,
    Map<String, String>? queryParameters,
  }) async {
    final response = await _client
        .get(
          _buildUri(path, queryParameters: queryParameters),
          headers: _headers(accessToken: accessToken),
        )
        .timeout(_readRequestTimeout);
    return _decodeList(response);
  }

  Future<({List<dynamic>? data, String? etag})> getConditionalJsonList(
    String path, {
    String? etag,
    Map<String, String>? queryParameters,
  }) async {
    final headers = _headers();
    if (etag != null) {
      headers['If-None-Match'] = etag;
    }
    final response = await _client
        .get(
          _buildUri(path, queryParameters: queryParameters),
          headers: headers,
        )
        .timeout(_readRequestTimeout);
    if (response.statusCode == 304 && etag != null) {
      return (data: null, etag: response.headers['etag'] ?? etag);
    }
    return (data: _decodeList(response), etag: response.headers['etag']);
  }

  Future<Map<String, dynamic>> getJsonObject(
    String path, {
    String? accessToken,
    Map<String, String>? queryParameters,
  }) async {
    final response = await _client
        .get(
          _buildUri(path, queryParameters: queryParameters),
          headers: _headers(accessToken: accessToken),
        )
        .timeout(_readRequestTimeout);
    return _decodeObject(response);
  }

  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required String accessToken,
    Map<String, String> fields = const {},
    List<File> imageFiles = const [],
    List<File> videoFiles = const [],
    void Function(int sentBytes, int totalBytes)? onUploadProgress,
  }) async {
    final request = _ProgressMultipartRequest(
      'POST',
      _buildUri(path),
      onProgress: onUploadProgress,
    );
    request.headers.addAll(_headers(accessToken: accessToken, isJson: false));
    request.fields.addAll(fields);

    for (final file in imageFiles) {
      request.files.add(await http.MultipartFile.fromPath('images', file.path));
    }

    final prepared = <File>[];
    try {
      for (final file in videoFiles) {
        final compressed = await VideoUpload.prepare(file);
        prepared.add(compressed);
        request.files.add(
          await http.MultipartFile.fromPath(
            'videos',
            compressed.path,
            contentType: MediaType('video', 'mp4'),
          ),
        );
      }
      final streamed = await request.send().timeout(_requestTimeout);
      final response = await http.Response.fromStream(streamed);
      return _decodeObject(response);
    } finally {
      for (final file in prepared) {
        if (!videoFiles.any((original) => original.path == file.path) &&
            await file.exists()) {
          await file.delete();
        }
      }
    }
  }

  Map<String, String> _headers({String? accessToken, bool isJson = true}) {
    final headers = <String, String>{'Accept': 'application/json'};

    if (isJson) {
      headers['Content-Type'] = 'application/json';
    }

    if (accessToken != null && accessToken.isNotEmpty) {
      headers['Authorization'] = 'Bearer $accessToken';
    }

    return headers;
  }

  Map<String, dynamic> _decodeObject(http.Response response) {
    final data = _decode(response);
    if (data is Map<String, dynamic>) {
      return data;
    }
    throw ApiException('Unexpected API response format.');
  }

  List<dynamic> _decodeList(http.Response response) {
    final data = _decode(response);
    if (data is List<dynamic>) {
      return data;
    }
    throw ApiException('Unexpected API response format.');
  }

  dynamic _decode(http.Response response) {
    final parsed = response.body.isEmpty ? null : jsonDecode(response.body);

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return parsed;
    }

    if (parsed is Map<String, dynamic>) {
      final detail = parsed['detail'];
      if (detail != null) {
        throw ApiException(detail.toString());
      }

      final nonFieldErrors = parsed['non_field_errors'];
      if (nonFieldErrors != null) {
        throw ApiException(nonFieldErrors.toString());
      }

      final error = parsed['error'];
      if (error != null) {
        throw ApiException(error.toString());
      }

      final message = parsed['message'];
      if (message != null) {
        throw ApiException(message.toString());
      }

      if (parsed.isNotEmpty) {
        throw ApiException(parsed.toString());
      }
    }

    throw ApiException('Request failed with status ${response.statusCode}.');
  }
}

class ApiException implements Exception {
  ApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

bool isNetworkError(Object error) {
  return error is SocketException ||
      error is TimeoutException ||
      error is http.ClientException;
}
