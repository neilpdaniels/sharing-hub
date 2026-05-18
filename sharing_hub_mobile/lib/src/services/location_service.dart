import 'package:geocoding/geocoding.dart';
import 'package:geolocator/geolocator.dart';

class LocationService {
  static Future<String> getCurrentLocationLabel() async {
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
      throw Exception('Location permission permanently denied. Enable it in settings.');
    }

    final position = await Geolocator.getCurrentPosition(
      desiredAccuracy: LocationAccuracy.high,
    );

    try {
      final placemarks = await placemarkFromCoordinates(
        position.latitude,
        position.longitude,
      );

      if (placemarks.isNotEmpty) {
        final place = placemarks.first;
        final candidates = <String>[
          (place.postalCode ?? '').trim(),
          (place.locality ?? '').trim(),
          (place.subAdministrativeArea ?? '').trim(),
          (place.administrativeArea ?? '').trim(),
        ].where((value) => value.isNotEmpty).toList(growable: false);

        if (candidates.isNotEmpty) {
          return candidates.join(', ');
        }
      }
    } catch (_) {
      // Fallback below if reverse geocoding fails.
    }

    return '${position.latitude.toStringAsFixed(5)}, ${position.longitude.toStringAsFixed(5)}';
  }
}