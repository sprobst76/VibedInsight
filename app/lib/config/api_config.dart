import 'dart:io';
import 'package:flutter/foundation.dart';

class ApiConfig {
  // Production URL
  static const String productionUrl = 'https://insight.lab.halbewahrheit21.de';

  // Development URLs
  static const String emulatorUrl = 'http://10.0.2.2:8000'; // Android Emulator
  static const String localUrl = 'http://localhost:8000'; // iOS Simulator / Web

  // Use production URL unless running on Android emulator in debug mode
  static String get baseUrl {
    // Always use production in release mode
    if (kReleaseMode) return productionUrl;

    // In debug mode, check if we're on an emulator
    // Real devices should use production URL
    if (Platform.isAndroid) {
      // On real Android device in debug, use production
      // Emulator detection: 10.0.2.2 only works on emulator
      return productionUrl; // Changed: always use production for now
    }

    return localUrl;
  }

  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 30);
}
