---
layout: page
title: Software Engineering
permalink: /software_engineering/
---

## 6. SWE Structure, Packages etc.

Our system is built on a robust and modular software architecture that is designed for scalability and ease of use.

### Publish-Subscribe Architecture

We use a publish-subscribe (pub-sub) architecture based on MQTT for communication between the UWB anchors and the central processing unit. This decoupled approach allows for a flexible and scalable system where anchors can be added or removed without affecting the overall system.

### Modular Design

The entire system is designed with a clear separation of concerns, which makes it easy to maintain and extend. The core functionalities are divided into three distinct layers:

*   **Hardware Layer:** Interacts with the UWB hardware.
*   **Communication Layer:** Handles data transfer using MQTT.
*   **Processing Layer:** Performs the PGO calculations and other optimizations.

### Python Packages

We have packaged the core functionalities of our system into easy-to-use Python packages. This allows developers to quickly integrate our localization middleware into their own applications with just a few lines of code.

Here's an example of how to bring up the system:

```python
# Configure MQTT with your laptop's IP
mqtt_config = MQTTConfig(
    broker="192.168.68.66",  # Replace with your laptop's IP
    port=1884
)

# Start server
server = ServerBringUp(
    mqtt_config=mqtt_config,
    window_size_seconds=1.0
)

try:
    server.start()
    print("Server started. Waiting for anchor connections...")
    while True:
        if server.user_position is not None:
            print(f"Current position: {server.user_position}")
        time.sleep(1)
except KeyboardInterrupt:
    server.stop()
```

This simple and intuitive API makes it easy for developers to focus on building their applications without having to worry about the complexities of the underlying localization technology.
