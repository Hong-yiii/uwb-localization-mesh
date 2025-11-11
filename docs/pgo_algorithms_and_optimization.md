---
layout: page
title: PGO, Algorithms, and Optimization
permalink: /pgo_algorithms_and_optimization/
---

## 3. PGO, Algorithms, and Optimization

At the heart of our middleware is a Pose Graph Optimization (PGO) algorithm. This approach treats the localization problem as a graph, where the UWB anchors are nodes and the measurements between them are edges. By minimizing the error across the entire graph, we can fuse the data from multiple anchors to achieve a more accurate and reliable position estimate.

### Optimizing PGO Inputs

The performance of the PGO system is highly dependent on the quality of the input edges. To ensure the best possible inputs, we have implemented several optimization techniques:

*   **Sliding Window:** Instead of running PGO on every new data point (which can be noisy), we use a 2-second sliding window to average out noise and update the datapoints in larger steps.
*   **Outlier Rejection:** We've implemented checks to reject "very wrong" measurements that could skew the sliding window average. This filter rejects approximately 10.05% of the data, which are identified as statistical outliers.
*   **Dynamic Anchor Disabling:** If an anchor is performing poorly and its variance is too high, we can temporarily disable it from the PGO calculation to prevent it from corrupting the overall estimate.

### Performance Gains

The following "God Plot" illustrates the performance improvement achieved through our PGO algorithm and optimization techniques. It shows how the accuracy improves as we add more anchors to the system.

![God Plot](./assets/god_plot_v5_orientation_A.png)

As you can see, the estimated position (in red) gets closer to the ground truth (the center of the crosshairs) as we increase the number of anchors from 1 to 4. This demonstrates the effectiveness of our sensor fusion approach.
