import 'dart:io';
import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:rentalution_mobile/src/services/api_client.dart';
import 'package:rentalution_mobile/src/services/catalog_repository.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test(
    'saved categories display before checksum check and survive a 304',
    () async {
      var calls = 0;
      final pending = Completer<http.Response>();
      ApiClient client() => ApiClient(
        baseUrl: 'https://example.test/api/v1',
        client: MockClient((request) async {
          calls++;
          if (calls == 1)
            return http.Response(
              '[{"slug":"tools","title":"Tools"}]',
              200,
              headers: {'etag': '"v1"'},
            );
          expect(request.headers['If-None-Match'], '"v1"');
          return pending.future;
        }),
      );
      await CatalogRepository(
        apiClient: client(),
      ).fetchCategories(parentSlug: 'top');
      final restarted = CatalogRepository(apiClient: client());
      final cached = await restarted.fetchCategories(parentSlug: 'top');
      expect(cached.single.title, 'Tools');
      expect(pending.isCompleted, isFalse);
      pending.complete(http.Response('', 304, headers: {'etag': '"v1"'}));
      await Future<void>.delayed(Duration.zero);
      expect(
        (await restarted.fetchCategories(parentSlug: 'top')).single.title,
        'Tools',
      );
      expect(calls, 2);
    },
  );

  test(
    'changed checksum refreshes cached tree with one bulk request',
    () async {
      final pending = Completer<http.Response>();
      final initial = CatalogRepository(
        apiClient: ApiClient(
          baseUrl: 'https://example.test',
          client: MockClient((request) async {
            expect(request.url.queryParameters['include_top'], 'true');
            return http.Response(
              '[{"slug":"tools","title":"Old"}]',
              200,
              headers: {'etag': '"v1"'},
            );
          }),
        ),
      );
      await initial.fetchAllCategories();
      final updated = CatalogRepository(
        apiClient: ApiClient(
          baseUrl: 'https://example.test',
          client: MockClient((request) async {
            expect(request.headers['If-None-Match'], '"v1"');
            return pending.future;
          }),
        ),
      );
      expect((await updated.fetchAllCategories()).single.title, 'Old');
      pending.complete(
        http.Response(
          '[{"slug":"tools","title":"New"}]',
          200,
          headers: {'etag': '"v2"'},
        ),
      );
      await Future<void>.delayed(Duration.zero);
      expect((await updated.fetchAllCategories()).single.title, 'New');
    },
  );

  test(
    'old snapshots remain available offline and are isolated by API server',
    () async {
      SharedPreferences.setMockInitialValues({
        'catalog_categories_v2::https://example.test::parent:top': jsonEncode({
          'etag': '"v1"',
          'data': [
            {'slug': 'tools', 'title': 'Tools'},
          ],
        }),
      });
      ApiClient offline(String server) => ApiClient(
        baseUrl: server,
        client: MockClient((_) async => throw const SocketException('Offline')),
      );
      final repository = CatalogRepository(
        apiClient: offline('https://example.test'),
      );
      expect(
        (await repository.fetchCategories(parentSlug: 'top')).single.title,
        'Tools',
      );
      await Future<void>.delayed(Duration.zero);
      expect(
        (await repository.fetchCategories(parentSlug: 'top')).single.title,
        'Tools',
      );
      await expectLater(
        CatalogRepository(
          apiClient: offline('https://other.test'),
        ).fetchCategories(parentSlug: 'top'),
        throwsA(isA<SocketException>()),
      );
    },
  );

  test(
    'preloaded tree supplies child categories without more requests',
    () async {
      var calls = 0;
      final repository = CatalogRepository(
        apiClient: ApiClient(
          baseUrl: 'https://example.test',
          client: MockClient((request) async {
            calls++;
            return http.Response(
              '[{"slug":"tools","parent_slug":"top"},{"slug":"drills","parent_slug":"tools"}]',
              200,
              headers: {'etag': '"tree"'},
            );
          }),
        ),
      );
      await repository.fetchAllCategories();
      expect(
        (await repository.fetchCategories(parentSlug: 'top')).single.slug,
        'tools',
      );
      expect(
        (await repository.fetchCategories(parentSlug: 'tools')).single.slug,
        'drills',
      );
      expect(await repository.fetchCategories(parentSlug: 'drills'), isEmpty);
      expect(calls, 1);
    },
  );

  for (final kind in ['categories', 'products', 'product detail']) {
    test(
      '$kind retries after a connection failure and caches success',
      () async {
        var requests = 0;
        final repository = CatalogRepository(
          apiClient: ApiClient(
            baseUrl: 'https://example.test/api/v1',
            client: MockClient((request) async {
              requests++;
              if (requests == 1) {
                throw const SocketException('Server unavailable');
              }
              return http.Response(kind == 'product detail' ? '{}' : '[]', 200);
            }),
          ),
        );

        Future<Object> fetch() {
          switch (kind) {
            case 'categories':
              return repository.fetchCategories(parentSlug: 'top');
            case 'products':
              return repository.fetchCategoryProducts(categorySlug: 'tools');
            default:
              return repository.fetchProductDetail(productSlug: 'drill');
          }
        }

        await expectLater(fetch(), throwsA(isA<SocketException>()));
        expect(requests, 1);
        final recovered = await fetch();
        expect(requests, 2);
        expect(await fetch(), same(recovered));
        expect(requests, 2);
      },
    );
  }
}
