import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const RoverCompanionApp());
}

class RoverCompanionApp extends StatelessWidget {
  const RoverCompanionApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RoverLink Companion',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF080A0F),
        primaryColor: const Color(0xFF00F2FE),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF00F2FE),
          secondary: Color(0xFF10B981),
          surface: Color(0xFF0F131A),
        ),
      ),
      home: const RoverMainScreen(),
    );
  }
}

class RoverMainScreen extends StatefulWidget {
  const RoverMainScreen({super.key});

  @override
  State<RoverMainScreen> createState() => _RoverMainScreenState();
}

class _RoverMainScreenState extends State<RoverMainScreen> {
  int _currentIndex = 0;
  String _serverUrl = "http://192.168.1.11:5000";
  bool _isConnected = false;
  double? _distanceCm;
  String _roverState = "STOP";
  int _targetSpeed = 180;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _startPolling();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      _fetchState();
    });
  }

  Future<void> _fetchState() async {
    try {
      final uri = Uri.parse("$_serverUrl/api/state");
      final res = await http.get(uri).timeout(const Duration(seconds: 2));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        if (mounted) {
          setState(() {
            _isConnected = true;
            final link = data['link'];
            if (link != null) {
              _roverState = link['state'] ?? 'STOP';
              if (link['distance_cm'] != null) {
                _distanceCm = (link['distance_cm'] as num).toDouble();
              }
            }
          });
        }
      } else {
        if (mounted) setState(() => _isConnected = false);
      }
    } catch (_) {
      if (mounted) setState(() => _isConnected = false);
    }
  }

  Future<void> _sendCommand(String cmd) async {
    try {
      final uri = Uri.parse("$_serverUrl/api/cmd");
      await http.post(
        uri,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"c": cmd, "speed": _targetSpeed}),
      ).timeout(const Duration(seconds: 1));
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F131A),
        elevation: 0,
        title: Row(
          children: [
            const Icon(Icons.bolt, color: Color(0xFF00F2FE), size: 22),
            const SizedBox(width: 8),
            const Text(
              'ROVERLINK',
              style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1.2, fontSize: 16),
            ),
            const Spacer(),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: _isConnected ? const Color(0xFF0D2818) : const Color(0xFF2D1212),
                border: Border.all(
                  color: _isConnected ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                ),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                _isConnected ? 'LINK OK' : 'OFFLINE',
                style: TextStyle(
                  color: _isConnected ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: [
          _buildDrivePadTab(),
          _buildPairingTab(),
          _buildWiringGuideTab(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        backgroundColor: const Color(0xFF0F131A),
        selectedItemColor: const Color(0xFF00F2FE),
        unselectedItemColor: Colors.grey,
        onTap: (idx) => setState(() => _currentIndex = idx),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.gamepad), label: 'Drive Pad'),
          BottomNavigationBarItem(icon: Icon(Icons.qr_code_scanner), label: 'Pairing'),
          BottomNavigationBarItem(icon: Icon(Icons.memory), label: 'Pinout Guide'),
        ],
      ),
    );
  }

  Widget _buildDrivePadTab() {
    Color distColor = const Color(0xFF10B981);
    if (_distanceCm != null) {
      if (_distanceCm! < 15.0) {
        distColor = const Color(0xFFEF4444);
      } else if (_distanceCm! < 30.0) {
        distColor = const Color(0xFFF59E0B);
      }
    }

    return Column(
      children: [
        // Telemetry HUD bar
        Container(
          margin: const EdgeInsets.all(16),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFF0F131A),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFF1E293B)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              Column(
                children: [
                  const Text('OBSTACLE', style: TextStyle(fontSize: 11, color: Colors.grey)),
                  const SizedBox(height: 4),
                  Text(
                    _distanceCm != null ? '${_distanceCm!.toStringAsFixed(1)} cm' : '— cm',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: distColor),
                  ),
                ],
              ),
              Column(
                children: [
                  const Text('GATE STATUS', style: TextStyle(fontSize: 11, color: Colors.grey)),
                  const SizedBox(height: 4),
                  Text(
                    (_distanceCm != null && _distanceCm! < 15.0) ? 'BLOCKED ($_roverState)' : 'CLEAR ($_roverState)',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: (_distanceCm != null && _distanceCm! < 15.0) ? const Color(0xFFEF4444) : const Color(0xFF10B981),
                    ),
                  ),
                ],
              ),
              Column(
                children: [
                  const Text('PWM SPEED', style: TextStyle(fontSize: 11, color: Colors.grey)),
                  const SizedBox(height: 4),
                  Text(
                    '$_targetSpeed',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF00F2FE)),
                  ),
                ],
              ),
            ],
          ),
        ),

        // Speed Slider
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Row(
            children: [
              const Text('SPEED: ', style: TextStyle(fontSize: 12, color: Colors.grey)),
              Expanded(
                child: Slider(
                  value: _targetSpeed.toDouble(),
                  min: 60,
                  max: 255,
                  activeColor: const Color(0xFF00F2FE),
                  onChanged: (v) => setState(() => _targetSpeed = v.toInt()),
                ),
              ),
            ],
          ),
        ),

        const Spacer(),

        // Directional Pad
        Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildDriveButton('▲', 'F'),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _buildDriveButton('◀', 'L'),
                const SizedBox(width: 12),
                // Emergency Stop
                GestureDetector(
                  onTap: () => _sendCommand('S'),
                  child: Container(
                    width: 80,
                    height: 70,
                    decoration: BoxDecoration(
                      color: const Color(0xFFEF4444),
                      borderRadius: BorderRadius.circular(10),
                      boxShadow: const [
                        BoxShadow(color: Color(0x66EF4444), blurRadius: 12, offset: Offset(0, 4)),
                      ],
                    ),
                    alignment: Alignment.center,
                    child: const Text('STOP', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.white)),
                  ),
                ),
                const SizedBox(width: 12),
                _buildDriveButton('▶', 'R'),
              ],
            ),
            const SizedBox(height: 12),
            _buildDriveButton('▼', 'B'),
          ],
        ),
        const Spacer(),
      ],
    );
  }

  Widget _buildDriveButton(String label, String cmd) {
    return Listener(
      onPointerDown: (_) => _sendCommand(cmd),
      onPointerUp: (_) => _sendCommand('S'),
      child: Container(
        width: 75,
        height: 65,
        decoration: BoxDecoration(
          color: const Color(0xFF1E293B),
          border: Border.all(color: const Color(0xFF334155)),
          borderRadius: BorderRadius.circular(10),
        ),
        alignment: Alignment.center,
        child: Text(label, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white)),
      ),
    );
  }

  Widget _buildPairingTab() {
    final controller = TextEditingController(text: _serverUrl);
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('MISSION CONTROL PAIRING', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF00F2FE))),
          const SizedBox(height: 8),
          const Text(
            'Connect your phone to the desktop Mission Deck. Once paired, your phone camera streams straight into YOLOv11 with zero ads.',
            style: TextStyle(fontSize: 12, color: Colors.grey),
          ),
          const SizedBox(height: 20),
          TextField(
            controller: controller,
            decoration: const InputDecoration(
              labelText: 'Desktop Mission Control URL',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.computer),
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF00F2FE), foregroundColor: Colors.black),
              icon: const Icon(Icons.link),
              label: const Text('TEST & SAVE CONNECTION', style: TextStyle(fontWeight: FontWeight.bold)),
              onPressed: () {
                setState(() => _serverUrl = controller.text.trim());
                _fetchState();
              },
            ),
          ),
          const SizedBox(height: 30),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF0F131A),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFF1E293B)),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('QR CODE QUICK-CONNECT', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
                SizedBox(height: 6),
                Text('1. Open Mission Deck on your desktop (http://192.168.1.11:5000).\n2. Click "PAIR PHONE (QR)".\n3. Scan with your phone to instantly link without typing URLs.', style: TextStyle(fontSize: 12, color: Colors.grey)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWiringGuideTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('HARDWARE CONNECTIONS', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF00F2FE))),
        const SizedBox(height: 8),
        const Text('Authoritative pinout verified against firmware pins.h', style: TextStyle(fontSize: 12, color: Colors.grey)),
        const SizedBox(height: 16),
        _buildWiringRow('ESP32 GPIO 17 (TX2)', 'Arduino UNO D4', 'SoftwareSerial RX 9600 baud'),
        _buildWiringRow('ESP32 GND', 'Arduino UNO GND', 'Mandatory Common Star Ground'),
        _buildWiringRow('HC-SR04 TRIG', 'Arduino UNO D11', '10 µs Ultrasonic Pulse'),
        _buildWiringRow('HC-SR04 ECHO', 'Arduino UNO D12', 'Echo Return Pulse Width'),
        _buildWiringRow('Motor Left (PWM)', 'Arduino UNO D5', 'ENA / PWMA Speed Gate'),
        _buildWiringRow('Motor Left (DIR)', 'Arduino UNO D6 / D7', 'AIN1 / AIN2 Direction Gates'),
        _buildWiringRow('Motor Right (PWM)', 'Arduino UNO D9 / D10', 'ENB / PWMB Speed Gate'),
        _buildWiringRow('Motor Right (DIR)', 'Arduino UNO D8 / D10', 'BIN1 / BIN2 Direction Gates'),
        _buildWiringRow('Battery (+ 7.4V)', 'Motor Driver 12V/VM', 'Direct High-Current Motor Rail'),
        _buildWiringRow('Buck 5.0V Out', 'Arduino 5V & ESP32 5V', 'Regulated Logic Power Rail'),
      ],
    );
  }

  Widget _buildWiringRow(String from, String to, String notes) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0F131A),
        border: Border.all(color: const Color(0xFF1E293B)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(from, style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF00F2FE), fontSize: 13)),
              const Text(' ──► ', style: TextStyle(color: Colors.grey)),
              Text(to, style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF10B981), fontSize: 13)),
            ],
          ),
          const SizedBox(height: 4),
          Text(notes, style: const TextStyle(fontSize: 11, color: Colors.grey)),
        ],
      ),
    );
  }
}
