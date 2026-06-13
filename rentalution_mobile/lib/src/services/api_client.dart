import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

class ApiClient {
  ApiClient({
    required this.baseUrl,
    http.Client? client,
  }) : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;
  static const Duration _requestTimeout = Duration(seconds: 20);

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
    final response = await _client.post(
      _buildUri(path, queryParameters: queryParameters),
      headers: _headers(accessToken: accessToken),
      body: jsonEncode(body),
    ).timeout(_requestTimeout);
    return _decodeObject(response);
  }

  Future<Map<String, dynamic>> patchJson(
    String path,
    Map<String, dynamic> body, {
    String? accessToken,
    Map<String, String>? queryParameters,
  }) async {
    final response = await _client.patch(
      _buildUri(path, queryParameters: queryParameters),
      headers: _headers(accessToken: accessToken),
      body: jsonEncode(body),
    ).timeout(_requestTimeout);
    return _decodeObject(response);
  }

  Future<List<dynamic>> getJsonList(
    String path, {
    String? accessToken,
    Map<String, String>? queryParameters,
  }) async {
    final response = await _client.get(
      _buildUri(path, queryParameters: queryParameters),
      headers: _headers(accessToken: accessToken),
    ).timeout(_requestTimeout);
    return _decodeList(response);
  }

  Future<Map<String, dynamic>> getJsonObject(
    String path, {
    String? accessToken,
    Map<String, String>? queryParameters,
  }) async {
    final response = await _client.get(
      _buildUri(path, queryParameters: queryParameters),
      headers: _headers(accessToken: accessToken),
    ).timeout(_requestTimeout);
    return _decodeObject(response);
  }

  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required String accessToken,
    Map<String, String> fields = const {},
    List<File> imageFiles = const [],
    List<File> videoFiles = const [],
  }) async {
    final request = http.MultipartRequest('POST', _buildUri(path));
    request.headers.addAll(_headers(accessToken: accessToken, isJson: false));
    request.fields.addAll(fields);

    for (final file in imageFiles) {
      request.files.add(await http.MultipartFile.fromPath('images', file.path));
    }

    for (final file in videoFiles) {
      request.files.add(await http.MultipartFile.fromPath('videos', file.path));
    }

    final streamed = await request.send().timeout(_requestTimeout);
    final response = await http.Response.fromStream(streamed);
    return _decodeObject(response);
  }

  Map<String, String> _headers({String? accessToken, bool isJson = true}) {
    final headers = <String, String>{
      'Accept': 'application/json',
    };

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
