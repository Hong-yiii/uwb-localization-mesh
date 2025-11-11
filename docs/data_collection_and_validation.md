---
layout: page
title: Data Collection and Validation
permalink: /data_collection_and_validation/
---

## 5. Data Collection and Validation

To ensure the accuracy and reliability of our system, we followed a rigorous data collection and validation process.

### Test Rig and Setup

We constructed a fixed test rig in the i-Lounge at EA-04-04 to ensure repeatability and eliminate confounding variables. The setup consists of four UWB anchors mounted on the ceiling in a rectangular configuration. The anchors are mounted with a 45° downward pitch to optimize their coverage of the test area.

![Test Rig](./assets/test_rig.png)

### Data Collection Process

We collected data at four fixed coordinates within the test rig. At each coordinate, we tested various orientations of the UWB transmitter (an iPhone) to account for the variations in signal strength and quality.

![Phone Orientations](./assets/phone_orientations.png)

The main aspects we evaluated were:

*   How the data changes with the user's movement throughout the area.
*   How the data changes with the rotation of the UWB device.
*   How the data varies with the addition of each UWB anchor.
*   How the output from our middleware compares with the raw coordinates.

This comprehensive data collection process allowed us to validate the performance of our system and make iterative improvements to our algorithms.
