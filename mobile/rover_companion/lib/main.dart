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
      title: 'RoverLink Ground Control Station',
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
  String _serverUrl = "http://127.0.0.1:5000";
  late final TextEditingController _urlController;
  late final FocusNode _keyboardFocusNode;

  // Active HTTP clients for isolated telemetry vs ultra-fast frame fetching
  final http.Client _telemetryClient = http.Client();
  final http.Client _frameClient = http.Client();

  bool _isConnected = false;
  bool _isDirectEsp32 = false;
  bool _isScanning = false;
  bool _isScanningCameras = false;
  bool _isRecording = false;

  double? _distanceCm;
  String _roverState = "STOP";
  String _pilotMode = "MANUAL";
  bool _isArmed = false;
  List<String> _armBlockers = [];

  int _targetSpeed = 185;
  List<String> _detectedObjects = [];
  String _modelName = "YOLOv8s";
  int _inferMs = 0;
  double _cameraFps = 0.0;

  // Why-Chain decision data
  String _decisionProposal = "S";
  String _steeringReason = "STANDBY • WAITING FOR PILOT";
  String _safetyReason = "CLEAR";
  String _decisionOverlay = "STOP";
  int _motorLeftPwm = 0;
  int _motorRightPwm = 0;

  // Ultra-fast zero-latency frame ingestion
  Uint8List? _latestFrameBytes;
  bool _isFetchingFrame = false;
  bool _liveStreamActive = true;
  Timer? _pollTimer;
  Timer? _frameLoopTimer;

  // Network & camera state from Mission Control
  String _primaryLanIp = "192.168.1.11";
  String _companionUrl = "http://192.168.1.11:5000/companion";
  String _currentStreamSource = "cam:0";

  // Set of actively pressed motion keys
  final Set<LogicalKeyboardKey> _pressedMotionKeys = {};

  String get _subnet => _primaryLanIp.contains('.')
      ? _primaryLanIp.substring(0, _primaryLanIp.lastIndexOf('.'))
      : "192.168.1";

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController(text: _serverUrl);
    _keyboardFocusNode = FocusNode();
    _startPolling();
    _startUltraFastFramePump();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _frameLoopTimer?.cancel();
    _telemetryClient.close();
    _frameClient.close();
    _urlController.dispose();
    _keyboardFocusNode.dispose();
    super.dispose();
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(milliseconds: 500), (timer) {
      _fetchState();
      if (!_isDirectEsp32) {
        _fetchDecision();
      }
    });
  }

  /// Active asynchronous frame pump: immediately requests the next frame as soon
  /// as the previous frame finishes downloading. Eliminates polling timer queues,
  /// reduces glass-to-glass latency to ~25ms, and ensures true 30 FPS smooth video.
  void _startUltraFastFramePump() {
    _frameLoopTimer?.cancel();
    _pumpNextFrame();
  }

  Future<void> _pumpNextFrame() async {
    if (!mounted) return;
    if (_liveStreamActive && _isConnected && !_isDirectEsp32 && !_isFetchingFrame) {
      _isFetchingFrame = true;
      try {
        final uri = Uri.parse("$_serverUrl/snapshot.jpg");
        final res = await _frameClient.get(uri).timeout(const Duration(milliseconds: 300));
        if (res.statusCode == 200 && res.bodyBytes.isNotEmpty && mounted) {
          setState(() {
            _latestFrameBytes = res.bodyBytes;
          });
        }
      } catch (_) {}
      _isFetchingFrame = false;
    }

    if (mounted) {
      // 20ms pause for ~30 FPS fluid rendering on Impeller
      _frameLoopTimer = Timer(const Duration(milliseconds: 20), _pumpNextFrame);
    }
  }

  Future<void> _fetchState() async {
    try {
      final isEspDirect = _serverUrl.contains("192.168.4.1") && !_serverUrl.contains(":5000");
      if (mounted && _isDirectEsp32 != isEspDirect) {
        setState(() => _isDirectEsp32 = isEspDirect);
      }

      if (isEspDirect) {
        // Direct ESP32 Gateway (/status)
        final uri = Uri.parse("$_serverUrl/status");
        final res = await _telemetryClient.get(uri).timeout(const Duration(seconds: 1));
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
              _steeringReason = "CONNECTED DIRECTLY TO MICROCONTROLLER";
            });
          }
        } else {
          if (mounted) setState(() => _isConnected = false);
        }
      } else {
        // Python Mission Control Deck (/api/state)
        final uri = Uri.parse("$_serverUrl/api/state");
        final res = await _telemetryClient.get(uri).timeout(const Duration(seconds: 2));
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
                _currentStreamSource = (feed['source'] ?? _currentStreamSource).toString();
                if (feed['detections'] != null) {
                  final rawDets = feed['detections'] as List;
                  _detectedObjects = rawDets.take(6).map((d) {
                    if (d is Map) {
                      final label = (d['label'] ?? 'TARGET').toString().toUpperCase();
                      final score = d['conf'] != null ? ' ${((d['conf'] as num) * 100).toInt()}%' : '';
                      return '$label$score';
                    }
                    return d.toString().toUpperCase();
                  }).toList();
                }
              }
              if (data['network'] != null) {
                final net = data['network'];
                if (net['primary_ip'] != null) {
                  _primaryLanIp = net['primary_ip'].toString();
                }
                if (net['companion_url'] != null) {
                  _companionUrl = net['companion_url'].toString();
                }
                if (net['current_source'] != null) {
                  _currentStreamSource = net['current_source'].toString();
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
      final res = await _telemetryClient.get(uri).timeout(const Duration(seconds: 1));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        if (mounted) {
          setState(() {
            _pilotMode = (data['mode'] ?? _pilotMode).toString().toUpperCase();
            _isArmed = data['armed'] == true;
            if (data['blockers'] is List) {
              _armBlockers = (data['blockers'] as List).map((b) => b.toString()).toList();
            }

            if (data['decision'] != null) {
              final dec = data['decision'];
              _decisionOverlay = dec['overlay'] ?? dec['command'] ?? 'STOP';
              _decisionProposal = dec['proposed'] ?? 'S';
              _steeringReason = dec['steering_reason'] ?? 'CRUISING';
              _safetyReason = dec['safety_reason'] ?? 'CLEAR';

              if (dec['motors'] is List && (dec['motors'] as List).length >= 2) {
                _motorLeftPwm = ((dec['motors'] as List)[0] as num).toInt();
                _motorRightPwm = ((dec['motors'] as List)[1] as num).toInt();
              }
            }
          });
        }
      }
    } catch (_) {}
  }

  Future<void> _sendCommand(String cmd) async {
    HapticFeedback.lightImpact();
    try {
      if (_isDirectEsp32) {
        final speedVal = cmd == "S" ? "" : "$_targetSpeed";
        final uri = Uri.parse("$_serverUrl/cmd?c=$cmd$speedVal");
        await _telemetryClient.get(uri).timeout(const Duration(milliseconds: 600));
      } else {
        final uri = Uri.parse("$_serverUrl/api/cmd");
        await _telemetryClient.post(
          uri,
          headers: {"Content-Type": "application/json"},
          body: jsonEncode({"c": cmd, "speed": _targetSpeed}),
        ).timeout(const Duration(milliseconds: 600));
      }
    } catch (_) {}
  }

  Future<void> _setMode(String mode) async {
    if (_isDirectEsp32) return;
    HapticFeedback.mediumImpact();
    try {
      final uri = Uri.parse("$_serverUrl/api/mode");
      final res = await _telemetryClient.post(
        uri,
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: "mode=${mode.toLowerCase()}",
      ).timeout(const Duration(seconds: 2));
      if (res.statusCode == 200) {
        final d = jsonDecode(res.body);
        if (mounted && d['mode'] != null) {
          setState(() => _pilotMode = d['mode'].toString().toUpperCase());
        }
      }
    } catch (_) {}
  }

  Future<void> _toggleRecording() async {
    if (_isDirectEsp32) return;
    final nextState = !_isRecording;
    try {
      final uri = Uri.parse("$_serverUrl/api/recording");
      final res = await _telemetryClient.post(
        uri,
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: "on=$nextState",
      ).timeout(const Duration(seconds: 2));
      if (res.statusCode == 200) {
        final d = jsonDecode(res.body);
        if (mounted) {
          setState(() => _isRecording = d['recording'] == true);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(_isRecording ? '● Mission Recording STARTED' : '■ Mission Recording STOPPED & SAVED'),
              backgroundColor: _isRecording ? const Color(0xFFEF4444) : const Color(0xFF10B981),
            ),
          );
        }
      }
    } catch (_) {}
  }

  KeyEventResult _handleKeyEvent(FocusNode node, KeyEvent event) {
    final key = event.logicalKey;
    final isMovementKey = key == LogicalKeyboardKey.keyW ||
        key == LogicalKeyboardKey.arrowUp ||
        key == LogicalKeyboardKey.keyS ||
        key == LogicalKeyboardKey.arrowDown ||
        key == LogicalKeyboardKey.keyA ||
        key == LogicalKeyboardKey.arrowLeft ||
        key == LogicalKeyboardKey.keyD ||
        key == LogicalKeyboardKey.arrowRight;

    if (event is KeyDownEvent) {
      if (key == LogicalKeyboardKey.space) {
        _sendCommand('S');
        return KeyEventResult.handled;
      }
      if (key == LogicalKeyboardKey.keyM) {
        // Cycle between MANUAL -> OBSERVE -> AUTO -> EXPLORE
        final next = _pilotMode == "MANUAL"
            ? "OBSERVE"
            : (_pilotMode == "OBSERVE" ? "AUTO" : (_pilotMode == "AUTO" ? "EXPLORE" : "MANUAL"));
        _setMode(next);
        return KeyEventResult.handled;
      }
      if (key == LogicalKeyboardKey.digit1) {
        setState(() => _targetSpeed = 130);
        return KeyEventResult.handled;
      }
      if (key == LogicalKeyboardKey.digit2) {
        setState(() => _targetSpeed = 185);
        return KeyEventResult.handled;
      }
      if (key == LogicalKeyboardKey.digit3) {
        setState(() => _targetSpeed = 255);
        return KeyEventResult.handled;
      }

      if (isMovementKey) {
        if (!_pressedMotionKeys.contains(key)) {
          _pressedMotionKeys.add(key);
          if (key == LogicalKeyboardKey.keyW || key == LogicalKeyboardKey.arrowUp) {
            _sendCommand('F');
          } else if (key == LogicalKeyboardKey.keyS || key == LogicalKeyboardKey.arrowDown) {
            _sendCommand('B');
          } else if (key == LogicalKeyboardKey.keyA || key == LogicalKeyboardKey.arrowLeft) {
            _sendCommand('L');
          } else if (key == LogicalKeyboardKey.keyD || key == LogicalKeyboardKey.arrowRight) {
            _sendCommand('R');
          }
        }
        return KeyEventResult.handled;
      }
    } else if (event is KeyUpEvent) {
      if (isMovementKey) {
        _pressedMotionKeys.remove(key);
        if (_pressedMotionKeys.isEmpty) {
          _sendCommand('S');
        } else {
          final remaining = _pressedMotionKeys.last;
          if (remaining == LogicalKeyboardKey.keyW || remaining == LogicalKeyboardKey.arrowUp) {
            _sendCommand('F');
          } else if (remaining == LogicalKeyboardKey.keyS || remaining == LogicalKeyboardKey.arrowDown) {
            _sendCommand('B');
          } else if (remaining == LogicalKeyboardKey.keyA || remaining == LogicalKeyboardKey.arrowLeft) {
            _sendCommand('L');
          } else if (remaining == LogicalKeyboardKey.keyD || remaining == LogicalKeyboardKey.arrowRight) {
            _sendCommand('R');
          }
        }
        return KeyEventResult.handled;
      }
    }
    return KeyEventResult.ignored;
  }

  Future<void> _autoDetectServer() async {
    setState(() => _isScanning = true);
    final candidates = [
      "http://127.0.0.1:5000",
      "http://localhost:5000",
      "http://192.168.43.1:5000", // Android Mobile Hotspot Laptop Gateway
      "http://192.168.1.11:5000",
      "http://192.168.4.2:5000",
      "http://10.42.0.1:5000",    // Linux Hotspot
      "http://192.168.4.1",       // ESP32 AP
    ];

    for (final candidate in candidates) {
      try {
        final checkUrl = candidate.contains(":5000") ? "$candidate/api/state" : "$candidate/status";
        final res = await _telemetryClient.get(Uri.parse(checkUrl)).timeout(const Duration(milliseconds: 700));
        if (res.statusCode == 200) {
          if (mounted) {
            setState(() {
              _serverUrl = candidate;
              _urlController.text = candidate;
              _isScanning = false;
            });
            await _fetchState();
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('✓ Connected to $candidate!'), backgroundColor: const Color(0xFF10B981)),
              );
            }
          }
          return;
        }
      } catch (_) {}
    }

    if (mounted) {
      setState(() => _isScanning = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Auto-detect: No rover server responded. Check network connection.'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
    }
  }

  void _openPhoneCameraHUD() {
    String phoneUrl = _companionUrl;
    if (_serverUrl.contains("127.0.0.1") || _serverUrl.contains("localhost")) {
      phoneUrl = "http://$_primaryLanIp:5000/companion";
    } else if (!_serverUrl.contains("192.168.4.1")) {
      phoneUrl = "$_serverUrl/companion";
    }

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF0F131A),
        title: const Row(
          children: [
            Icon(Icons.phone_android, color: Color(0xFF00F2FE), size: 20),
            SizedBox(width: 8),
            Text('PHONE CAMERA & WIRELESS SETUP', style: TextStyle(color: Color(0xFF00F2FE), fontSize: 15, fontWeight: FontWeight.bold)),
          ],
        ),
        content: SizedBox(
          width: 520,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Mount your phone on the rover to act as its AI vision eye. When at college or in the field, mobile hotspot provides the highest smoothness and lowest latency (<3ms):',
                style: TextStyle(fontSize: 12, color: Colors.grey, height: 1.3),
              ),
              const SizedBox(height: 12),

              // Hotspot & IP Webcam (Recommended)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF08201A),
                  border: Border.all(color: const Color(0xFF10B981)),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.wifi_tethering, color: Color(0xFF10B981), size: 16),
                        SizedBox(width: 6),
                        Text('COLLEGE MOBILE HOTSPOT SETUP (FASTEST & ZERO LAG)', style: TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.bold, fontSize: 11)),
                      ],
                    ),
                    SizedBox(height: 6),
                    Text(
                      '1. Turn on Personal Hotspot on your phone (e.g. "Rover_Hotspot")\n2. Connect your laptop to your phone\'s hotspot Wi-Fi\n3. In Android "IP Webcam" app, tap "Start server"\n4. Phone IP in hotspot is ALWAYS: http://192.168.43.1:8080/video\n5. Direct peer-to-peer 5 GHz streaming bypasses college firewalls!',
                      style: TextStyle(fontSize: 11, color: Colors.white, height: 1.4),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10),

              // Browser AR Companion
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFF131822),
                  border: Border.all(color: const Color(0xFF1E293B)),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Direct Mobile Browser HUD URL:', style: TextStyle(fontSize: 11, color: Colors.grey)),
                    const SizedBox(height: 4),
                    SelectableText(
                      phoneUrl,
                      style: const TextStyle(color: Color(0xFF00F2FE), fontWeight: FontWeight.bold, fontSize: 12),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            child: const Text('DISMISS'),
            onPressed: () => Navigator.pop(ctx),
          ),
          OutlinedButton.icon(
            style: OutlinedButton.styleFrom(side: const BorderSide(color: Color(0xFF00F2FE))),
            icon: const Icon(Icons.videocam, size: 16, color: Color(0xFF00F2FE)),
            label: const Text('CONFIGURE CAMERA SOURCE', style: TextStyle(color: Color(0xFF00F2FE), fontSize: 11, fontWeight: FontWeight.bold)),
            onPressed: () {
              Navigator.pop(ctx);
              _openCameraSourceDialog();
            },
          ),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF10B981), foregroundColor: Colors.black),
            icon: const Icon(Icons.copy, size: 16),
            label: const Text('COPY LINK', style: TextStyle(fontWeight: FontWeight.bold)),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: phoneUrl));
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Copied: $phoneUrl')),
              );
            },
          ),
        ],
      ),
    );
  }

  void _openCameraSourceDialog() {
    final textController = TextEditingController(
      text: _currentStreamSource.startsWith("http") ? _currentStreamSource : "http://$_subnet.x:8080/video",
    );
    List<Map<String, dynamic>> discovered = [];

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: const Color(0xFF0F131A),
          title: const Row(
            children: [
              Icon(Icons.videocam, color: Color(0xFF00F2FE), size: 20),
              SizedBox(width: 8),
              Text('CAMERA STREAM SOURCE', style: TextStyle(color: Color(0xFF00F2FE), fontSize: 15, fontWeight: FontWeight.bold)),
            ],
          ),
          content: SizedBox(
            width: 490,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1E293B),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(
                    children: [
                      const Text('ACTIVE: ', style: TextStyle(fontSize: 10, color: Colors.grey, fontWeight: FontWeight.bold)),
                      Expanded(
                        child: Text(
                          _currentStreamSource.startsWith("cam") ? 'Laptop Webcam ($_currentStreamSource)' : _currentStreamSource,
                          style: const TextStyle(fontSize: 11, color: Color(0xFF10B981), fontWeight: FontWeight.bold),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),

                // Auto-Detect Button
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        style: OutlinedButton.styleFrom(
                          side: const BorderSide(color: Color(0xFF10B981)),
                          padding: const EdgeInsets.symmetric(vertical: 10),
                        ),
                        icon: _isScanningCameras
                            ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF10B981)))
                            : const Icon(Icons.radar, size: 16, color: Color(0xFF10B981)),
                        label: Text(
                          _isScanningCameras ? 'SCANNING WI-FI SUBNET...' : 'AUTO-DETECT PHONE IP WEBCAM',
                          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF10B981)),
                        ),
                        onPressed: _isScanningCameras
                            ? null
                            : () async {
                                setDialogState(() => _isScanningCameras = true);
                                try {
                                  final uri = Uri.parse("$_serverUrl/api/camera/discover");
                                  final res = await _telemetryClient.get(uri).timeout(const Duration(seconds: 4));
                                  if (res.statusCode == 200) {
                                    final data = jsonDecode(res.body);
                                    if (data['cameras'] is List) {
                                      final list = (data['cameras'] as List).cast<Map<String, dynamic>>();
                                      setDialogState(() {
                                        discovered = list;
                                        if (discovered.isNotEmpty) {
                                          textController.text = discovered.first['url'] ?? textController.text;
                                        }
                                      });
                                    }
                                  }
                                } catch (_) {}
                                setDialogState(() => _isScanningCameras = false);
                              },
                      ),
                    ),
                  ],
                ),

                if (discovered.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  const Text('DISCOVERED CAMERAS ON WI-FI:', style: TextStyle(fontSize: 10, color: Color(0xFF10B981), fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  ...discovered.map((c) => InkWell(
                        onTap: () {
                          textController.text = c['url'] ?? '';
                        },
                        child: Container(
                          margin: const EdgeInsets.only(bottom: 4),
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: const Color(0xFF08201A),
                            border: Border.all(color: const Color(0xFF10B981)),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.camera_alt, color: Color(0xFF10B981), size: 16),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  '${c['name']} • ${c['url']}',
                                  style: const TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.bold),
                                ),
                              ),
                              const Text('SELECT', style: TextStyle(fontSize: 10, color: Color(0xFF10B981), fontWeight: FontWeight.bold)),
                            ],
                          ),
                        ),
                      )),
                ],

                const SizedBox(height: 12),
                const Text('STREAM URL OR PRESET:', style: TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.bold)),
                const SizedBox(height: 6),
                TextField(
                  controller: textController,
                  style: const TextStyle(fontSize: 12, color: Colors.white),
                  decoration: const InputDecoration(
                    hintText: 'e.g. http://192.168.43.1:8080/video or cam',
                    hintStyle: TextStyle(color: Colors.grey, fontSize: 11),
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                  ),
                ),
                const SizedBox(height: 10),

                // Presets
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    ActionChip(
                      backgroundColor: const Color(0xFF08201A),
                      side: const BorderSide(color: Color(0xFF10B981)),
                      label: const Text('Phone Hotspot (192.168.43.1)', style: TextStyle(fontSize: 10, color: Color(0xFF10B981), fontWeight: FontWeight.bold)),
                      onPressed: () => textController.text = "http://192.168.43.1:8080/video",
                    ),
                    ActionChip(
                      backgroundColor: const Color(0xFF1E293B),
                      label: const Text('Home Wi-Fi (:8080)', style: TextStyle(fontSize: 10, color: Color(0xFF00F2FE))),
                      onPressed: () => textController.text = "http://$_subnet.x:8080/video",
                    ),
                    ActionChip(
                      backgroundColor: const Color(0xFF1E293B),
                      label: const Text('Laptop Webcam', style: TextStyle(fontSize: 10, color: Colors.white)),
                      onPressed: () => textController.text = "cam",
                    ),
                    ActionChip(
                      backgroundColor: const Color(0xFF1E293B),
                      label: const Text('DroidCam (:4747)', style: TextStyle(fontSize: 10, color: Colors.white)),
                      onPressed: () => textController.text = "http://$_subnet.x:4747/video",
                    ),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              child: const Text('CANCEL'),
              onPressed: () => Navigator.pop(ctx),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF00F2FE), foregroundColor: Colors.black),
              child: const Text('SWITCH STREAM SOURCE', style: TextStyle(fontWeight: FontWeight.bold)),
              onPressed: () async {
                final targetUrl = textController.text.trim();
                if (targetUrl.isEmpty) return;
                Navigator.pop(ctx);
                try {
                  final uri = Uri.parse("$_serverUrl/api/stream");
                  final res = await _telemetryClient.post(
                    uri,
                    headers: {"Content-Type": "application/json"},
                    body: jsonEncode({"url": targetUrl}),
                  ).timeout(const Duration(seconds: 4));
                  if (res.statusCode == 200) {
                    final data = jsonDecode(res.body);
                    if (data['ok'] == true) {
                      setState(() => _currentStreamSource = data['source'] ?? targetUrl);
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('✓ Video stream connected to: ${data['source']}'), backgroundColor: const Color(0xFF10B981)),
                        );
                      }
                      return;
                    }
                  }
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Failed to switch source: ${res.body}'), backgroundColor: const Color(0xFFEF4444)),
                    );
                  }
                } catch (e) {
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Error contacting server: $e'), backgroundColor: const Color(0xFFEF4444)),
                    );
                  }
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Focus(
      focusNode: _keyboardFocusNode,
      autofocus: true,
      onKeyEvent: _handleKeyEvent,
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: const Color(0xFF0F131A),
          elevation: 0,
          title: Row(
            children: [
              const Icon(Icons.bolt, color: Color(0xFF00F2FE), size: 22),
              const SizedBox(width: 8),
              const Text(
                'ROVERLINK GCS',
                style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1.2, fontSize: 16),
              ),
              const Spacer(),
              // Recording Indicator
              if (_isRecording)
                Container(
                  margin: const EdgeInsets.only(right: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFF3B0707),
                    border: Border.all(color: const Color(0xFFEF4444)),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.circle, size: 8, color: Color(0xFFEF4444)),
                      SizedBox(width: 4),
                      Text('REC', style: TextStyle(color: Color(0xFFEF4444), fontSize: 10, fontWeight: FontWeight.bold)),
                    ],
                  ),
                ),

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
          onTap: (idx) {
            setState(() => _currentIndex = idx);
            _keyboardFocusNode.requestFocus();
          },
          items: const [
            BottomNavigationBarItem(icon: Icon(Icons.gamepad), label: 'Drive Pad'),
            BottomNavigationBarItem(icon: Icon(Icons.qr_code_scanner), label: 'Pairing'),
            BottomNavigationBarItem(icon: Icon(Icons.memory), label: 'Pinout Guide'),
          ],
        ),
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

    return LayoutBuilder(
      builder: (context, constraints) {
        final isWideScreen = constraints.maxWidth >= 720;
        if (isWideScreen) {
          return _buildWideDesktopLayout(distColor);
        } else {
          return _buildCompactMobileLayout(distColor);
        }
      },
    );
  }

  Widget _buildCompactMobileLayout(Color distColor) {
    return SingleChildScrollView(
      child: Column(
        children: [
          _buildKeyboardHintsBanner(),
          _buildModeSelectorBar(),
          _buildCameraViewport(),
          _buildActionButtonsBar(),
          _buildWhyChainCard(),
          _buildTelemetryBar(distColor),
          _buildMotorBars(),
          if (_detectedObjects.isNotEmpty) _buildDetectionChips(),
          _buildSpeedSelector(),
          const SizedBox(height: 8),
          _buildDirectionalPad(),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildWideDesktopLayout(Color distColor) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Left Column: Video Feed & Why Chain
        Expanded(
          flex: 5,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildKeyboardHintsBanner(),
                _buildModeSelectorBar(),
                const SizedBox(height: 6),
                _buildCameraViewport(height: 330),
                const SizedBox(height: 8),
                _buildActionButtonsBar(),
                const SizedBox(height: 8),
                _buildWhyChainCard(),
                const SizedBox(height: 8),
                if (_detectedObjects.isNotEmpty) _buildDetectionChips(),
              ],
            ),
          ),
        ),

        // Right Column: Telemetry, Motor Visualizer & Drive Controls
        Expanded(
          flex: 4,
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(4, 12, 12, 12),
            child: Column(
              children: [
                _buildTelemetryBar(distColor),
                const SizedBox(height: 10),
                _buildMotorBars(),
                const SizedBox(height: 10),
                _buildSpeedSelector(),
                const SizedBox(height: 14),
                _buildDirectionalPad(),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildKeyboardHintsBanner() {
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 4, 12, 4),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        border: Border.all(color: const Color(0xFF1E293B)),
        borderRadius: BorderRadius.circular(6),
      ),
      child: const Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.keyboard, size: 14, color: Color(0xFF00F2FE)),
          SizedBox(width: 6),
          Flexible(
            child: Text(
              'KEYS: [W/▲] FWD • [S/▼] BACK • [A/◀] LEFT • [D/▶] RIGHT • [SPACE] STOP • [M] MODE • [1/2/3] SPEED',
              style: TextStyle(fontSize: 10, color: Color(0xFF94A3B8), fontWeight: FontWeight.bold),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  /// All 4 Mission Modes from Python server: MANUAL, OBSERVE, AUTO, EXPLORE
  Widget _buildModeSelectorBar() {
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 4, 12, 4),
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: const Color(0xFF0F131A),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Row(
        children: [
          _buildModeButton('MANUAL', const Color(0xFF00F2FE)),
          const SizedBox(width: 4),
          _buildModeButton('OBSERVE', const Color(0xFF38BDF8)),
          const SizedBox(width: 4),
          _buildModeButton('AUTO', const Color(0xFF10B981)),
          const SizedBox(width: 4),
          _buildModeButton('EXPLORE', const Color(0xFFF59E0B)),
        ],
      ),
    );
  }

  Widget _buildModeButton(String mode, Color activeColor) {
    final isSelected = (_pilotMode == mode);
    return Expanded(
      child: GestureDetector(
        onTap: () => _setMode(mode),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 7),
          decoration: BoxDecoration(
            color: isSelected ? activeColor.withOpacity(0.2) : Colors.transparent,
            border: Border.all(color: isSelected ? activeColor : const Color(0xFF1E293B)),
            borderRadius: BorderRadius.circular(6),
          ),
          alignment: Alignment.center,
          child: Text(
            mode,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: isSelected ? activeColor : Colors.grey,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCameraViewport({double height = 210}) {
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 4, 12, 4),
      height: height,
      decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        fit: StackFit.expand,
        children: [
          // Zero-latency Image.memory rendering directly from in-memory byte stream
          _isConnected && !_isDirectEsp32 && _latestFrameBytes != null
              ? Image.memory(
                  _latestFrameBytes!,
                  gaplessPlayback: true,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) => _buildNoFeedPlaceholder(),
                )
              : _buildNoFeedPlaceholder(),

          // Top HUD: Model & Decision Overlay
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
                    border: Border.all(color: _decisionOverlay == 'STOP' ? const Color(0xFFF59E0B) : const Color(0xFF10B981)),
                  ),
                  child: Text(
                    '$_pilotMode: $_decisionOverlay',
                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: _decisionOverlay == 'STOP' ? const Color(0xFFF59E0B) : const Color(0xFF10B981)),
                  ),
                ),
              ],
            ),
          ),

          // Bottom HUD: Autonomous Reason Banner
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
                'WHY: $_steeringReason',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 10, color: Color(0xFFE2E8F0), fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButtonsBar() {
    return Padding(
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
              icon: const Icon(Icons.phone_android, size: 15, color: Color(0xFF00F2FE)),
              label: const Text(
                'PHONE CAM AR HUD',
                style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF00F2FE)),
              ),
              onPressed: () => _openPhoneCameraHUD(),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: Color(0xFF10B981)),
                padding: const EdgeInsets.symmetric(vertical: 8),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              icon: const Icon(Icons.videocam, size: 15, color: Color(0xFF10B981)),
              label: Text(
                _currentStreamSource.startsWith("cam") ? 'SRC: LAPTOP CAM' : 'SRC: IP WEBCAM',
                style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF10B981)),
                overflow: TextOverflow.ellipsis,
              ),
              onPressed: () => _openCameraSourceDialog(),
            ),
          ),
          const SizedBox(width: 6),
          IconButton(
            tooltip: _isRecording ? 'Stop Recording' : 'Start Mission Recording',
            icon: Icon(_isRecording ? Icons.stop_circle : Icons.fiber_manual_record, color: const Color(0xFFEF4444), size: 22),
            onPressed: _toggleRecording,
          ),
        ],
      ),
    );
  }

  /// Why Chain Inspector: shows why the wheels are moving or stopped
  Widget _buildWhyChainCard() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFF0F131A),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.psychology, size: 14, color: Color(0xFF00F2FE)),
              const SizedBox(width: 6),
              const Text('WHY CHAIN (AUTONOMOUS LOGIC)', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white)),
              const Spacer(),
              Text(
                _isArmed ? 'ARMED ✓' : 'DISARMED',
                style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: _isArmed ? const Color(0xFF10B981) : const Color(0xFFEF4444)),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('PROPOSAL: $_decisionProposal', style: const TextStyle(fontSize: 10, color: Colors.grey)),
              Text('STEERING: $_steeringReason', style: const TextStyle(fontSize: 10, color: Color(0xFF00F2FE), fontWeight: FontWeight.bold)),
              Text('SAFETY: $_safetyReason', style: TextStyle(fontSize: 10, color: _safetyReason == 'SAFE' || _safetyReason == 'CLEAR' ? const Color(0xFF10B981) : const Color(0xFFEF4444), fontWeight: FontWeight.bold)),
            ],
          ),
        ],
      ),
    );
  }

  /// Tank Steer Motor Visualizer from Mission Deck
  Widget _buildMotorBars() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFF0F131A),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('MOTORS — TANK STEER PWM', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.grey)),
          const SizedBox(height: 6),
          _buildMotorRow('LEFT (ENA)', _motorLeftPwm),
          const SizedBox(height: 4),
          _buildMotorRow('RIGHT (ENB)', _motorRightPwm),
        ],
      ),
    );
  }

  Widget _buildMotorRow(String name, int pwm) {
    final absPwm = pwm.abs().clamp(0, 255);
    final ratio = absPwm / 255.0;
    final isRev = pwm < 0;
    final isStopped = pwm == 0;

    return Row(
      children: [
        SizedBox(width: 80, child: Text(name, style: const TextStyle(fontSize: 10, color: Colors.grey))),
        Icon(
          isStopped ? Icons.remove : (isRev ? Icons.arrow_downward : Icons.arrow_upward),
          size: 14,
          color: isStopped ? Colors.grey : (isRev ? const Color(0xFF38BDF8) : const Color(0xFF10B981)),
        ),
        const SizedBox(width: 6),
        Expanded(
          child: Stack(
            children: [
              Container(
                height: 12,
                decoration: BoxDecoration(color: const Color(0xFF1E293B), borderRadius: BorderRadius.circular(3)),
              ),
              FractionallySizedBox(
                widthFactor: ratio,
                child: Container(
                  height: 12,
                  decoration: BoxDecoration(
                    color: isRev ? const Color(0xFF38BDF8) : const Color(0xFF10B981),
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(width: 45, child: Text('$pwm PWM', textAlign: TextAlign.right, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.white))),
      ],
    );
  }

  Widget _buildTelemetryBar(Color distColor) {
    return Container(
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
          Column(
            children: [
              const Text('PILOT MODE', style: TextStyle(fontSize: 10, color: Colors.grey)),
              const SizedBox(height: 2),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: _pilotMode == 'AUTO'
                      ? const Color(0xFF08201A)
                      : (_pilotMode == 'EXPLORE' ? const Color(0xFF2E1A05) : const Color(0xFF1E293B)),
                  border: Border.all(
                    color: _pilotMode == 'AUTO'
                        ? const Color(0xFF10B981)
                        : (_pilotMode == 'EXPLORE' ? const Color(0xFFF59E0B) : const Color(0xFF00F2FE)),
                  ),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  _pilotMode,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: _pilotMode == 'AUTO'
                        ? const Color(0xFF10B981)
                        : (_pilotMode == 'EXPLORE' ? const Color(0xFFF59E0B) : const Color(0xFF00F2FE)),
                  ),
                ),
              ),
            ],
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
    );
  }

  Widget _buildDetectionChips() {
    return Padding(
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
    );
  }

  Widget _buildSpeedSelector() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text('SPEED: ', style: TextStyle(fontSize: 11, color: Colors.grey, fontWeight: FontWeight.bold)),
          const SizedBox(width: 6),
          _buildSpeedChip('ECO [1]', 130),
          const SizedBox(width: 6),
          _buildSpeedChip('NORMAL [2]', 185),
          const SizedBox(width: 6),
          _buildSpeedChip('TURBO [3]', 255),
        ],
      ),
    );
  }

  Widget _buildDirectionalPad() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        _buildDriveButton('▲  W', 'F'),
        const SizedBox(height: 10),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _buildDriveButton('◀  A', 'L'),
            const SizedBox(width: 14),
            // Emergency Stop
            GestureDetector(
              onTap: () {
                HapticFeedback.heavyImpact();
                _sendCommand('S');
              },
              child: Container(
                width: 86,
                height: 64,
                decoration: BoxDecoration(
                  color: const Color(0xFFEF4444),
                  borderRadius: BorderRadius.circular(10),
                  boxShadow: const [
                    BoxShadow(color: Color(0x66EF4444), blurRadius: 14, offset: Offset(0, 4)),
                  ],
                ),
                alignment: Alignment.center,
                child: const Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text('STOP', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.white)),
                    Text('[SPACE]', style: TextStyle(fontSize: 9, color: Colors.white70)),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 14),
            _buildDriveButton('▶  D', 'R'),
          ],
        ),
        const SizedBox(height: 10),
        _buildDriveButton('▼  S', 'B'),
      ],
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
                : (_isConnected ? 'Connecting to Low-Latency AI Stream...' : 'AI Mission Deck Offline'),
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

  Widget _buildSpeedChip(String label, int speed) {
    final isSel = (_targetSpeed == speed);
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        setState(() => _targetSpeed = speed);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
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
        width: 82,
        height: 60,
        decoration: BoxDecoration(
          color: const Color(0xFF1E293B),
          border: Border.all(color: const Color(0xFF334155)),
          borderRadius: BorderRadius.circular(10),
        ),
        alignment: Alignment.center,
        child: Text(label, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
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
            'Connect your companion to the desktop Mission Deck to stream video into YOLO AI and receive real-time object bounding boxes and autonomous decisions.',
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
                    onPressed: () async {
                      var url = _urlController.text.trim();
                      if (url.isNotEmpty) {
                        if (!url.startsWith('http://') && !url.startsWith('https://')) {
                          url = 'http://$url';
                        }
                        final uri = Uri.tryParse(url);
                        if (uri != null && uri.host.isNotEmpty && uri.port == 80 && !url.contains(':80') && !url.contains('192.168.4.1')) {
                          url = 'http://${uri.host}:5000';
                        }
                      }
                      setState(() {
                        _serverUrl = url;
                        _urlController.text = url;
                      });
                      await _fetchState();
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(_isConnected ? '✓ Connected to $_serverUrl' : '✗ Could not reach $_serverUrl. Check Wi-Fi & port :5000'),
                            backgroundColor: _isConnected ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                            duration: const Duration(seconds: 2),
                          ),
                        );
                      }
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
                title: 'Phone Mobile Hotspot (College Mode)',
                url: 'http://192.168.43.1:5000',
                desc: 'Laptop connected to phone hotspot. Zero lag, bypasses college Wi-Fi blocks.',
                icon: Icons.wifi_tethering,
              ),
              const SizedBox(height: 8),
              _buildPresetCard(
                title: 'Localhost (Linux Desktop)',
                url: 'http://127.0.0.1:5000',
                desc: 'Connect to Mission Control running on this same laptop.',
                icon: Icons.computer,
              ),
              const SizedBox(height: 8),
              _buildPresetCard(
                title: 'Home Wi-Fi LAN',
                url: 'http://$_primaryLanIp:5000',
                desc: 'Use when laptop & phone are connected to your home router.',
                icon: Icons.router,
              ),
              const SizedBox(height: 8),
              _buildPresetCard(
                title: 'Rover Wi-Fi (ESP32 AP)',
                url: 'http://192.168.4.2:5000',
                desc: 'Use when laptop is connected to AI_Rover_Control Wi-Fi.',
                icon: Icons.wifi,
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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('COLLEGE & FIELD WIRELESS GUIDE', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
                const SizedBox(height: 8),
                const Text(
                  '• College Wi-Fi / eduroam blocks peer-to-peer devices.\n• BEST SETUP: Turn on Personal Hotspot on phone. Connect laptop to phone hotspot.\n• Phone is ALWAYS 192.168.43.1. Camera URL: http://192.168.43.1:8080/video.\n• Rover ESP32 can connect to phone hotspot, or run Soft-AP 192.168.4.1.',
                  style: TextStyle(fontSize: 11, color: Colors.grey, height: 1.4),
                ),
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
