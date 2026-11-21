import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
  String _pilotMode = "MANUAL";
  int _targetSpeed = 185;
  List<String> _detectedObjects = [];
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
    _pollTimer = Timer.periodic(const Duration(milliseconds: 900), (timer) {
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
                if (_distanceCm! < 25.0) {
                  HapticFeedback.heavyImpact();
                }
              }
            }
            if (data['feed'] != null && data['feed']['detections'] != null) {
              final rawDets = data['feed']['detections'] as List;
              _detectedObjects = rawDets.take(5).map((d) {
                if (d is Map) {
                  final label = (d['label'] ?? 'TARGET').toString().toUpperCase();
                  final score = d['score'] != null ? ' ${((d['score'] as num) * 100).toInt()}%' : '';
                  return '$label$score';
                }
                return d.toString().toUpperCase();
              }).toList();
            }
            if (data['pilot'] != null && data['pilot']['mode'] != null) {
              _pilotMode = data['pilot']['mode'].toString().toUpperCase();
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
    HapticFeedback.lightImpact();
    try {
      final uri = Uri.parse("$_serverUrl/api/cmd");
      await http.post(
        uri,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"c": cmd, "speed": _targetSpeed}),
      ).timeout(const Duration(seconds: 1));
    } catch (_) {}
  }

  Future<void> _toggleMode() async {
    HapticFeedback.mediumImpact();
    final target = (_pilotMode == "MANUAL") ? "auto" : "manual";
    try {
      final uri = Uri.parse("$_serverUrl/api/mode");
      final res = await http.post(
        uri,
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: "mode=$target",
      ).timeout(const Duration(seconds: 2));
      if (res.statusCode == 200) {
        final d = jsonDecode(res.body);
        if (mounted && d['mode'] != null) {
          setState(() => _pilotMode = d['mode'].toString().toUpperCase());
        }
      }
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
      if (_distanceCm! < 18.0) {
        distColor = const Color(0xFFEF4444);
      } else if (_distanceCm! < 30.0) {
        distColor = const Color(0xFFF59E0B);
      }
    }

    return Column(
      children: [
        // Telemetry HUD bar
        Container(
          margin: const EdgeInsets.all(12),
          padding: const EdgeInsets.all(14),
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
                  const Text('OBSTACLE', style: TextStyle(fontSize: 10, color: Colors.grey)),
                  const SizedBox(height: 4),
                  Text(
                    _distanceCm != null ? '${_distanceCm!.toStringAsFixed(1)} cm' : '— cm',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: distColor),
                  ),
                ],
              ),
              GestureDetector(
                onTap: _toggleMode,
                child: Column(
                  children: [
                    const Text('AUTONOMY', style: TextStyle(fontSize: 10, color: Colors.grey)),
                    const SizedBox(height: 4),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: _pilotMode == 'AUTO' ? const Color(0xFF08201A) : const Color(0xFF1E293B),
                        border: Border.all(color: _pilotMode == 'AUTO' ? const Color(0xFF10B981) : const Color(0xFF00F2FE)),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        _pilotMode,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.bold,
                          color: _pilotMode == 'AUTO' ? const Color(0xFF10B981) : const Color(0xFF00F2FE),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              Column(
                children: [
                  const Text('GATE STATUS', style: TextStyle(fontSize: 10, color: Colors.grey)),
                  const SizedBox(height: 4),
                  Text(
                    (_distanceCm != null && _distanceCm! < 20.0) ? 'BLOCKED' : 'CLEAR',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: (_distanceCm != null && _distanceCm! < 20.0) ? const Color(0xFFEF4444) : const Color(0xFF10B981),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),

        // Live AI Detection Chips HUD
        if (_detectedObjects.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
            child: Wrap(
              spacing: 6,
              runSpacing: 4,
              children: _detectedObjects.map((det) => Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFF121D24),
                  border: Border.all(color: const Color(0xFF00F2FE)),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.radar, size: 12, color: Color(0xFF00F2FE)),
                    const SizedBox(width: 4),
                    Text(det, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white)),
                  ],
                ),
              )).toList(),
            ),
          ),

        // Speed Preset Buttons
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text('SPEED: ', style: TextStyle(fontSize: 11, color: Colors.grey, fontWeight: FontWeight.bold)),
              const SizedBox(width: 6),
              _buildSpeedChip('ECO', 130),
              const SizedBox(width: 6),
              _buildSpeedChip('NORMAL', 185),
              const SizedBox(width: 6),
              _buildSpeedChip('TURBO', 255),
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
                const SizedBox(width: 14),
                // Emergency Stop
                GestureDetector(
                  onTap: () {
                    HapticFeedback.heavyImpact();
                    _sendCommand('S');
                  },
                  child: Container(
                    width: 82,
                    height: 70,
                    decoration: BoxDecoration(
                      color: const Color(0xFFEF4444),
                      borderRadius: BorderRadius.circular(10),
                      boxShadow: const [
                        BoxShadow(color: Color(0x66EF4444), blurRadius: 14, offset: Offset(0, 4)),
                      ],
                    ),
                    alignment: Alignment.center,
                    child: const Text('STOP', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.white)),
                  ),
                ),
                const SizedBox(width: 14),
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

  Widget _buildSpeedChip(String label, int speed) {
    final isSel = (_targetSpeed == speed);
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        setState(() => _targetSpeed = speed);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
        decoration: BoxDecoration(
          color: isSel ? const Color(0xFF10B981) : const Color(0xFF1E293B),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: isSel ? const Color(0xFF10B981) : const Color(0xFF334155)),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.bold,
            color: isSel ? Colors.black : Colors.white,
          ),
        ),
      ),
    );
  }

  Widget _buildDriveButton(String label, String cmd) {
    return Listener(
      onPointerDown: (_) => _sendCommand(cmd),
      onPointerUp: (_) => _sendCommand('S'),
      child: Container(
        width: 76,
        height: 64,
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
      child: ListView(
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
          const SizedBox(height: 24),
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
                Text('QUICK PAIRING METHODS', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
                SizedBox(height: 8),
                Text('• Plan A (Web Companion): Scan the QR code on the desktop deck to open /companion with AR HUD & WebCam streaming.\n• Plan B (IP Webcam): Start IP Webcam app on phone, open /companion and tap "Plan B" to auto-link the stream.\n• Plan C (Soft-AP): Connect to Wi-Fi "AI_Rover_Control" at 192.168.4.1.', style: TextStyle(fontSize: 11, color: Colors.grey, height: 1.4)),
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
