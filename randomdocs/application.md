# UWB Localization Platform - Application Architecture

> **Note:** The standalone `Demos/PyQT_Visualisation/` demo was removed; the shipping desktop app is **`Demos/UnifiedDemo/`** (PyQt5 tabs: PGO plot, adaptive audio, zone DJ).

## Marketing Overview: Build Amazing Apps in Minutes, Not Months

```mermaid
graph TB
    subgraph "🏗️ UWB Localization Platform"
        CORE[📦 Core Packages<br/>Ready-to-use components]
        SERVER[🖥️ Server<br/>Real or simulated data]
    end
    
    subgraph "🎨 Your Custom App"
        APP[🖼️ Unified Demo (PyQt)<br/>• Live PGO path<br/>• Floorplan + homography<br/>• Zones & spatial audio tabs]
    end
    
    CORE --> APP
    SERVER --> APP
    
    CORE -.->|"Just import & use"| TEXT1["✨ No complex setup<br/>✨ No reinventing algorithms<br/>✨ Focus on YOUR features"]
    
    classDef platform fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    classDef app fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px
    classDef benefit fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    
    class CORE,SERVER platform
    class APP app
    class TEXT1 benefit
```

## The Message
**"Our baseline packages do the heavy lifting. You build the magic."**

- **Left side**: Robust, tested foundation
- **Right side**: Your creative application  
- **Arrow**: Seamless integration
- **Bottom**: The developer benefits
