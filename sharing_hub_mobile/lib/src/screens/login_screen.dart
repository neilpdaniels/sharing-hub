import 'package:flutter/material.dart';

import '../models/auth_models.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({
    super.key,
    required this.onLogin,
    required this.busy,
    this.embedded = false,
    this.onClose,
    this.onBiometricLogin,
    this.showBiometricLogin = false,
    this.onOpenRegister,
    this.onRegistered,
  });

  final Future<void> Function(String login, String password) onLogin;
  final bool busy;
  final bool embedded;
  final VoidCallback? onClose;
  final Future<void> Function()? onBiometricLogin;
  final bool showBiometricLogin;
  final Future<AuthSession?> Function()? onOpenRegister;
  final Future<void> Function(AuthSession session)? onRegistered;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _loginController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _passwordVisible = false;
  String? _error;

  @override
  void dispose() {
    _loginController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate() || widget.busy) {
      return;
    }

    setState(() {
      _error = null;
    });

    try {
      await widget.onLogin(
        _loginController.text.trim(),
        _passwordController.text,
      );
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    }
  }

  Future<void> _openRegister() async {
    final onOpenRegister = widget.onOpenRegister;
    if (onOpenRegister == null || widget.busy) {
      return;
    }

    final session = await onOpenRegister();
    if (session == null) {
      return;
    }

    final onRegistered = widget.onRegistered;
    if (onRegistered != null) {
      await onRegistered(session);
    }

    if (!mounted) {
      return;
    }
    if (widget.onClose != null) {
      widget.onClose!();
    } else {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final content = SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Card(
        elevation: 8,
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const Spacer(),
                    IconButton(
                      onPressed: widget.onClose,
                      icon: const Icon(Icons.close),
                      tooltip: 'Close',
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                TextFormField(
                  controller: _loginController,
                  textInputAction: TextInputAction.next,
                  decoration: const InputDecoration(
                    labelText: 'Email or username',
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Enter your email or username';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _passwordController,
                  obscureText: !_passwordVisible,
                  decoration: InputDecoration(
                    labelText: 'Password',
                    suffixIcon: IconButton(
                      onPressed: () {
                        setState(() {
                          _passwordVisible = !_passwordVisible;
                        });
                      },
                      icon: Icon(
                        _passwordVisible
                            ? Icons.visibility_off
                            : Icons.visibility,
                      ),
                      tooltip: _passwordVisible
                          ? 'Hide password'
                          : 'Show password',
                    ),
                  ),
                  onFieldSubmitted: (_) => _submit(),
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Enter your password';
                    }
                    return null;
                  },
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                ],
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: widget.busy ? null : _submit,
                  child: widget.busy
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Sign in'),
                ),
                const SizedBox(height: 10),
                TextButton(
                  onPressed: widget.busy ? null : _openRegister,
                  child: const Text('Create account'),
                ),
                if (widget.showBiometricLogin &&
                    widget.onBiometricLogin != null) ...[
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: widget.busy ? null : widget.onBiometricLogin,
                    icon: const Icon(Icons.fingerprint),
                    label: const Text('Use Face ID / Fingerprint'),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );

    if (widget.embedded) {
      return Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: content,
        ),
      );
    }

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF0B132B), Color(0xFF1C2541)],
          ),
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: content,
          ),
        ),
      ),
    );
  }
}
