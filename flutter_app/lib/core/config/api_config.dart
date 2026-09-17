class ApiConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );

  static const String wsUrl = String.fromEnvironment(
    'WS_URL',
    defaultValue: 'ws://10.0.2.2:8000/ws',
  );

  // Endpoints
  static const String devices = '/devices';
  static const String detections = '/detections';
  static const String spray = '/spray';
  static const String ai = '/ai';
  static const String statistics = '/statistics';
}
