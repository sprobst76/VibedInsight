class ApiConfig {
  // Production URL - change to your VPS domain
  static const String productionUrl = 'https://insight.lab.YOUR_DOMAIN.com';

  // Development URLs
  static const String emulatorUrl = 'http://10.0.2.2:8000'; // Android Emulator
  static const String localUrl = 'http://localhost:8000'; // iOS Simulator / Web

  // Toggle this for production builds
  static const bool isProduction = false;

  static String get baseUrl => isProduction ? productionUrl : emulatorUrl;

  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 30);
}
