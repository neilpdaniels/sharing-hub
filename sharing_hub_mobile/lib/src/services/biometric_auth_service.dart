import 'package:local_auth/local_auth.dart';

class BiometricAuthService {
  BiometricAuthService({LocalAuthentication? localAuthentication})
      : _localAuthentication = localAuthentication ?? LocalAuthentication();

  final LocalAuthentication _localAuthentication;

  Future<bool> isAvailable() async {
    try {
      final deviceSupported = await _localAuthentication.isDeviceSupported();
      final canCheckBiometrics = await _localAuthentication.canCheckBiometrics;
      final biometrics = await _localAuthentication.getAvailableBiometrics();
      return deviceSupported && canCheckBiometrics && biometrics.isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  Future<bool> authenticate() async {
    try {
      return await _localAuthentication.authenticate(
        localizedReason: 'Unlock Sharing Hub',
        options: const AuthenticationOptions(
          biometricOnly: false,
          stickyAuth: true,
        ),
      );
    } catch (_) {
      return false;
    }
  }
}