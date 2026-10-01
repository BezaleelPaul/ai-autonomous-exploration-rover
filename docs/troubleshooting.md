# Troubleshooting

- Camera FAIL: check ESP32 IP in config.yaml camera.esp32_url; test in browser
  http://<ip>:81/stream; lower to QVGA if latency high; --mock to bypass.
- Serial not found: correct config.yaml serial.port (COMx / /dev/ttyUSB0);
  close Arduino IDE monitor; check USB cable is data-capable.
- No detections: backend=mock always emits (for pipeline tests); backend=color
  needs green object + opencv installed; backend=hf needs torch+transformers and
  one-time model download (then offline from HF cache).
- Rover spins forever: search_timeout_s / max_search_rotations cap it; check logs.
- Oscillates L/R: increase min_command_duration_s / center_tolerance.
- Motors run on exit: CTRL+C triggers shutdown STOP; Arduino also stops after 3s
  without commands. Always verify wheels off ground on first run.
