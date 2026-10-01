/*
 * AI Visual Smart Rover — ESP32-CAM stream
 * Board: AI Thinker ESP32-CAM. Stream: http://<ip>:81/stream
 * Adjust WIFI_SSID / WIFI_PASS before flashing.
 */
#include "esp_camera.h"
#include <WiFi.h>

#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASS "YOUR_WIFI_PASSWORD"

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#include "esp_http_server.h"

httpd_handle_t stream_httpd = NULL;

static esp_err_t stream_handler(httpd_req_t *req) {
  httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=frame");
  char part[64];
  while (true) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) { vTaskDelay(pdMS_TO_TICKS(100)); continue; }
    size_t hlen = snprintf(part, sizeof(part),
      "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
    if (httpd_resp_send_chunk(req, part, hlen) != ESP_OK) { esp_camera_fb_return(fb); break; }
    if (httpd_resp_send_chunk(req, (const char*)fb->buf, fb->len) != ESP_OK) { esp_camera_fb_return(fb); break; }
    httpd_resp_send_chunk(req, "\r\n", 2);
    esp_camera_fb_return(fb);
  }
  return ESP_OK;
}

static void start_server() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;
  httpd_uri_t uri = {.uri="/stream", .method=HTTP_GET, .handler=stream_handler, .user_ctx=NULL};
  if (httpd_start(&stream_httpd, &config) == ESP_OK) httpd_register_uri_handler(stream_httpd, &uri);
}

void setup() {
  Serial.begin(115200);
  camera_config_t c;
  c.ledc_channel = LEDC_CHANNEL_0; c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0=Y2_GPIO_NUM; c.pin_d1=Y3_GPIO_NUM; c.pin_d2=Y4_GPIO_NUM; c.pin_d3=Y5_GPIO_NUM;
  c.pin_d4=Y6_GPIO_NUM; c.pin_d5=Y7_GPIO_NUM; c.pin_d6=Y8_GPIO_NUM; c.pin_d7=Y9_GPIO_NUM;
  c.pin_xclk=XCLK_GPIO_NUM; c.pin_pclk=PCLK_GPIO_NUM; c.pin_vsync=VSYNC_GPIO_NUM;
  c.pin_href=HREF_GPIO_NUM; c.pin_sscb_sda=SIOD_GPIO_NUM; c.pin_sscb_scl=SIOC_GPIO_NUM;
  c.pin_pwdn=PWDN_GPIO_NUM; c.pin_reset=RESET_GPIO_NUM;
  c.xclk_freq_hz=20000000; c.pixel_format=PIXFORMAT_JPEG;
  c.frame_size=FRAMESIZE_VGA; c.jpeg_quality=12; c.fb_count=2;
  if (esp_camera_init(&c) != ESP_OK) { Serial.println("CAM FAIL"); return; }
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int t=0; while (WiFi.status()!=WL_CONNECTED && t<60) { delay(500); t++; }
  Serial.println(WiFi.localIP());
  start_server();
}

void loop() {
  // R6: reconnect if Wi-Fi drops (laptop side already retries the stream).
  static unsigned long lastCheck = 0;
  if (millis() - lastCheck >= 5000) {
    lastCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("WIFI: lost, reconnecting...");
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASS);
    } else {
      static bool wasConnected = false;
      if (!wasConnected) { wasConnected = true; Serial.println(WiFi.localIP()); }
    }
  }
  delay(1000);
}
