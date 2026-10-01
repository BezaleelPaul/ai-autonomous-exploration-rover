# 34. Research Notes & Engineering Trade-Offs

**Document ID:** DOC-RES-001  

## 1. Architectural Insights & Technical Trade-Offs

- **Bipolar L298N vs. MOSFET Driver:** The legacy L298N driver exhibits an internal saturation drop of $1.8$ V to $2.5$ V, dissipating substantial heat. Modern MOSFET drivers (e.g. TB6612FNG) offer $< 0.2$ V drop and 95%+ efficiency. L298N was retained for educational accessibility but is marked for hardware revision.
- **Microcontroller UART Decoupling:** Isolating perception on an ESP32 while delegating hard safety to an Arduino UNO proved vastly more reliable than single-board computer architectures, preventing software thread starvation from inducing physical crashes.
