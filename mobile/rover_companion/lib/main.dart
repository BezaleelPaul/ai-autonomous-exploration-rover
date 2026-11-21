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
  String _serverUrl = "http://192.168.4.2:5000";
  late final TextEditingController _urlController;
  bool _isConnected = false;
  bool _isDirectEsp32 = false;
  bool _isScanning = false;
  double? _distanceCm;
  String _roverState = "STOP";
  String _pilotMode = "MANUAL";
  int _targetSpeed = 185;
  List<String> _detectedObjects = [];
  String _modelName = "YOLOv8s";
  int _inferMs = 0;
  double _cameraFps = 0.0;
  String _decisionReason = "STANDBY • WAITING FOR PILOT";
  String _decisionOverlay = "STOP";
  int _frameCounter = 0;
  bool _liveStreamActive = true;
  Timer? _pollTimer;
  Timer? _frameTimer;

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController(text: _serverUrl);
    _startPolling();
    _startFrameTimer();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _frameTimer?.cancel();
    _urlController.dispose();
    super.dispose();
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(milliseconds: 750), (timer) {
      _fetchState();
      if (!_isDirectEsp32) {
        _fetchDecision();
      }
    });
  }

  void _startFrameTimer() {
    _frameTimer?.cancel();
    _frameTimer = Timer.periodic(const Duration(milliseconds: 140), (timer) {
      if (mounted && _liveStreamActive && _isConnected && !_isDirectEsp32) {
        setState(() {
          _frameCounter = (_frameCounter + 1) % 100000;
        });
      }
    });
  }

  Future<void> _fetchState() async {
    try {
      final isEspDirect = _serverUrl.contains("192.168.4.1") && !_serverUrl.contains(":5000");
      if (mounted) setState(() => _isDirectEsp32 = isEspDirect);

      if (isEspDirect) {
        // Direct ESP32 Gateway (/status)
        final uri = Uri.parse("$_serverUrl/status");
        final res = await http.get(uri).timeout(const Duration(seconds: 1));
        if (res.statusCode == 200) {
          final data = jsonDecode(res.body);
          if (mounted) {
            setState(() {
              _isConnected = true;
              final uno = data['uno'];
              if (uno != null) {
                _roverState = uno['state'] ?? 'STOP';
                if (uno['dist_cm'] != null) {
                  _distanceCm = (uno['dist_cm'] as num).toDouble();
                }
              }
              _modelName = "ESP32 DIRECT";
              _decisionOverlay = _roverState;
              _decisionReason = "CONNECTED DIRECTLY TO MICROCONTROLLER";
            });
          }
        } else {
          if (mounted) setState(() => _isConnected = false);
        }
      } else {
        // Python Mission Control Deck (/api/state)
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
                  if (_distanceCm! < 20.0 && _distanceCm! > 0) {
                    HapticFeedback.heavyImpact();
                  }
                }
              }
              if (data['feed'] != null) {
                final feed = data['feed'];
                _modelName = (feed['model'] ?? feed['backend'] ?? 'YOLOv8s').toString();
                _inferMs = (feed['infer_ms'] as num?)?.toInt() ?? 0;
                _cameraFps = (feed['camera_fps'] as num?)?.toDouble() ?? 0.0;
                if (feed['detections'] != null) {
                  final rawDets = feed['detections'] as List;
                  _detectedObjects = rawDets.take(5).map((d) {
                    if (d is Map) {
                      final label = (d['label'] ?? 'TARGET').toString().toUpperCase();
                      final score = d['score'] != null ? ' ${((d['score'] as num) * 100).toInt()}%' : '';
                      return '$label$score';
                    }
                    return d.toString().toUpperCase();
                  }).toList();
                }
              }
              if (data['pilot'] != null && data['pilot']['mode'] != null) {
                _pilotMode = data['pilot']['mode'].toString().toUpperCase();
              }
            });
          }
        } else {
          if (mounted) setState(() => _isConnected = false);
        }
      }
    } catch (_) {
      if (mounted) setState(() => _isConnected = false);
    }
  }

  Future<void> _fetchDecision() async {
    try {
      final uri = Uri.parse("$_serverUrl/api/decision");
      final res = await http.get(uri).timeout(const Duration(seconds: 1));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        if (mounted && data['decision'] != null) {
          final dec = data['decision'];
          setState(() {
            _decisionOverlay = dec['overlay'] ?? dec['command'] ?? 'STOP';
            final steer = dec['steering_reason'];
            final safety = dec['safety_reason'];
            _decisionReason = safety != null && safety.toString().isNotEmpty
                ? safety.toString()
                : (steer != null ? steer.toString() : 'CRUISING');
          });
        }
      }
    } catch (_) {}
  }

  Future<void> _sendCommand(String cmd) async {
    HapticFeedback.lightImpact();
    try {
      if (_isDirectEsp32) {
        // Direct ESP32 endpoint: /cmd?c=F180
        final speedVal = cmd == "S" ? "" : "$_targetSpeed";
        final uri = Uri.parse("$_serverUrl/cmd?c=$cmd$speedVal");
        await http.get(uri).timeout(const Duration(milliseconds: 600));
      } else {
        // Python Mission Deck: /api/cmd JSON POST
        final uri = Uri.parse("$_serverUrl/api/cmd");
        await http.post(
          uri,
          headers: {"Content-Type": "application/json"},
          body: jsonEncode({"c": cmd, "speed": _targetSpeed}),
        ).timeout(const Duration(milliseconds: 600));
      }
    } catch (_) {}
  }

  Future<void> _toggleMode() async {
    if (_isDirectEsp32) return;
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

  Future<void> _autoDetectServer() async {
    setState(() => _isScanning = true);
    final candidates = [
      "http://192.168.4.2:5000",   // Laptop on ESP32 Rover Wi-Fi (connected 1st)
      "http://192.168.4.3:5000",   // Laptop on ESP32 Rover Wi-Fi (connected 2nd)
      "http://192.168.1.11:5000",  // Laptop on Home Wi-Fi LAN
      "http://10.42.0.1:5000",     // Laptop on Ubuntu Wi-Fi Hotspot
      "http://192.168.4.1",        // Direct ESP32 Soft-AP
      "http://localhost:5000",
    ];

    for (final candidate in candidates) {
      try {
        final checkUrl = candidate.contains(":5000") ? "$candidate/api/state" : "$candidate/status";
        final res = await http.get(Uri.parse(checkUrl)).timeout(const Duration(milliseconds: 900));
        if (res.statusCode == 200) {
          if (mounted) {
            setState(() {
              _serverUrl = candidate;
              _urlController.text = candidate;
              _isScanning = false;
            });
            _fetchState();
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('✓ Connected to $candidate!'), backgroundColor: const Color(0xFF10B981)),
            );
          }
          return;
        }
      } catch (_) {}
    }

    if (mounted) {
      setState(() => _isScanning = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Auto-detect: No server responded. Check your phone Wi-Fi connection.'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
    }
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
                _isConnected ? (_isDirectEsp32 ? 'ESP32 LINK' : 'AI ONLINE') : 'OFFLINE',
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
      if (_distanceCm! < 18.0 && _distanceCm! > 0) {
        distColor = const Color(0xFFEF4444);
      } else if (_distanceCm! < 30.0 && _distanceCm! > 0) {
        distColor = const Color(0xFFF59E0B);
      }
    }

    return SingleChildScrollView(
      child: Column(
        children: [
          // 1. Live AI Camera Stream Viewport (FPV HUD)
          Container(
            margin: const EdgeInsets.fromLTRB(12, 8, 12, 6),
            height: 210,
            decoration: BoxDecoration(
              color: Colors.black,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFF1E293B)),
            ),
            clipBehavior: Clip.antiAlias,
            child: Stack(
              fit: StackFit.expand,
              children: [
                _isConnected && !_isDirectEsp32
                    ? Image.network(
                        "$_serverUrl/snapshot.jpg?t=$_frameCounter",
                        gaplessPlayback: true,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) => _buildNoFeedPlaceholder(),
                      )
                    : _buildNoFeedPlaceholder(),

                // Top HUD: Model & Inference Info
                Positioned(
                  top: 8,
                  left: 8,
                  right: 8,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.black.withOpacity(0.75),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: const Color(0xFF00F2FE)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.remove_red_eye, size: 12, color: Color(0xFF00F2FE)),
                            const SizedBox(width: 4),
                            Text(
                              _isDirectEsp32 ? 'DIRECT HARDWARE MODE' : '$_modelName • ${_inferMs}ms • ${_cameraFps.toStringAsFixed(1)} FPS',
                              style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.white),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.black.withOpacity(0.75),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: const Color(0xFF10B981)),
                        ),
                        child: Text(
                          'DECISION: $_decisionOverlay',
                          style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF10B981)),
                        ),
                      ),
                    ],
                  ),
                ),

                // Bottom HUD: Autonomous Reason
                Positioned(
                  bottom: 8,
                  left: 8,
                  right: 8,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.black.withOpacity(0.8),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: const Color(0xFF334155)),
                    ),
                    child: Text(
                      'WHY: $_decisionReason',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 10, color: Color(0xFFE2E8F0), fontWeight: FontWeight.w600),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // 2. Phone Camera Streamer Quick Action Bar
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      side: const BorderSide(color: Color(0xFF00F2FE)),
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                    icon: const Icon(Icons.camera_alt, size: 16, color: Color(0xFF00F2FE)),
                    label: const Text(
                      'OPEN PHONE CAM AR HUD',
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF00F2FE)),
                    ),
                    onPressed: () => _openPhoneCameraHUD(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  tooltip: 'Toggle Video Feed',
                  icon: Icon(_liveStreamActive ? Icons.videocam : Icons.videocam_off, color: const Color(0xFF10B981)),
                  onPressed: () => setState(() => _liveStreamActive = !_liveStreamActive),
                ),
              ],
            ),
          ),

          // 3. Telemetry HUD bar
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            padding: const EdgeInsets.all(12),
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
                    const SizedBox(height: 2),
                    Text(
                      _distanceCm != null && _distanceCm! > 0 ? '${_distanceCm!.toStringAsFixed(1)} cm' : '— cm',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: distColor),
                    ),
                  ],
                ),
                GestureDetector(
                  onTap: _toggleMode,
                  child: Column(
                    children: [
                      const Text('AUTONOMY', style: TextStyle(fontSize: 10, color: Colors.grey)),
                      const SizedBox(height: 2),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: _pilotMode == 'AUTO' ? const Color(0xFF08201A) : const Color(0xFF1E293B),
                          border: Border.all(color: _pilotMode == 'AUTO' ? const Color(0xFF10B981) : const Color(0xFF00F2FE)),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          _pilotMode,
                          style: TextStyle(
                            fontSize: 12,
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
                    const SizedBox(height: 2),
                    Text(
                      (_distanceCm != null && _distanceCm! < 20.0 && _distanceCm! > 0) ? 'BLOCKED' : 'CLEAR',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                        color: (_distanceCm != null && _distanceCm! < 20.0 && _distanceCm! > 0) ? const Color(0xFFEF4444) : const Color(0xFF10B981),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // 4. Live AI Detection Chips
          if (_detectedObjects.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
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

          // 5. Speed Selector
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
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

          const SizedBox(height: 8),

          // 6. Directional Drive Pad
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildDriveButton('▲', 'F'),
              const SizedBox(height: 10),
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
                      height: 64,
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
              const SizedBox(height: 10),
              _buildDriveButton('▼', 'B'),
            ],
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildNoFeedPlaceholder() {
    return Container(
      color: const Color(0xFF0F131A),
      alignment: Alignment.center,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            _isDirectEsp32 ? Icons.memory : Icons.radar,
            size: 36,
            color: const Color(0xFF00F2FE),
          ),
          const SizedBox(height: 8),
          Text(
            _isDirectEsp32
                ? 'Plan C: Direct ESP32 Gateway (No Video on Microcontroller)'
                : (_isConnected ? 'Connecting to AI Video Stream...' : 'AI Mission Deck Offline'),
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 12, color: Colors.grey),
          ),
          const SizedBox(height: 4),
          Text(
            _isDirectEsp32
                ? 'Connect to Laptop (:5000) for YOLO AI Vision & Camera'
                : 'Target: $_serverUrl',
            style: const TextStyle(fontSize: 10, color: Color(0xFF00F2FE)),
          ),
        ],
      ),
    );
  }

  void _openPhoneCameraHUD() {
    final companionUrl = _isDirectEsp32 ? "http://192.168.4.2:5000/companion" : "$_serverUrl/companion";
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF0F131A),
        title: const Text('PHONE CAMERA AR STREAMER', style: TextStyle(color: Color(0xFF00F2FE), fontSize: 14)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Your smartphone camera can act as the real-time eye of the AI Rover, streaming straight into YOLO model inference with bounding boxes and AR HUD.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
            const SizedBox(height: 12),
            const Text('Open in your phone browser:', style: TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            SelectableText(
              companionUrl,
              style: const TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.bold, fontSize: 13),
            ),
          ],
        ),
        actions: [
          TextButton(
            child: const Text('DISMISS'),
            onPressed: () => Navigator.pop(ctx),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF00F2FE), foregroundColor: Colors.black),
            child: const Text('COPY LINK', style: TextStyle(fontWeight: FontWeight.bold)),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: companionUrl));
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Copied AR HUD URL! Open in Chrome or Safari.')),
              );
            },
          ),
        ],
      ),
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
        height: 60,
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
    return Padding(
      padding: const EdgeInsets.all(20),
      child: ListView(
        children: [
          const Text('MISSION CONTROL PAIRING', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF00F2FE))),
          const SizedBox(height: 8),
          const Text(
            'Connect your phone to the desktop Mission Deck to stream video into YOLO AI and receive real-time object bounding boxes and autonomous decisions.',
            style: TextStyle(fontSize: 12, color: Colors.grey),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _urlController,
            decoration: const InputDecoration(
              labelText: 'Mission Control URL',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.computer),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 46,
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF00F2FE), foregroundColor: Colors.black),
                    icon: const Icon(Icons.link),
                    label: const Text('SAVE & CONNECT', style: TextStyle(fontWeight: FontWeight.bold)),
                    onPressed: () {
                      setState(() => _serverUrl = _urlController.text.trim());
                      _fetchState();
                    },
                  ),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                height: 46,
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(side: const BorderSide(color: Color(0xFF10B981))),
                  icon: _isScanning
                      ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF10B981)))
                      : const Icon(Icons.search, color: Color(0xFF10B981)),
                  label: const Text('AUTO-DETECT', style: TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.bold)),
                  onPressed: _isScanning ? null : _autoDetectServer,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          const Text('NETWORK PRESETS (TAP TO CONNECT)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 8),
          Column(
            children: [
              _buildPresetCard(
                title: 'Rover Wi-Fi (ESP32 AP)',
                url: 'http://192.168.4.2:5000',
                desc: 'Use when laptop & phone are connected to AI_Rover_Control Wi-Fi.',
                icon: Icons.wifi,
              ),
              const SizedBox(height: 8),
              _buildPresetCard(
                title: 'Home Wi-Fi LAN',
                url: 'http://192.168.1.11:5000',
                desc: 'Use when laptop & phone are connected to your home router.',
                icon: Icons.router,
              ),
              const SizedBox(height: 8),
              _buildPresetCard(
                title: 'Direct ESP32 Gateway (Plan C)',
                url: 'http://192.168.4.1',
                desc: 'Direct hardware control without laptop running.',
                icon: Icons.memory,
              ),
            ],
          ),
          const SizedBox(height: 16),
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
                Text('NETWORK TROUBLESHOOTING', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
                SizedBox(height: 8),
                Text('• When on "AI_Rover_Control" Wi-Fi: Laptop IP is 192.168.4.2 (port :5000). ESP32 is 192.168.4.1.\n• When on Home Wi-Fi: Laptop IP is 192.168.1.11 (port :5000).\n• If the app cannot connect, tap "AUTO-DETECT" above to automatically find the running server.', style: TextStyle(fontSize: 11, color: Colors.grey, height: 1.4)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPresetCard({required String title, required String url, required String desc, required IconData icon}) {
    final isSelected = (_serverUrl == url);
    return InkWell(
      onTap: () {
        setState(() {
          _serverUrl = url;
          _urlController.text = url;
        });
        _fetchState();
      },
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF0D2818) : const Color(0xFF0F131A),
          border: Border.all(color: isSelected ? const Color(0xFF10B981) : const Color(0xFF1E293B)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            Icon(icon, color: isSelected ? const Color(0xFF10B981) : const Color(0xFF00F2FE), size: 24),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.white)),
                  Text(url, style: const TextStyle(fontSize: 11, color: Color(0xFF00F2FE), fontWeight: FontWeight.w600)),
                  const SizedBox(height: 2),
                  Text(desc, style: const TextStyle(fontSize: 10, color: Colors.grey)),
                ],
              ),
            ),
            if (isSelected)
              const Icon(Icons.check_circle, color: Color(0xFF10B981), size: 18),
          ],
        ),
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
        _buildWiringRow('HC-SR04 TRIG', 'Arduino UNO D2', '10 µs Ultrasonic Pulse'),
        _buildWiringRow('HC-SR04 ECHO', 'Arduino UNO D3', 'Echo Return Pulse Width'),
        _buildWiringRow('TB6612FNG PWMA', 'Arduino UNO D5', 'Left Speed PWM (~976 Hz)'),
        _buildWiringRow('TB6612FNG AIN2', 'Arduino UNO D6', 'Left Direction B Gate'),
        _buildWiringRow('TB6612FNG AIN1', 'Arduino UNO D7', 'Left Direction A Gate'),
        _buildWiringRow('TB6612FNG BIN1', 'Arduino UNO D8', 'Right Direction A Gate'),
        _buildWiringRow('TB6612FNG PWMB', 'Arduino UNO D9', 'Right Speed PWM (~490 Hz)'),
        _buildWiringRow('TB6612FNG BIN2', 'Arduino UNO D10', 'Right Direction B Gate'),
        _buildWiringRow('TB6612FNG STBY', '5V Rail', 'Standby Active High (Bench Mode)'),
        _buildWiringRow('Battery (+ 7.4V)', 'TB6612FNG VM', 'Direct High-Current Motor Rail'),
        _buildWiringRow('Logic 5.0V Out', 'Arduino 5V & TB6612 VCC', 'Regulated Logic Power Rail'),
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
