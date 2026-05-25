import 'dart:math';

import 'package:flutter/material.dart';

import '../models/auth_models.dart';
import '../services/auth_repository.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key, required this.authRepository});

  final AuthRepository authRepository;

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _startFormKey = GlobalKey<FormState>();
  final _verifyFormKey = GlobalKey<FormState>();

  final _firstNameController = TextEditingController();
  final _lastNameController = TextEditingController();
  final _usernameController = TextEditingController();
  final _emailController = TextEditingController();
  final _mobileController = TextEditingController();
  final _dobController = TextEditingController();
  final _houseNumberController = TextEditingController();
  final _addressLine1Controller = TextEditingController();
  final _addressLine2Controller = TextEditingController();
  final _townController = TextEditingController();
  final _countyController = TextEditingController();
  final _postcodeController = TextEditingController();

  final _codeController = TextEditingController();
  final _passwordController = TextEditingController();
  final _password2Controller = TextEditingController();

  bool _busy = false;
  int _registrationStep = 0; // 0=details, 1=avatar, 2=verify
  bool _legalAccepted = false;
  String? _error;
  String? _info;
  String _avatarSeed = '';
  String _avatarEyes = 'default';
  String _avatarMouth = 'smile';
  String _avatarClothing = 'hoodie';
  String _avatarAccessories = 'none';
  String _avatarHairLength = 'short';
  int _avatarSkinTone = 4;
  int _avatarFacialHair = 25;

  @override
  void initState() {
    super.initState();
    _randomizeAvatar();
  }

  @override
  void dispose() {
    _firstNameController.dispose();
    _lastNameController.dispose();
    _usernameController.dispose();
    _emailController.dispose();
    _mobileController.dispose();
    _dobController.dispose();
    _houseNumberController.dispose();
    _addressLine1Controller.dispose();
    _addressLine2Controller.dispose();
    _townController.dispose();
    _countyController.dispose();
    _postcodeController.dispose();
    _codeController.dispose();
    _passwordController.dispose();
    _password2Controller.dispose();
    super.dispose();
  }

  Future<void> _pickDob() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      firstDate: DateTime(now.year - 100),
      lastDate: DateTime(now.year - 18, now.month, now.day),
      initialDate: DateTime(now.year - 25, now.month, now.day),
    );
    if (picked == null) {
      return;
    }
    setState(() {
      _dobController.text = _formatDate(picked);
    });
  }

  void _randomizeAvatar() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    final random = Random();
    final seed = List.generate(
      12,
      (_) => chars[random.nextInt(chars.length)],
    ).join();
    setState(() {
      _avatarSeed = seed;
    });
  }

  String _avatarPreviewUrl() {
    final seed = _avatarSeed.isEmpty
        ? (_usernameController.text.trim().isNotEmpty
              ? _usernameController.text.trim()
              : 'rentalution')
        : _avatarSeed;

    const skinToneHex = {
      1: 'f2d3b1',
      2: 'e8c39e',
      3: 'd9a07b',
      4: 'c6865f',
      5: 'a56b46',
      6: '7a4a2f',
    };
    final skinColor = skinToneHex[_avatarSkinTone] ?? 'c6865f';

    const shortHair =
        'shortFlat,shortRound,shortWaved,theCaesar,theCaesarAndSidePart,'
        'sides,shavedSides,dreads01,dreads02,frizzle,shaggyMullet,shortCurly';
    const longHair =
        'longButNotTooLong,straight01,straight02,straightAndStrand,'
        'bun,bob,curly,curvy,miaWallace,frida,bigHair';
    final hairTop = _avatarHairLength == 'long' ? longHair : shortHair;

    final params = <String, String>{
      'seed': seed,
      'size': '256',
      'skinColor': skinColor,
      'top': hairTop,
      'eyes': _avatarEyes,
      'mouth': _avatarMouth,
      'clothing': _avatarClothing,
    };

    if (_avatarAccessories == 'none') {
      params['accessoriesProbability'] = '0';
    } else {
      params['accessories'] = _avatarAccessories;
      params['accessoriesProbability'] = '100';
    }

    if (_avatarFacialHair <= 0) {
      params['facialHairProbability'] = '0';
    } else {
      final beardStyle = _avatarFacialHair <= 33
          ? 'beardLight'
          : _avatarFacialHair <= 66
          ? 'beardMedium'
          : 'beardMajestic';
      params['facialHair'] = beardStyle;
      params['facialHairProbability'] = '100';
    }

    final queryParts = <String>[];
    params.forEach((k, v) => queryParts.add('$k=$v'));
    return 'https://api.dicebear.com/9.x/avataaars/png?${queryParts.join("&")}';
  }

  String _formatDate(DateTime value) {
    final dd = value.day.toString().padLeft(2, '0');
    final mm = value.month.toString().padLeft(2, '0');
    final yyyy = value.year.toString();
    return '$dd-$mm-$yyyy';
  }

  void _nextStep() {
    if (!_startFormKey.currentState!.validate()) return;
    setState(() {
      _registrationStep = 1;
      _error = null;
      _info = null;
    });
  }

  Future<void> _sendVerificationCode() async {
    if (_busy) {
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
      _info = null;
    });

    try {
      final message = await widget.authRepository.registerStart(
        firstName: _firstNameController.text.trim(),
        lastName: _lastNameController.text.trim(),
        username: _usernameController.text.trim(),
        email: _emailController.text.trim().toLowerCase(),
        avatarPreset: _avatarSeed,
        dateOfBirth: _dobController.text.trim(),
        mobileNumber: _mobileController.text.trim(),
        houseNameNumber: _houseNumberController.text.trim(),
        addressLine1: _addressLine1Controller.text.trim(),
        addressLine2: _addressLine2Controller.text.trim(),
        town: _townController.text.trim(),
        county: _countyController.text.trim(),
        postcode: _postcodeController.text.trim(),
        avatarEyes: _avatarEyes,
        avatarMouth: _avatarMouth,
        avatarClothing: _avatarClothing,
        avatarAccessories: _avatarAccessories,
        avatarHairLength: _avatarHairLength,
        avatarSkinTone: _avatarSkinTone,
        avatarFacialHair: _avatarFacialHair,
      );

      setState(() {
        _registrationStep = 2;
        _info = message;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  Future<void> _resendCode() async {
    if (_busy) {
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
      _info = null;
    });

    try {
      final message = await widget.authRepository.registerResend(
        email: _emailController.text.trim().toLowerCase(),
      );
      setState(() {
        _info = message;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  Future<void> _completeRegistration() async {
    if (!_verifyFormKey.currentState!.validate() || _busy) {
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
      _info = null;
    });

    try {
      final session = await widget.authRepository.registerVerify(
        email: _emailController.text.trim().toLowerCase(),
        verificationCode: _codeController.text.trim(),
        password: _passwordController.text,
      );

      if (!mounted) {
        return;
      }
      Navigator.of(context).pop<AuthSession>(session);
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          _registrationStep == 2
              ? 'Verify account'
              : _registrationStep == 1
              ? 'Choose your avatar'
              : 'Create account',
        ),
      ),
      body: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(
          16,
          16,
          16,
          16 + MediaQuery.of(context).padding.bottom,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_registrationStep == 2)
              _buildVerifyStage()
            else if (_registrationStep == 1)
              _buildAvatarStage()
            else
              _buildStartStage(),
            if (_info != null) ...[
              const SizedBox(height: 12),
              Text(_info!, style: const TextStyle(color: Colors.green)),
            ],
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: Colors.red)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildStartStage() {
    return AutofillGroup(
      child: Form(
        key: _startFormKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _requiredField(
              _firstNameController,
              'First name',
              keyboardType: TextInputType.name,
              autofillHints: const [AutofillHints.givenName],
            ),
            const SizedBox(height: 10),
            _requiredField(
              _lastNameController,
              'Surname',
              keyboardType: TextInputType.name,
              autofillHints: const [AutofillHints.familyName],
            ),
            const SizedBox(height: 10),
            _requiredField(
              _usernameController,
              'Username',
              autofillHints: const [AutofillHints.username],
              validator: (value) {
                final text = (value ?? '').trim();
                if (text.isEmpty) return 'Enter a username';
                if (text.length < 3 || text.length > 30) {
                  return 'Username must be 3-30 characters';
                }
                final valid = RegExp(r'^[a-zA-Z0-9_-]{3,30}$').hasMatch(text);
                if (!valid) {
                  return 'Use letters, numbers, hyphens or underscores';
                }
                return null;
              },
            ),
            const SizedBox(height: 10),
            _requiredField(
              _emailController,
              'Email address',
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              validator: (value) {
                final text = (value ?? '').trim();
                if (text.isEmpty) return 'Enter an email address';
                if (!text.contains('@')) return 'Enter a valid email address';
                return null;
              },
            ),
            const SizedBox(height: 10),
            _requiredField(
              _mobileController,
              'Mobile number',
              keyboardType: TextInputType.phone,
              autofillHints: const [AutofillHints.telephoneNumber],
            ),
            const SizedBox(height: 10),
            TextFormField(
              controller: _dobController,
              readOnly: true,
              onTap: _pickDob,
              decoration: const InputDecoration(
                labelText: 'Date of birth (dd-mm-yyyy)',
                suffixIcon: Icon(Icons.calendar_month),
              ),
              validator: (value) {
                if ((value ?? '').trim().isEmpty) {
                  return 'Select your date of birth';
                }
                return null;
              },
            ),
            const SizedBox(height: 14),
            Text('Address', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 10),
            TextFormField(
              controller: _houseNumberController,
              keyboardType: TextInputType.streetAddress,
              decoration: const InputDecoration(
                labelText: 'House name/number (optional)',
              ),
            ),
            const SizedBox(height: 10),
            _requiredField(
              _addressLine1Controller,
              'Address line 1',
              keyboardType: TextInputType.streetAddress,
              autofillHints: const [AutofillHints.streetAddressLine1],
            ),
            const SizedBox(height: 10),
            TextFormField(
              controller: _addressLine2Controller,
              keyboardType: TextInputType.streetAddress,
              autofillHints: const [AutofillHints.streetAddressLine2],
              decoration: const InputDecoration(
                labelText: 'Address line 2 (optional)',
              ),
            ),
            const SizedBox(height: 10),
            _requiredField(
              _townController,
              'Town / city',
              autofillHints: const [AutofillHints.addressCity],
            ),
            const SizedBox(height: 10),
            TextFormField(
              controller: _countyController,
              autofillHints: const [AutofillHints.addressState],
              decoration: const InputDecoration(labelText: 'County (optional)'),
            ),
            const SizedBox(height: 10),
            _requiredField(
              _postcodeController,
              'Postcode',
              autofillHints: const [AutofillHints.postalCode],
            ),
            const SizedBox(height: 16),
            CheckboxListTile(
              value: _legalAccepted,
              onChanged: (value) {
                setState(() {
                  _legalAccepted = value ?? false;
                });
              },
              controlAffinity: ListTileControlAffinity.leading,
              contentPadding: EdgeInsets.zero,
              title: const Text(
                'I agree to the Terms, Privacy Policy, and Cookie Policy.',
              ),
              subtitle: const Text(
                'Under UK GDPR and PECR, we use your data to run your account and service, and ask consent for non-essential cookies where required.',
              ),
            ),
            const SizedBox(height: 6),
            FilledButton.icon(
              onPressed: _legalAccepted
                  ? _nextStep
                  : () {
                      setState(() {
                        _error =
                            'Please accept the Terms, Privacy Policy, and Cookie Policy to continue.';
                      });
                    },
              icon: const Icon(Icons.arrow_forward),
              label: const Text('Next'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAvatarStage() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isNarrow = constraints.maxWidth < 430;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: ClipOval(
                child: Image.network(
                  _avatarPreviewUrl(),
                  key: Key(_avatarPreviewUrl()),
                  width: 136,
                  height: 136,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) => Container(
                    width: 136,
                    height: 136,
                    color: const Color(0xFFF0F3F4),
                    alignment: Alignment.center,
                    child: const Icon(Icons.person_outline, size: 60),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Center(
              child: OutlinedButton.icon(
                onPressed: _randomizeAvatar,
                icon: const Icon(Icons.shuffle),
                label: const Text('Randomise'),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: ExpansionTile(
                initiallyExpanded: !isNarrow,
                title: const Text('Face & Style'),
                childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                children: [
                  _avatarRow('Eyes', _avatarEyes, const [
                    DropdownMenuItem(value: 'default', child: Text('Default')),
                    DropdownMenuItem(value: 'happy', child: Text('Happy')),
                    DropdownMenuItem(value: 'wink', child: Text('Wink')),
                    DropdownMenuItem(
                      value: 'surprised',
                      child: Text('Surprised'),
                    ),
                    DropdownMenuItem(value: 'squint', child: Text('Squint')),
                    DropdownMenuItem(value: 'closed', child: Text('Closed')),
                  ], (v) => setState(() => _avatarEyes = v!)),
                  const SizedBox(height: 10),
                  _avatarRow('Mouth', _avatarMouth, const [
                    DropdownMenuItem(value: 'smile', child: Text('Smile')),
                    DropdownMenuItem(value: 'default', child: Text('Default')),
                    DropdownMenuItem(value: 'serious', child: Text('Serious')),
                    DropdownMenuItem(value: 'twinkle', child: Text('Twinkle')),
                    DropdownMenuItem(value: 'tongue', child: Text('Tongue')),
                  ], (v) => setState(() => _avatarMouth = v!)),
                  const SizedBox(height: 10),
                  _avatarRow(
                    'Clothing',
                    _avatarClothing,
                    const [
                      DropdownMenuItem(value: 'hoodie', child: Text('Hoodie')),
                      DropdownMenuItem(
                        value: 'graphicShirt',
                        child: Text('Graphic shirt'),
                      ),
                      DropdownMenuItem(
                        value: 'overall',
                        child: Text('Overall'),
                      ),
                      DropdownMenuItem(
                        value: 'shirtCrewNeck',
                        child: Text('Crew neck'),
                      ),
                      DropdownMenuItem(
                        value: 'shirtVNeck',
                        child: Text('V-neck'),
                      ),
                      DropdownMenuItem(
                        value: 'blazerAndShirt',
                        child: Text('Blazer & shirt'),
                      ),
                    ],
                    (v) => setState(() => _avatarClothing = v!),
                  ),
                  const SizedBox(height: 10),
                  _avatarRow(
                    'Accessories',
                    _avatarAccessories,
                    const [
                      DropdownMenuItem(value: 'none', child: Text('None')),
                      DropdownMenuItem(
                        value: 'round',
                        child: Text('Round glasses'),
                      ),
                      DropdownMenuItem(
                        value: 'prescription01',
                        child: Text('Prescription 1'),
                      ),
                      DropdownMenuItem(
                        value: 'prescription02',
                        child: Text('Prescription 2'),
                      ),
                      DropdownMenuItem(
                        value: 'wayfarers',
                        child: Text('Wayfarers'),
                      ),
                      DropdownMenuItem(
                        value: 'sunglasses',
                        child: Text('Sunglasses'),
                      ),
                      DropdownMenuItem(value: 'kurt', child: Text('Kurt')),
                      DropdownMenuItem(
                        value: 'eyepatch',
                        child: Text('Eyepatch'),
                      ),
                    ],
                    (v) => setState(() => _avatarAccessories = v!),
                  ),
                ],
              ),
            ),
            Card(
              child: ExpansionTile(
                initiallyExpanded: !isNarrow,
                title: const Text('Hair & Tone'),
                childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                children: [
                  Row(
                    children: [
                      const SizedBox(width: 90, child: Text('Hair length:')),
                      SegmentedButton<String>(
                        segments: const [
                          ButtonSegment(value: 'short', label: Text('Short')),
                          ButtonSegment(value: 'long', label: Text('Long')),
                        ],
                        selected: {_avatarHairLength},
                        onSelectionChanged: (v) =>
                            setState(() => _avatarHairLength = v.first),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const SizedBox(width: 90, child: Text('Skin tone:')),
                      Expanded(
                        child: Slider(
                          value: _avatarSkinTone.toDouble(),
                          min: 1,
                          max: 6,
                          divisions: 5,
                          onChanged: (v) =>
                              setState(() => _avatarSkinTone = v.round()),
                        ),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      const SizedBox(width: 90, child: Text('Facial hair:')),
                      Expanded(
                        child: Slider(
                          value: _avatarFacialHair.toDouble(),
                          min: 0,
                          max: 100,
                          divisions: 4,
                          onChanged: (v) =>
                              setState(() => _avatarFacialHair = v.round()),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            FilledButton.icon(
              onPressed: _busy ? null : _sendVerificationCode,
              icon: _busy
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.mark_email_unread_outlined),
              label: const Text('Send verification code'),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: _busy
                  ? null
                  : () => setState(() {
                      _registrationStep = 0;
                      _info = null;
                      _error = null;
                    }),
              child: const Text('Back to details'),
            ),
          ],
        );
      },
    );
  }

  Widget _avatarRow(
    String label,
    String value,
    List<DropdownMenuItem<String>> items,
    void Function(String?) onChanged,
  ) {
    return Row(
      children: [
        SizedBox(width: 90, child: Text(label)),
        Expanded(
          child: DropdownButtonFormField<String>(
            initialValue: value,
            isExpanded: true,
            items: items,
            onChanged: onChanged,
            decoration: const InputDecoration(
              isDense: true,
              contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 8),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildVerifyStage() {
    return Form(
      key: _verifyFormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Code sent to ${_emailController.text.trim()}'),
          const SizedBox(height: 12),
          _requiredField(_codeController, 'Verification code'),
          const SizedBox(height: 10),
          _requiredField(
            _passwordController,
            'Password',
            obscureText: true,
            validator: (value) {
              final text = value ?? '';
              if (text.isEmpty) return 'Enter a password';
              if (text.length < 8) return 'Use at least 8 characters';
              return null;
            },
          ),
          const SizedBox(height: 10),
          _requiredField(
            _password2Controller,
            'Repeat password',
            obscureText: true,
            validator: (value) {
              final text = value ?? '';
              if (text.isEmpty) return 'Repeat your password';
              if (text != _passwordController.text) {
                return 'Passwords do not match';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy ? null : _completeRegistration,
            child: _busy
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Complete registration'),
          ),
          const SizedBox(height: 10),
          TextButton(
            onPressed: _busy ? null : _resendCode,
            child: const Text('Resend code'),
          ),
          TextButton(
            onPressed: _busy
                ? null
                : () {
                    setState(() {
                      _registrationStep = 1;
                      _info = null;
                      _error = null;
                    });
                  },
            child: const Text('Back to details'),
          ),
        ],
      ),
    );
  }

  Widget _requiredField(
    TextEditingController controller,
    String label, {
    bool obscureText = false,
    TextInputType? keyboardType,
    List<String>? autofillHints,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      obscureText: obscureText,
      keyboardType: keyboardType,
      autofillHints: autofillHints,
      decoration: InputDecoration(labelText: label),
      validator:
          validator ??
          (value) {
            if ((value ?? '').trim().isEmpty) {
              return 'Enter $label';
            }
            return null;
          },
    );
  }
}
