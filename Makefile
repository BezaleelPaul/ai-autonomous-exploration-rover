# AI Rover - build / test / flash helper
#
#   make            # help
#   make test       # 200+ Python tests + native C++ firmware tests
#   make compile    # compile both firmwares (no board attached)
#   make flash      # flash Uno + ESP32 (set PORT_UNO / PORT_ESP)
#   make smoke      # gateway bench test
#   make vision     # run the YOLO pilot
#
# Windows: use the same commands inside Git Bash, or run the underlying
# commands from docs/BRINGUP.md in PowerShell.

PY          ?= .venv/bin/python
PYTHON      ?= python3
PORT_UNO    ?= /dev/ttyACM0
PORT_ESP    ?= /dev/ttyUSB0
FQBN_UNO    ?= arduino:avr:uno
# Production safety inputs (E-stop contact + battery divider). Rear sensor optional:
#   make flash-prod-uno PROD_FLAGS="-DREQUIRE_ESTOP=1 -DBATTERY_SENSE=1 -DREAR_SONAR=1"
PROD_FLAGS  ?= -DREQUIRE_ESTOP=1 -DBATTERY_SENSE=1
ENC_FLAGS   ?= -DENCODERS=1
OTA_HOST    ?= 192.168.4.1
OTA_PASS    ?= roverota
ESPOTA      := $(firstword $(wildcard $(HOME)/.arduino15/packages/esp32/hardware/esp32/*/tools/espota.py))
KERNEL      ?= bezaleelpaul/ai-rover-coco-6-bootstrap
KERNEL24    ?= bezaleelpaul/ai-rover-coco-24
KERNEL_OUT  ?= /tmp/ai-rover-model
FQBN_ESP    ?= esp32:esp32:esp32doit-devkit-v1
LIBS        := --libraries firmware/libraries
UNO_SKETCH  := firmware/arduino/motion_safety
ESP_SKETCH  := firmware/esp32/wifi_bridge
TEST_SKETCH := firmware/arduino/wheel_test_hold
CAM_SKETCH  := firmware/esp32/esp32_cam_stream
BUILD_DIR   := build

.DEFAULT_GOAL := help
.PHONY: help setup test test-py test-native compile compile-uno compile-esp compile-test compile-cam \
        install-libs compile-prod-uno compile-encoders compile-esp-ota flash flash-uno flash-esp flash-esp32 \
        flash-prod-uno flash-encoders flash-test monitor-uno smoke teleop vision status sim soak ota-esp32 \
        dataset kaggle-pack clean

help:
	@echo "AI Rover targets"
	@echo "  setup          create .venv and install dependencies"
	@echo "  install-libs   copy AIRoverCore into the Arduino IDE sketchbook"
	@echo "  test           run Python + native C++ test suites"
	@echo "  compile        compile Uno and ESP32 firmware"
	@echo "  compile-prod-uno  Uno with E-stop + battery sensing ($(PROD_FLAGS))"
	@echo "  compile-encoders  Uno with closed-loop speed + odometry ($(ENC_FLAGS))"
	@echo "  flash-uno      flash firmware/arduino/motion_safety  (PORT_UNO=$(PORT_UNO))"
	@echo "  flash-esp32    flash firmware/esp32/wifi_bridge      (PORT_ESP=$(PORT_ESP))"
	@echo "  flash-prod-uno flash the production safety build     (PORT_UNO=$(PORT_UNO))"
	@echo "  flash-encoders flash the encoder build               (PORT_UNO=$(PORT_UNO))"
	@echo "  ota-esp32      wireless update                      (OTA_HOST=$(OTA_HOST))"
	@echo "  sim            virtual rover on :8090 (no hardware)"
	@echo "  soak           link/latency soak test"
	@echo "  kaggle-coco6   push the COCO-6 bootstrap training kernel"
	@echo "  kaggle-coco24  push the 24-class + edge-case training kernel"
	@echo "  kaggle-status  status of the bootstrap kernel ($(KERNEL))"
	@echo "  kaggle-logs    tail the bootstrap kernel logs"
	@echo "  kaggle-download pull the trained bundle to $(KERNEL_OUT)"
	@echo "  kaggle-status24 / kaggle-logs24 / kaggle-download24  (24-class run)"
	@echo "  flash-test     flash the isolated wheel test        (PORT_UNO=$(PORT_UNO))"
	@echo "  monitor-uno    open the Uno serial telemetry"
	@echo "  smoke          bench smoke test the ESP32 gateway"
	@echo "  teleop         keyboard teleop (HTTP)"
	@echo "  vision         run the YOLO autonomous pilot"
	@echo "  dataset        collect + prepare a Kaggle dataset"
	@echo "  clean          remove build artifacts and caches"

setup:
	./setup.sh

test: test-py test-native

test-py:
	$(PYTHON) -m pytest -q

test-native:
	@mkdir -p $(BUILD_DIR)
	g++ -std=c++17 -Wall -Wextra -Werror -I firmware/libraries/AIRoverCore/src \
	    tests/native/test_safety_core.cpp -o $(BUILD_DIR)/test_safety_core
	./$(BUILD_DIR)/test_safety_core

install-libs:
	./scripts/install_arduino_library.sh

compile: compile-uno compile-esp

compile-uno:
	arduino-cli compile --fqbn $(FQBN_UNO) $(LIBS) $(UNO_SKETCH)

compile-esp:
	arduino-cli compile --fqbn $(FQBN_ESP) $(LIBS) $(ESP_SKETCH)

compile-prod-uno:
	arduino-cli compile --fqbn $(FQBN_UNO) $(LIBS) --output-dir $(BUILD_DIR)/uno-prod \
	    --build-property "compiler.cpp.extra_flags=$(PROD_FLAGS)" $(UNO_SKETCH)

compile-encoders:
	arduino-cli compile --fqbn $(FQBN_UNO) $(LIBS) --output-dir $(BUILD_DIR)/uno-enc \
	    --build-property "compiler.cpp.extra_flags=$(PROD_FLAGS) $(ENC_FLAGS)" $(UNO_SKETCH)

compile-esp-ota:
	arduino-cli compile --fqbn $(FQBN_ESP) $(LIBS) --output-dir $(BUILD_DIR)/esp32 $(ESP_SKETCH)

compile-test:
	arduino-cli compile --fqbn $(FQBN_UNO) $(LIBS) $(TEST_SKETCH)

compile-cam:
	arduino-cli compile --fqbn esp32:esp32:esp32cam $(LIBS) $(CAM_SKETCH)

flash: flash-uno flash-esp32

flash-uno: compile-uno
	arduino-cli upload -p $(PORT_UNO) --fqbn $(FQBN_UNO) $(UNO_SKETCH)

flash-esp32: flash-esp

flash-esp: compile-esp
	arduino-cli upload -p $(PORT_ESP) --fqbn $(FQBN_ESP) $(ESP_SKETCH)

flash-prod-uno: compile-prod-uno
	arduino-cli upload -p $(PORT_UNO) --fqbn $(FQBN_UNO) --input-dir $(BUILD_DIR)/uno-prod

flash-encoders: compile-encoders
	arduino-cli upload -p $(PORT_UNO) --fqbn $(FQBN_UNO) --input-dir $(BUILD_DIR)/uno-enc

ota-esp32: compile-esp-ota
	@test -n "$(ESPOTA)" || (echo "espota.py not found; update the ESP32 core or use the Arduino IDE" && exit 1)
	python $(ESPOTA) -i $(OTA_HOST) -p 3232 -P $(OTA_PASS) -f $(BUILD_DIR)/esp32/wifi_bridge.ino.bin

kaggle-coco6:
	kaggle kernels push -p kaggle/coco6

kaggle-status:
	kaggle kernels status $(KERNEL)

kaggle-logs:
	kaggle kernels logs $(KERNEL)

kaggle-download:
	mkdir -p $(KERNEL_OUT)
	kaggle kernels output $(KERNEL) -p $(KERNEL_OUT) \
	    --file-pattern 'rover6_bundle\.zip|val_summary\.json|dataset_stats\.json' -o

kaggle-coco24:
	kaggle kernels push -p kaggle/coco24

kaggle-status24:
	kaggle kernels status $(KERNEL24)

kaggle-logs24:
	kaggle kernels logs $(KERNEL24)

kaggle-download24:
	mkdir -p $(KERNEL_OUT)
	kaggle kernels output $(KERNEL24) -p $(KERNEL_OUT) \
	    --file-pattern 'rover24_bundle\.zip|val_summary\.json|edge_cases\.json|dataset_stats\.json' -o

sim:
	$(PYTHON) simulator/virtual_rover.py --port 8090

soak:
	$(PYTHON) scripts/soak_test.py

flash-test: compile-test
	arduino-cli upload -p $(PORT_UNO) --fqbn $(FQBN_UNO) $(TEST_SKETCH)

monitor-uno:
	arduino-cli monitor -p $(PORT_UNO) --config baudrate=115200

smoke:
	$(PYTHON) scripts/bench_smoke_test.py

teleop:
	$(PYTHON) scripts/teleop_cli.py

vision:
	$(PYTHON) scripts/ai_video_server.py

dataset:
	$(PYTHON) scripts/collect_dataset.py --auto-label
	$(PYTHON) scripts/prepare_dataset.py --raw datasets/raw --zip

kaggle-pack:
	$(PYTHON) scripts/prepare_dataset.py --raw datasets/raw --zip

clean:
	rm -rf $(BUILD_DIR) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
