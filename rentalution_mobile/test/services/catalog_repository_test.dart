import 'dart:io';

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
