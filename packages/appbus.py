"""
AppBus - Central Signal Hub for Application-Wide Communication

The AppBus implements a publish-subscribe pattern using Qt signals to decouple
producers (MainWindow polling server) from consumers (widgets). It ensures
thread-safe event delivery and provides a consistent communication interface
for all application components.

All inter-component communication flows through AppBus:
- Position updates: Server → MainWindow → AppBus → Widgets
- Audio commands: Widgets → AppBus → MainWindow → Server
- Event callbacks: Widget → AppBus → Other Widgets

Thread Safety:
Qt's signal system automatically ensures signals are delivered to the main thread,
making this pattern inherently thread-safe.
"""

from PyQt5.QtCore import QObject, pyqtSignal as Signal


class AppBus(QObject):
    """
    Central event bus for application-wide communication.
    
    All signals use Qt's signal/slot mechanism for thread-safe delivery.
    Widgets subscribe to signals they need and emit signals for commands/events.
    MainWindow routes command signals to the live server (ServerBringUp) methods.
    """
    
    # ============================================================
    # POSITION & TRACKING DATA (Server → Widgets)
    # ============================================================
    pointerUpdated = Signal(float, float, float, str)  # x_m, y_m, ts, source
    
    # ============================================================
    # ZONE EVENTS (Widgets → AppBus → Logging/Status)
    # ============================================================
    zoneRegistered = Signal(object, float, float, float, str)  # idx, x_m, y_m, ts, source
    zoneDeregistered = Signal(object, float, float, float, str)
    zoneSelected = Signal(object)  # zone object
    zoneCreated = Signal(object)  # zone object
    zoneDeleted = Signal(object)  # zone object
    zoneMoved = Signal(object, float, float)  # zone, new_x, new_y
    
    # ============================================================
    # PLAYBACK CONTROL COMMANDS (Widgets → MainWindow → Server)
    # ============================================================
    playRequested = Signal(str)           # source widget_id
    pauseRequested = Signal(str)          # source widget_id
    stopRequested = Signal(str)           # source widget_id
    skipRequested = Signal(str)           # source widget_id (next track)
    previousRequested = Signal(str)       # source widget_id (previous track)
    seekRequested = Signal(str, float)    # source, position (0.0-1.0)
    
    # ============================================================
    # AUDIO MODE COMMANDS (Widgets → MainWindow → Server)
    # ============================================================
    audioStartRequested = Signal(str, dict)  # mode ("adaptive"|"zone_dj"), params
    audioStopRequested = Signal(str)  # mode ("adaptive"|"zone_dj")
    adaptiveAudioEnabled = Signal(bool)   # enable/disable adaptive audio
    zoneDjEnabled = Signal(bool)          # enable/disable zone DJ
    bypassAudioRequested = Signal(bool)   # bypass all audio processing
    
    # ============================================================
    # PLAYLIST & VOLUME COMMANDS (Widgets → MainWindow → Server)
    # ============================================================
    playlistChangeRequested = Signal(int)  # playlist_number (1-5)
    playlistSelected = Signal(int)         # playlist_id
    shuffleToggled = Signal(bool)          # shuffle on/off
    repeatToggled = Signal(bool)           # repeat on/off
    volumeChangeRequested = Signal(int, int)  # device_id, volume (0-100); device_id=-1 for all
    globalVolumeChanged = Signal(int)      # master volume (0-100)
    
    # ============================================================
    # PLAYBACK STATE UPDATES (MainWindow → Widgets, bidirectional)
    # ============================================================
    playbackStateChanged = Signal(str, bool)  # widget_id, is_playing
    trackChanged = Signal(str, int)        # track_name, track_index
    playbackProgressChanged = Signal(float)  # progress 0.0-1.0
    queueUpdated = Signal(list, str)       # queue_preview (list of songs), current_track
    
    # ============================================================
    # VOLUME STATE UPDATES (MainWindow → Widgets)
    # ============================================================
    volumeUpdated = Signal(int, int)       # device_id, volume
    globalVolumeUpdated = Signal(int)      # master volume
    speakerVolumesUpdated = Signal(dict)   # {speaker_id: volume, ...} - all speaker volumes at once
    
    # ============================================================
    # SERVER STATUS
    # ============================================================
    serverStatusChanged = Signal(str)      # "running", "stopped", "error", "audio_playing"

    # ============================================================
    # FLOORPLAN INTERACTION EVENTS
    # ============================================================
    floorplanCornerMarked = Signal(int, float, float)  # corner_idx, x_px, y_px
    floorplanImageLoaded = Signal(str)     # image_path
    homographyComputed = Signal(object)    # homography_matrix (np.ndarray)
    
    # ============================================================
    # SETTINGS & CONFIGURATION
    # ============================================================
    settingsChanged = Signal(str, object)  # setting_key, value
    
    def __init__(self, parent=None):
        """
        Initialize the AppBus.
        
        Args:
            parent: Optional parent QObject (default: None)
        """
        super().__init__(parent)

