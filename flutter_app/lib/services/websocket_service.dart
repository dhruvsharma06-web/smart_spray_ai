import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../core/config/api_config.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  StreamController<dynamic>? _controller;

  void connect(String deviceId) {
    _channel?.sink.close();
    _controller?.close();

    _controller = StreamController<dynamic>.broadcast();
    final url = Uri.parse('${ApiConfig.wsUrl}/device/$deviceId');
    _channel = WebSocketChannel.connect(url);

    _channel!.stream.listen(
      (data) {
        _controller?.add(data);
      },
      onError: (error) {
        // Handle error
      },
      onDone: () {
        // Handle disconnect
      },
    );
  }

  Stream<dynamic>? get stream => _controller?.stream;

  void disconnect() {
    _channel?.sink.close();
    _controller?.close();
  }
}

final webSocketServiceProvider = Provider<WebSocketService>((ref) {
  final service = WebSocketService();
  ref.onDispose(() {
    service.disconnect();
  });
  return service;
});
