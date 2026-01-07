class ApiConfig {
  // Production URL
  static const String productionUrl = 'https://insight.lab.halbewahrheit21.de';

  // Development URLs
  static const String emulatorUrl = 'http://10.0.2.2:8000'; // Android Emulator
  static const String localUrl = 'http://localhost:8000'; // iOS Simulator / Web

  // Set to true for release builds
  static const bool isProduction = bool.fromEnvironment('dart.vm.product', defaultValue: false);

  static String get baseUrl => isProduction ? productionUrl : emulatorUrl;

  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 30);
}
