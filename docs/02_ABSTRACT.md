# 02. Abstract

**Project Title:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  

### Abstract

Autonomous ground vehicles operating in resource-constrained environments require robust visual perception, agile trajectory tracking, and deterministically guaranteed obstacle avoidance without the weight, thermal dissipation, and power consumption of desktop-class computers. This project develops a low-cost, distributed dual-microcontroller differential drive rover that partitions computationally intensive vision tasks from hard real-time safety control. 

An ESP32-CAM coprocessor captures optical video at VGA resolution, applies contrast-limited adaptive histogram equalization (CLAHE), estimates target centroid displacement, and executes an anti-oscillatory finite state machine. Movement commands are transmitted across an electrically isolated, level-shifted serial link to an Arduino UNO supervisor. The supervisor enforces hard real-time safety through an independent 3000 ms communication watchdog and front-mounted HC-SR04 ultrasonic obstacle interlock (< 15.0 cm), driving an L298N dual H-bridge motor controller. 

Kinematic modeling and proportional steering control ($K_p = 0.6$) demonstrate responsive target alignment with settling times under 2.5 seconds in simulation. Empirical verification protocols across 32 standardized test scenarios demonstrate failsafe behavior under visual occlusion, communication disconnect, and electrical transients. The platform achieves fully self-contained edge autonomy at an estimated prototype bill of materials under $35.00 USD.
