# ESP32-CAM -> Laptop -> Arduino pipeline. Safety gates every movement.

```
ESP32-CAM --WiFi MJPEG--> ESP32Stream -> FrameManager -+
                                                       v
                                              Detector (mock|color|hf)
                                                       v
                                              ObjectTracker -> SceneAnalyzer
                                                       v
                                              steering.py (mapping + AntiOscillation)
                                                       v
                                              ObstacleAvoidance
                                                       v
                                              SafetyManager --ALLOW?--> ArduinoSerial
                                                                              |
                                                                              v
                                                              Arduino UNO + L298N + HC-SR04
```

States: IDLE MANUAL OBSERVE SEARCHING ALIGNING APPROACHING AVOIDING STOPPED EMERGENCY_STOP ERROR.
Closed loop: PERCEIVE -> LOCALIZE -> DECIDE -> SAFETY -> CONTROL -> FEEDBACK -> REASSESS.
AI never drives motors directly. Arduino has its own emergency stop + comm-timeout stop.
