import 'dart:math';

import 'package:flutter/material.dart';

import '../models/auth_models.dart';
import '../services/auth_repository.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({
    super.key,
    required this.authRepository,
  });

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
  bool _verificationStage = false;
  String? _error;
  String? _info;
  String _avatarSeed = '';

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
    final seed = List.generate(12, (_) => chars[random.nextInt(chars.length)]).join();
    setState(() {
      _avatarSeed = seed;
    });
  }

  String _avatarPreviewUrl() {
    final seed = _avatarSeed.isEmpty ? (_usernameController.text.trim().isNotEmpty ? _usernameController.text.trim() : 'sharing-hub') : _avatarSeed;
    return 'https://api.dicebear.com/9.x/avataaars/png?seed=$seed&size=256&mouth=smile';
  }

  String _formatDate(DateTime value) {
    final dd = value.day.toString().padLeft(2, '0');
    final mm = value.month.toString().padLeft(2, '0');
    final yyyy = value.year.toString();
    return '$dd-$mm-$yyyy';
  }

  Future<void> _sendVerificationCode() async {
    if (!_startFormKey.currentState!.validate() || _busy) {
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
      );

      setState(() {
        _verificationStage = true;
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
        title: Text(_verificationStage ? 'Verify account' : 'Create account'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_verificationStage) _buildVerifyStage() else _buildStartStage(),
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
    return Form(
      key: _startFormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Step 1: Your details', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          _requiredField(_firstNameController, 'First name'),
          const SizedBox(height: 10),
          _requiredField(_lastNameController, 'Surname'),
          const SizedBox(height: 10),
          _requiredField(
            _usernameController,
            'Username',
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
            validator: (value) {
              final text = (value ?? '').trim();
              if (text.isEmpty) return 'Enter an email address';
              if (!text.contains('@')) return 'Enter a valid email address';
              return null;
            },
          ),
          const SizedBox(height: 10),
          _requiredField(_mobileController, 'Mobile number'),
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
            decoration: const InputDecoration(labelText: 'House name/number (optional)'),
          ),
          const SizedBox(height: 10),
          _requiredField(_addressLine1Controller, 'Address line 1'),
          const SizedBox(height: 10),
          TextFormField(
            controller: _addressLine2Controller,
            decoration: const InputDecoration(labelText: 'Address line 2 (optional)'),
          ),
          const SizedBox(height: 10),
          _requiredField(_townController, 'Town / city'),
          const SizedBox(height: 10),
          TextFormField(
            controller: _countyController,
            decoration: const InputDecoration(labelText: 'County (optional)'),
          ),
          const SizedBox(height: 10),
          _requiredField(_postcodeController, 'Postcode'),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Text('Avatar', style: Theme.of(context).textTheme.titleSmall),
                      const Spacer(),
                      OutlinedButton.icon(
                        onPressed: _busy ? null : _randomizeAvatar,
                        icon: const Icon(Icons.shuffle),
                        label: const Text('Randomize'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Center(
                    child: ClipOval(
                      child: Image.network(
                        _avatarPreviewUrl(),
                        width: 112,
                        height: 112,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) {
                          return Container(
                            width: 112,
                            height: 112,
                            color: const Color(0xFFF0F3F4),
                            alignment: Alignment.center,
                            child: const Icon(Icons.person_outline, size: 48),
                          );
                        },
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Further avatar controls are available on the web.',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _busy ? null : _sendVerificationCode,
            icon: const Icon(Icons.mark_email_unread_outlined),
            label: _busy
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Send verification code'),
          ),
        ],
      ),
    );
  }

  Widget _buildVerifyStage() {
    return Form(
      key: _verifyFormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Step 2: Verify and set password', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
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
              if (text != _passwordController.text) return 'Passwords do not match';
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
                      _verificationStage = false;
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
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      obscureText: obscureText,
      keyboardType: keyboardType,
      decoration: InputDecoration(labelText: label),
      validator: validator ??
          (value) {
            if ((value ?? '').trim().isEmpty) {
              return 'Enter $label';
            }
            return null;
          },
    );
  }
}
