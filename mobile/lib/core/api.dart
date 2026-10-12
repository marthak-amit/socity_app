import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../state/auth.dart';
import 'config.dart';
import 'models.dart';

class ApiError implements Exception {
  ApiError(this.status, this.code, this.message, [this.extra = const {}]);
  final int status;
  final String code, message;
  final Map<String, dynamic> extra;
  bool get isNetwork => status == 0;
  @override
  String toString() => 'ApiError($status, $code): $message';
}

final httpClientProvider = Provider<http.Client>((ref) => http.Client());
final apiProvider = Provider<ApiClient>((ref) => ApiClient(ref, ref.watch(httpClientProvider)));

/// JSON-over-HTTP client with bearer auth and single-flight refresh-token rotation.
class ApiClient {
  ApiClient(this._ref, this._http);
  final Ref _ref;
  final http.Client _http;
  Future<bool>? _refreshing;

  Uri _uri(String path, Map<String, dynamic>? query) {
    final q = <String, String>{};
    query?.forEach((k, v) {
      if (v != null && '$v'.isNotEmpty) q[k] = '$v';
    });
    final base = Uri.parse('${apiBase()}$path');
    return q.isEmpty ? base : base.replace(queryParameters: {...base.queryParameters, ...q});
  }

  Future<bool> _refresh() async {
    final auth = _ref.read(authProvider.notifier);
    final token = _ref.read(authProvider).refreshToken;
    if (token == null) return false;
    try {
      final res = await _http.post(_uri('/auth/refresh', null),
          headers: {'Content-Type': 'application/json'}, body: jsonEncode({'refresh_token': token}));
      if (res.statusCode == 401) {
        await auth.logout(); // refresh token rejected → really signed out
        return false;
      }
      if (res.statusCode != 200) return false;
      final j = jsonDecode(res.body) as Json;
      await auth.setSession(j['access_token'], j['refresh_token'], User.fromJson(j['user']));
      return true;
    } catch (_) {
      return false; // offline: keep the session
    }
  }

  Future<http.Response> _send(String method, String path, Map<String, dynamic>? query, Object? body, bool auth) {
    final headers = <String, String>{'Accept': 'application/json'};
    if (body != null) headers['Content-Type'] = 'application/json';
    final token = _ref.read(authProvider).accessToken;
    if (auth && token != null) headers['Authorization'] = 'Bearer $token';
    final req = http.Request(method, _uri(path, query))..headers.addAll(headers);
    if (body != null) req.body = jsonEncode(body);
    return _http.send(req).then(http.Response.fromStream).timeout(const Duration(seconds: 30));
  }

  Future<dynamic> request(String method, String path, {Map<String, dynamic>? query, Object? body, bool auth = true}) async {
    http.Response res;
    try {
      res = await _send(method, path, query, body, auth);
    } on Object {
      throw ApiError(0, 'network_error', 'No connection. Check your internet and try again.');
    }
    if (res.statusCode == 401 && auth) {
      _refreshing ??= _refresh().whenComplete(() => _refreshing = null);
      if (await _refreshing!) {
        try {
          res = await _send(method, path, query, body, auth);
        } on Object {
          throw ApiError(0, 'network_error', 'No connection. Check your internet and try again.');
        }
      }
    }
    final text = utf8.decode(res.bodyBytes);
    dynamic data;
    if (text.isNotEmpty) {
      try {
        data = jsonDecode(text);
      } catch (_) {}
    }
    if (res.statusCode >= 400) {
      final d = data is Map ? data['detail'] : null;
      if (d is Map && d['code'] != null) {
        throw ApiError(res.statusCode, '${d['code']}', '${d['message'] ?? d['code']}', Map<String, dynamic>.from(d));
      }
      throw ApiError(res.statusCode, 'http_error', d is String ? d : 'Request failed (${res.statusCode})');
    }
    return data;
  }

  Future<Json> getJson(String path, {Map<String, dynamic>? query}) async => (await request('GET', path, query: query)) as Json;
  Future<List<dynamic>> getList(String path, {Map<String, dynamic>? query}) async => (await request('GET', path, query: query)) as List;
  Future<Json> post(String path, [Object? body]) async => ((await request('POST', path, body: body ?? <String, dynamic>{})) ?? {}) as Json;
  Future<Json> patch(String path, Object body) async => (await request('PATCH', path, body: body)) as Json;
  Future<Json> delete(String path, [Object? body]) async => ((await request('DELETE', path, body: body)) ?? {}) as Json;

  Future<PageData<T>> page<T>(String path, T Function(Json) f, {Map<String, dynamic>? query, int limit = 20, int offset = 0}) async =>
      PageData.fromJson(await getJson(path, query: {...?query, 'limit': limit, 'offset': offset}), f);

  /// Presign → PUT bytes → returns the `upload_id` to hand to the endpoint that uses the file.
  Future<String> uploadImage({String? societyId, required String purpose, required Uint8List bytes, String? mime}) async {
    final contentType = (mime != null && mime.startsWith('image/')) ? mime : 'image/jpeg';
    final presign = Presign.fromJson(await post(
      purpose == 'avatar' ? '/me/avatar-upload' : '/societies/$societyId/uploads/presign',
      {'purpose': purpose, 'content_type': contentType, 'size': bytes.length},
    ));
    http.Response res;
    try {
      res = await _http.put(Uri.parse(presign.url), headers: presign.headers, body: bytes);
    } on Object {
      throw ApiError(0, 'network_error', 'No connection. Check your internet and try again.');
    }
    if (res.statusCode >= 300) throw ApiError(res.statusCode, 'upload_failed', 'Photo upload failed. Please try again.');
    return presign.uploadId;
  }

  /// Authenticated binary download (CSV / XLSX exports).
  Future<Uint8List> download(String path) async {
    http.Response res;
    try {
      res = await _send('GET', path, null, null, true);
    } on Object {
      throw ApiError(0, 'network_error', 'No connection. Check your internet and try again.');
    }
    if (res.statusCode >= 400) throw ApiError(res.statusCode, 'export_failed', 'Export failed');
    return res.bodyBytes;
  }
}
