import '../models/auth_models.dart';
import '../storage/token_store.dart';
import 'api_client.dart';

class AuthRepository {
  AuthRepository({
    required ApiClient apiClient,
    required ApiClient websiteApiClient,
    required TokenStore tokenStore,
  })
    : _apiClient = apiClient,
      _websiteApiClient = websiteApiClient,
      _tokenStore = tokenStore;

  final ApiClient _apiClient;
  final ApiClient _websiteApiClient;
  final TokenStore _tokenStore;

  Future<AuthSession> login({
    required String login,
    required String password,
  }) async {
    final json = await _apiClient.postJson('/auth/login/', {
      'login': login,
      'password': password,
    });

    final session = AuthSession.fromJson(json);

    await _tokenStore.saveTokens(
      accessToken: session.accessToken,
      refreshToken: session.refreshToken,
    );

    return session;
  }

  Future<String> registerStart({
    required String firstName,
    required String lastName,
    required String username,
    required String email,
    required String avatarPreset,
    required String dateOfBirth,
    required String mobileNumber,
    required String addressLine1,
    required String town,
    required String postcode,
    String houseNameNumber = '',
    String addressLine2 = '',
    String county = '',
    String avatarEyes = 'default',
    String avatarMouth = 'smile',
    String avatarClothing = 'hoodie',
    String avatarAccessories = 'none',
    String avatarHairLength = 'short',
    int avatarSkinTone = 4,
    int avatarFacialHair = 25,
  }) async {
    final json = await _apiClient.postJson('/auth/register/start/', {
      'first_name': firstName,
      'last_name': lastName,
      'username': username,
      'email': email,
      'avatar_preset': avatarPreset,
      'date_of_birth': dateOfBirth,
      'mobile_number': mobileNumber,
      'house_name_number': houseNameNumber,
      'address_line_1': addressLine1,
      'address_line_2': addressLine2,
      'town': town,
      'county': county,
      'postcode': postcode,
      'avatar_eyes': avatarEyes,
      'avatar_mouth': avatarMouth,
      'avatar_clothing': avatarClothing,
      'avatar_accessories': avatarAccessories,
      'avatar_hair_length': avatarHairLength,
      'avatar_skin_tone': avatarSkinTone.toString(),
      'avatar_facial_hair': avatarFacialHair,
    });

    return json['message'] as String? ?? 'Verification code sent.';
  }

  Future<String> registerResend({required String email}) async {
    final json = await _apiClient.postJson('/auth/register/resend/', {
      'email': email,
    });
    return json['message'] as String? ??
        'A new verification code has been sent.';
  }

  Future<(bool available, String? error)> checkUsername(
    String username,
  ) async {
    final json = await _websiteApiClient.getJsonObject(
      '/account/register/check-username/',
      queryParameters: {'username': username},
    );
    return (
      json['available'] as bool? ?? false,
      json['error'] as String?,
    );
  }

  Future<String> requestPasswordReset({required String email}) async {
    final json = await _apiClient.postJson('/auth/password-reset/', {
      'email': email,
    });
    return json['message'] as String? ??
        'If the email exists, a reset link has been sent.';
  }

  Future<String> changePassword({
    required String oldPassword,
    required String newPassword,
  }) async {
    final json = await _apiClient.postJson('/auth/password-change/', {
      'old_password': oldPassword,
      'new_password': newPassword,
    });
    return json['message'] as String? ?? 'Password updated.';
  }

  Future<AuthSession> registerVerify({
    required String email,
    required String verificationCode,
    required String password,
  }) async {
    final json = await _apiClient.postJson('/auth/register/verify/', {
      'email': email,
      'verification_code': verificationCode,
      'password': password,
      'password2': password,
    });

    final session = AuthSession.fromJson(json);
    await _tokenStore.saveTokens(
      accessToken: session.accessToken,
      refreshToken: session.refreshToken,
    );
    return session;
  }

  Future<AuthSession?> restoreSession() async {
    final access = await _tokenStore.getAccessToken();
    final refresh = await _tokenStore.getRefreshToken();

    if (access == null || refresh == null) {
      return null;
    }

    try {
      final me = await _apiClient.getJsonObject(
        '/auth/me/',
        accessToken: access,
      );
      return AuthSession(
        accessToken: access,
        refreshToken: refresh,
        user: UserSummary.fromJson(me['user'] as Map<String, dynamic>),
        profile: me['profile'] is Map<String, dynamic>
            ? ProfileSummary.fromJson(me['profile'] as Map<String, dynamic>)
            : null,
      );
    } catch (_) {
      await _tokenStore.clear();
      return null;
    }
  }

  Future<void> logout() async {
    await _tokenStore.clear();
  }
}
