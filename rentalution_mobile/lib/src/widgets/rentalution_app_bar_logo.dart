import 'package:flutter/material.dart';

class RentalutionAppBarLogo extends StatelessWidget {
  const RentalutionAppBarLogo({
    super.key,
    required this.assetPath,
    this.height = 32,
    this.width = 170,
    this.alignment = Alignment.centerLeft,
  });

  final String assetPath;
  final double height;
  final double width;
  final Alignment alignment;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      height: height,
      child: Align(
        alignment: alignment,
        child: FittedBox(
          fit: BoxFit.contain,
          alignment: alignment,
          child: Image.asset(
            assetPath,
            height: height,
            fit: BoxFit.contain,
            filterQuality: FilterQuality.high,
          ),
        ),
      ),
    );
  }
}
