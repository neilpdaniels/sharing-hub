import 'dart:convert';

import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;

class LocationSelection {
  const LocationSelection({
    required this.displayLabel,
    required this.searchQuery,
  });

  final String displayLabel;
  final String searchQuery;
}

class LocationService {
  static Future<LocationSelection> getCurrentLocationSelection() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw Exception('Location services are disabled on this device.');
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.denied) {
      throw Exception('Location permission denied.');
    }

    if (permission == LocationPermission.deniedForever) {
      throw Exception(
        'Location permission permanently denied. Enable it in settings.',
      );
    }

    final position = await Geolocator.getCurrentPosition(
      desiredAccuracy: LocationAccuracy.high,
    );

    final latitude = position.latitude.toStringAsFixed(5);
    final longitude = position.longitude.toStringAsFixed(5);
    final fallbackQuery = '$latitude, $longitude';

    final placemark = await _reverseGeocode(
      position.latitude,
      position.longitude,
    );
    if (placemark != null) {
      final query = placemark.postcode?.trim().isNotEmpty == true
          ? placemark.postcode!.trim()
          : placemark.locality?.trim().isNotEmpty == true
          ? placemark.locality!.trim()
          : fallbackQuery;
      final display = placemark.displayLabel;
      return LocationSelection(
        displayLabel: display.isEmpty ? query : display,
        searchQuery: query,
      );
    }

    return LocationSelection(
      displayLabel: fallbackQuery,
      searchQuery: fallbackQuery,
    );
  }

  static Future<_ReverseGeocodeResult?> _reverseGeocode(
    double latitude,
    double longitude,
  ) async {
    final uri = Uri.https('nominatim.openstreetmap.org', '/reverse', {
      'format': 'jsonv2',
      'lat': latitude.toString(),
      'lon': longitude.toString(),
      'zoom': '16',
      'addressdetails': '1',
    });

    try {
      final response = await http.get(
        uri,
        headers: const {
          'Accept': 'application/json',
          'User-Agent': 'rentalution-mobile/1.0',
        },
      );
      if (response.statusCode < 200 || response.statusCode >= 300) {
        return null;
      }

      final parsed = jsonDecode(response.body);
      if (parsed is! Map<String, dynamic>) {
        return null;
      }

      final address = parsed['address'];
      if (address is! Map<String, dynamic>) {
        return null;
      }

      final postcode = (address['postcode'] as String? ?? '').trim();
      final locality =
          (address['city'] as String? ??
                  address['town'] as String? ??
                  address['village'] as String? ??
                  address['suburb'] as String? ??
                  '')
              .trim();

      final displayParts = <String>[];
      if (locality.isNotEmpty) {
        displayParts.add(locality);
      }
      if (postcode.isNotEmpty) {
        displayParts.add(postcode);
      }

      return _ReverseGeocodeResult(
        postcode: postcode.isEmpty ? null : postcode,
        locality: locality.isEmpty ? null : locality,
        displayLabel: displayParts.join(', '),
      );
    } catch (_) {
      return null;
    }
  }
}

class _ReverseGeocodeResult {
  const _ReverseGeocodeResult({
    required this.postcode,
    required this.locality,
    required this.displayLabel,
  });

  final String? postcode;
  final String? locality;
  final String displayLabel;
}
