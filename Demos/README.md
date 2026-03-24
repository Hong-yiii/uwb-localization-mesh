# Demos

The **UWB localization pipeline** is the core product (packages + `Anchor_bring_up.py` + `Server_bring_up.py`). Demos are **optional compositions** on top.

| Path | Description |
|------|-------------|
| **[UnifiedDemo/](UnifiedDemo/README.md)** | **Reference PyQt app:** embeds `ServerBringUpProMax`, wires `AppBus` and tab widgets—useful as a **developer template** for building on the base stack (deploy + architecture in that README). |
| [Basic_render_graph/](Basic_render_graph/README.md) | Minimal matplotlib view of anchors + phone (separate-server workflow). See folder README. |

System overview, MQTT topics, and bring-up order: [repository root README](../README.md). Hands-on setup: [`dummies_setup_guide.md`](../dummies_setup_guide.md).
