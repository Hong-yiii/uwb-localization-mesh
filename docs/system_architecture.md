---
layout: page
title: System Architecture
permalink: /system_architecture/
---

## 2. System Architecture

Our system is designed with a three-layer architecture to ensure modularity, scalability, and real-time performance.

![System Architecture Diagram](./assets/Overall_detailed_system_arch.png)

### The Three Layers:

1.  **Edge Layer:** This layer consists of multiple NXP Type-2BP UWB modules that act as anchors. These anchors collect Time-of-Flight (ToF) and Angle-of-Arrival (AoA) data from a UWB-enabled device, such as an iPhone, which acts as the transmitter.

2.  **Communication Layer:** A distributed MQTT (Message Queuing Telemetry Transport) Pub-Sub framework forms the backbone of our communication layer. Each anchor publishes its data over Wi-Fi to a central broker. This lightweight and scalable solution ensures resilient communication across multiple rooms.

3.  **Processing Layer:** This is the core of our middleware. A Pose Graph Optimization (PGO) algorithm fuses the data from all anchors to produce a globally consistent position estimate. This layer also includes outlier rejection and a sliding-window filter to reduce noise and reject erroneous readings in real-time.
