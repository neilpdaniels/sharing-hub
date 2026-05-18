class UserSummary {
  UserSummary({
    required this.id,
    required this.username,
    required this.email,
    required this.firstName,
    required this.lastName,
  });

  final int id;
  final String username;
  final String email;
  final String firstName;
  final String lastName;

  factory UserSummary.fromJson(Map<String, dynamic> json) {
    return UserSummary(
      id: json['id'] as int,
      username: json['username'] as String? ?? '',
      email: json['email'] as String? ?? '',
      firstName: json['first_name'] as String? ?? '',
      lastName: json['last_name'] as String? ?? '',
    );
  }
}

class ProfileSummary {
  ProfileSummary({
    required this.emailConfirmed,
    required this.mobileVerified,
    required this.addressVerified,
    required this.postcode,
  });

  final bool emailConfirmed;
  final bool mobileVerified;
  final bool addressVerified;
  final String postcode;

  factory ProfileSummary.fromJson(Map<String, dynamic> json) {
    return ProfileSummary(
      emailConfirmed: json['email_confirmed'] as bool? ?? false,
      mobileVerified: json['mobile_verified'] as bool? ?? false,
      addressVerified: json['address_verified'] as bool? ?? false,
      postcode: json['postcode'] as String? ?? '',
    );
  }
}

class AuthSession {
  AuthSession({
    required this.accessToken,
    required this.refreshToken,
    required this.user,
    this.profile,
  });

  final String accessToken;
  final String refreshToken;
  final UserSummary user;
  final ProfileSummary? profile;

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    final profileJson = json['profile'];
    return AuthSession(
      accessToken: json['access'] as String,
      refreshToken: json['refresh'] as String,
      user: UserSummary.fromJson(json['user'] as Map<String, dynamic>),
      profile: profileJson is Map<String, dynamic>
          ? ProfileSummary.fromJson(profileJson)
          : null,
    );
  }
}
