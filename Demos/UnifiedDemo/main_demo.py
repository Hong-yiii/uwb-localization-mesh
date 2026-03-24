
import sys
import os
import glob
import time
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFileDialog, QAction, QToolBar, QMessageBox, QDialog, QDialogButtonBox,
    QFormLayout, QDoubleSpinBox, QLineEdit, QPushButton
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QSize

def _import_pkg_fallback():
    # Allow running from a repo where 'packages' are siblings of Demos/
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))
    
    # Add packages directory
    pkgs_path = os.path.join(repo_root, "packages")
    if os.path.isdir(pkgs_path) and pkgs_path not in sys.path:
        sys.path.insert(0, pkgs_path)

    # This directory (server_bring_up_with_audio.py lives here)
    unified_dir = os.path.abspath(os.path.dirname(__file__))
    if unified_dir not in sys.path:
        sys.path.insert(0, unified_dir)

    # Also add repo root (for packages.* imports in the server module)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

# Add packages to path BEFORE importing
_import_pkg_fallback()

# Now import from packages
from appbus import AppBus
from services.settings import load_settings

def _mqtt_config_from_settings(settings):
    """Broker settings for real hardware (same defaults as server_bring_up_with_audio)."""
    from packages.uwb_mqtt_server.config import MQTTConfig

    broker = settings.value("mqtt/broker", "localhost", type=str)
    port = settings.value("mqtt/port", 1884, type=int)
    user = settings.value("mqtt/username", "laptop", type=str)
    password = settings.value("mqtt/password", "laptop", type=str)
    return MQTTConfig(
        broker=broker.strip() or "localhost",
        port=port,
        username=user.strip() or None,
        password=password or None,
    )


def _start_server_bringup(settings):
    """
    Start ServerBringUpProMax from Demos/UnifiedDemo/server_bring_up_with_audio.py.

    Expects a running MQTT broker and UWB anchors publishing measurements (see repo README).
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        from server_bring_up_with_audio import ServerBringUpProMax

        mqtt_config = _mqtt_config_from_settings(settings)
        sb = ServerBringUpProMax(mqtt_config=mqtt_config)
        if hasattr(sb, "start"):
            sb.start()
        print(
            f"[UnifiedDemo] ServerBringUpProMax started "
            f"(MQTT {mqtt_config.broker}:{mqtt_config.port})"
        )
        return sb
    except Exception as e:
        print(f"[UnifiedDemo] ServerBringUpProMax failed: {e}")
        return None

def _load_pgo_widget(app_bus, services, settings):
    try:
        from pgo_data_widget import PgoPlotWidget
        return PgoPlotWidget(app_bus, services, settings)
    except Exception as e:
        w = QWidget(); QVBoxLayout(w).addWidget(QLabel(f"PGO Data widget not installed.\n{e}", w))
        return w

def _load_adaptive_widget(app_bus, services, settings):
    try:
        from adaptive_audio_widget import AdaptiveAudioWidget
        return AdaptiveAudioWidget(app_bus, services, settings)
    except Exception as e:
        w = QWidget(); QVBoxLayout(w).addWidget(QLabel(f"Adaptive Audio widget not installed.\n{e}", w))
        return w

def _load_zonedj_widget(app_bus, services, settings):
    try:
        from zone_dj_widget import ZoneDjWidget
        return ZoneDjWidget(app_bus, services, settings)
    except Exception as e:
        w = QWidget(); QVBoxLayout(w).addWidget(QLabel(f"Zone DJ widget not installed.\n{e}", w))
        return w


class _SettingsDialog(QDialog):
    """Settings dialog for zone radius and default floorplan path."""
    
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(500, 200)
        
        layout = QFormLayout(self)
        
        # Zone radius
        self.radius_spinbox = QDoubleSpinBox()
        self.radius_spinbox.setRange(0.01, 10.0)
        self.radius_spinbox.setSingleStep(0.05)
        self.radius_spinbox.setSuffix(" m")
        self.radius_spinbox.setDecimals(2)
        current_radius = settings.value("zonedj/default_zone_radius_m", 0.25, type=float)
        self.radius_spinbox.setValue(current_radius)
        layout.addRow("Zone Radius:", self.radius_spinbox)
        
        # Default floorplan path
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        current_path = settings.value("floorplan/default_path", "", type=str)
        self.path_edit.setText(current_path)
        path_layout.addWidget(self.path_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(browse_btn)
        layout.addRow("Default Floorplan Path:", path_layout)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def _browse_path(self):
        """Browse for floorplan file."""
        start_dir = self.path_edit.text() if self.path_edit.text() else os.path.expanduser("~")
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Default Floorplan", start_dir, "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if filename:
            self.path_edit.setText(filename)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UWB Localization Visualization - Unified Demo")
        self.resize(1400, 900)

        # Load settings
        self.settings = load_settings()

        # Create AppBus
        self.bus = AppBus()

        # Build services dictionary (passed to widgets)
        self.services = {
            "settings": self.settings
        }
        
        # Create shared FloorplanView instance (used by both Adaptive Audio and Zone DJ)
        from viz_floorplan.floorplan_view import FloorplanView
        self.shared_floorplan = FloorplanView(
            world_width_m=self.settings.value("world/width_m", 4.80, type=float),
            world_height_m=self.settings.value("world/height_m", 6.00, type=float),
            grid_cols=self.settings.value("grid/cols", 8, type=int),
            grid_rows=self.settings.value("grid/rows", 10, type=int),
            default_zone_radius_m=self.settings.value("zonedj/default_zone_radius_m", 0.25, type=float),
            parent=None  # No parent, will be reparented by widgets
        )
        # Add shared floorplan to services
        self.services["shared_floorplan"] = self.shared_floorplan

        # Create and start server
        self.server = _start_server_bringup(self.settings)
        if self.server is None:
            QMessageBox.critical(
                self,
                "Server Error",
                "Failed to start ServerBringUpProMax (Demos/UnifiedDemo/server_bring_up_with_audio.py).\n\n"
                "Run Mosquitto, set mqtt/broker in QSettings if the broker is not localhost, "
                "and ensure anchors are publishing. See repository README.",
            )
            return

        # Add server to services for direct access by widgets
        self.services["server"] = self.server

        # Connect AppBus signals to server methods (routing layer)
        self._connect_appbus_signals()

        # Setup polling timers
        self._last_position = None
        self._last_volumes = {}

        # Position polling (20Hz)
        poll_rate_hz = self.settings.value("server/poll_rate_hz", 20, type=int)
        poll_interval_ms = 1000 // poll_rate_hz
        self._position_timer = QTimer()
        self._position_timer.timeout.connect(self._poll_server_position)
        self._position_timer.start(poll_interval_ms)  # Default: 50ms = 20Hz

        # Queue/playback state polling (1Hz - less frequent)
        self._queue_timer = QTimer()
        self._queue_timer.timeout.connect(self._poll_playback_state)
        self._queue_timer.start(1000)  # 1Hz
        
        # Speaker volumes polling timer (5Hz = 200ms)
        self._speaker_volumes_timer = QTimer()
        self._speaker_volumes_timer.timeout.connect(self._poll_speaker_volumes)
        self._speaker_volumes_timer.start(200)  # 5Hz

        # UI
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self._build_menu_bar()
        self._build_tabs()
        self._build_toolbar()
        self._apply_light_theme()
        
        # Initialize toolbar state based on initial tab (PGO Data - disable Place Zones)
        if hasattr(self, 'act_place_zones'):
            self.act_place_zones.setEnabled(False)

        # Status bar
        self.bus.serverStatusChanged.connect(self._on_server_status_changed)
        self.statusBar().showMessage("Server: starting…")
        if self.server:
            self.bus.serverStatusChanged.emit("running")

        # Default floorplan load (same folder as main demo)
        self._default_load_floorplan()

    # ---- Menu Bar ----
    def _build_menu_bar(self):
        """Build menu bar (File, Edit, View, Tools, Help)"""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("File")
        act_new = file_menu.addAction("New Session")
        act_open = file_menu.addAction("Open Floorplan...")
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._open_image)
        file_menu.addSeparator()
        act_save = file_menu.addAction("Save Configuration...")
        act_save.setShortcut("Ctrl+S")
        act_export = file_menu.addAction("Export Data...")
        act_export.setShortcut("Ctrl+E")
        file_menu.addSeparator()
        act_exit = file_menu.addAction("Exit")
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        
        # Edit Menu
        edit_menu = menubar.addMenu("Edit")
        act_prefs = edit_menu.addAction("Preferences...")
        act_prefs.setShortcut("Ctrl+,")
        act_settings = edit_menu.addAction("Settings...")
        
        # View Menu
        view_menu = menubar.addMenu("View")
        act_toolbar = view_menu.addAction("Toolbar")
        act_toolbar.setCheckable(True)
        act_toolbar.setChecked(True)
        act_statusbar = view_menu.addAction("Status Bar")
        act_statusbar.setCheckable(True)
        act_statusbar.setChecked(True)
        view_menu.addSeparator()
        act_fullscreen = view_menu.addAction("Fullscreen")
        act_fullscreen.setShortcut("F11")
        
        # Tools Menu
        tools_menu = menubar.addMenu("Tools")
        act_reset = tools_menu.addAction("Reset Position")
        
        # Help Menu
        help_menu = menubar.addMenu("Help")
        act_guide = help_menu.addAction("User Guide")
        help_menu.addSeparator()
        act_about = help_menu.addAction("About")

    # ---- Tabs ----
    def _build_tabs(self):
        """Build tab widgets (they communicate via AppBus, not server directly)."""
        self.tab_pgo = _load_pgo_widget(self.bus, self.services, self.settings)
        self.tab_adaptive = _load_adaptive_widget(self.bus, self.services, self.settings)
        self.tab_zonedj = _load_zonedj_widget(self.bus, self.services, self.settings)

        self.tabs.addTab(self.tab_pgo, "PGO Data")
        self.tabs.addTab(self.tab_adaptive, "Adaptive Audio")
        self.tabs.addTab(self.tab_zonedj, "Zone DJ")

        # Connect tab change signal to handle floorplan reparenting
        self.tabs.currentChanged.connect(self._on_tab_changed)
        
        # Connect floorplan signals for coordinate mapping display
        self._connect_floorplan_signals()
    
    def _connect_floorplan_signals(self):
        """Connect floorplan signals for coordinate mapping display."""
        if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
            self.shared_floorplan.pixelToMeterMapped.connect(self._on_pixel_to_meter_mapped)
    
    def _on_pixel_to_meter_mapped(self, x_px: float, y_px: float, x_m: float, y_m: float):
        """Handle pixel-to-meter mapping signal from floorplan."""
        # Update status bar with pixel and meter coordinates
        self._update_status_bar_coords(x_px, y_px, x_m, y_m)
    
    def _update_status_bar_coords(self, x_px: float = None, y_px: float = None, 
                                   x_m: float = None, y_m: float = None):
        """Update status bar with coordinate information."""
        parts = []
        
        # Add pixel coordinates if available
        if x_px is not None and y_px is not None:
            parts.append(f"Pixel: ({x_px:.0f}, {y_px:.0f})")
        
        # Add meter coordinates if available
        if x_m is not None and y_m is not None:
            parts.append(f"Meter: ({x_m:.2f}m, {y_m:.2f}m)")
        
        # Add server status
        parts.append("Server: running")
        
        self.statusBar().showMessage(" | ".join(parts))
    
    def _on_tab_changed(self, index):
        """Handle tab change - reparent shared floorplan to active widget and update toolbar."""
        current_widget = self.tabs.currentWidget()
        
        # Handle tab switching for Adaptive Audio (no zones needed anymore)
        if current_widget == self.tab_adaptive:
            # Enable speaker visualization for Adaptive Audio
            if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
                self.shared_floorplan.set_show_speakers(True)
                # Set speaker positions if server is available
                if self.server:
                    positions = self.server.get_speaker_positions()
                    if positions:
                        self.shared_floorplan.set_speaker_positions(positions)
        else:
            # Disable speaker visualization for other tabs
            if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
                self.shared_floorplan.set_show_speakers(False)
        
        # Enable/disable Place Zones button based on active tab
        # Only Zone DJ supports zone placement, Adaptive Audio does not
        if hasattr(self, 'act_place_zones'):
            if current_widget == self.tab_zonedj:
                # Enable Place Zones for Zone DJ
                self.act_place_zones.setEnabled(True)
            elif current_widget == self.tab_adaptive:
                # Disable Place Zones for Adaptive Audio
                self.act_place_zones.setEnabled(False)
                self.act_place_zones.setChecked(False)
                # Ensure zone placement is disabled
                if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
                    self.shared_floorplan.toggle_place_zones(False)
            else:
                # Disable for other tabs (PGO Data)
                self.act_place_zones.setEnabled(False)
                self.act_place_zones.setChecked(False)
                # Ensure zone placement is disabled
                if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
                    self.shared_floorplan.toggle_place_zones(False)
        
        # Only handle reparenting for widgets that use floorplan
        if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
            # Check if current widget uses the shared floorplan
            if current_widget and hasattr(current_widget, 'floorplan'):
                if current_widget.floorplan == self.shared_floorplan:
                    # Get the current layout
                    current_layout = current_widget.layout()
                    if current_layout:
                        # Check if floorplan is already in this layout
                        floorplan_index = None
                        for i in range(current_layout.count()):
                            item = current_layout.itemAt(i)
                            if item and item.widget() == self.shared_floorplan:
                                floorplan_index = i
                                break
                        
                        # If not in layout, add it (Qt automatically removes from old parent when reparenting)
                        if floorplan_index is None:
                            # Reparent to current widget (Qt will remove from old layout automatically)
                            self.shared_floorplan.setParent(current_widget)
                            # Insert at position 0 (before sidebar)
                            current_layout.insertWidget(0, self.shared_floorplan, stretch=1)
                        
                        # Ensure floorplan is visible
                        self.shared_floorplan.setVisible(True)
                        
                        # Disable zone placement for Adaptive Audio
                        if current_widget == self.tab_adaptive:
                            self.shared_floorplan.toggle_place_zones(False)

    # ---- AppBus Signal Connections (Routing Layer) ----
    def _connect_appbus_signals(self):
        """Connect all AppBus signals to their handlers (route AppBus → Server)."""
        # Playback control
        self.bus.playRequested.connect(self._on_play_requested)
        self.bus.pauseRequested.connect(self._on_pause_requested)
        self.bus.stopRequested.connect(self._on_stop_requested)
        self.bus.skipRequested.connect(self._on_skip_requested)
        self.bus.previousRequested.connect(self._on_previous_requested)
        self.bus.seekRequested.connect(self._on_seek_requested)

        # Audio mode control
        self.bus.audioStartRequested.connect(self._on_audio_start_requested)
        self.bus.audioStopRequested.connect(self._on_audio_stop_requested)
        self.bus.adaptiveAudioEnabled.connect(self._on_adaptive_audio_enabled)
        self.bus.zoneDjEnabled.connect(self._on_zone_dj_enabled)
        self.bus.bypassAudioRequested.connect(self._on_bypass_audio_requested)

        # Playlist & volume control
        self.bus.playlistChangeRequested.connect(self._on_playlist_change_requested)
        self.bus.volumeChangeRequested.connect(self._on_volume_change_requested)
        self.bus.globalVolumeChanged.connect(self._on_global_volume_changed)
        self.bus.shuffleToggled.connect(self._on_shuffle_toggled)
        self.bus.repeatToggled.connect(self._on_repeat_toggled)

        # Zone events (for logging/status)
        self.bus.zoneRegistered.connect(self._on_zone_registered)
        self.bus.zoneDeregistered.connect(self._on_zone_deregistered)

    # ---- Toolbar ----
    def _build_toolbar(self):
        tb = QToolBar("Floorplan", self)
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.TopToolBarArea, tb)

        # Use emoji icons matching the reference design
        act_open = QAction("📁", self)
        act_open.setToolTip("Open Floorplan")
        act_mark = QAction("📐", self)
        act_mark.setToolTip("Mark Corners")
        act_auto = QAction("🔍", self)
        act_auto.setToolTip("Auto Detect Corners")
        act_place = QAction("🎯", self)
        act_place.setToolTip("Place Zones")
        act_place.setCheckable(True)
        self.act_place_zones = act_place  # Store reference for enabling/disabling
        
        act_load_default = QAction("📋", self)
        act_load_default.setToolTip("Load Default Floorplan")
        act_settings = QAction("⚙", self)
        act_settings.setToolTip("Settings")

        act_open.triggered.connect(self._open_image)
        act_mark.triggered.connect(lambda: self._call_plan("start_marking_corners"))
        act_auto.triggered.connect(lambda: self._call_plan("auto_transform"))
        act_place.triggered.connect(lambda chk: self._call_plan("toggle_place_zones", chk))
        act_load_default.triggered.connect(self._load_default_floorplan)
        act_settings.triggered.connect(self._open_settings)

        tb.addAction(act_open)
        tb.addAction(act_mark)
        tb.addAction(act_auto)
        tb.addAction(act_place)
        tb.addSeparator()
        tb.addAction(act_load_default)
        tb.addSeparator()
        tb.addAction(act_settings)

    def _current_plan(self):
        w = self.tabs.currentWidget()
        # Our two audio tabs expose .plan (FloorplanView). PGO tab does not.
        return getattr(w, "plan", None)

    def _call_plan(self, method, *args):
        plan = self._current_plan()
        if plan is None:
            QMessageBox.information(self, "No floorplan", "Switch to Adaptive Audio or Zone DJ to use this action.")
            return
        fn = getattr(plan, method, None)
        if not fn:
            QMessageBox.warning(self, "Not available", f"Current plan does not support '{method}'.")
            return
        try:
            fn(*args)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{method} failed:\n{e}")
    
    def _apply_light_theme(self):
        """Apply light theme stylesheet"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
                color: #000000;
            }
            
            /* Menu Bar */
            QMenuBar {
                background-color: #f5f5f5;
                color: #000000;
                border-bottom: 1px solid #d0d0d0;
                padding: 4px 8px;
                font-size: 11pt;
            }
            
            QMenuBar::item {
                padding: 4px 12px;
                border-radius: 4px;
                min-width: 60px;
                background: transparent;
            }
            
            QMenuBar::item:selected {
                background-color: #e0e0e0;
            }
            
            QMenu {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                padding: 4px;
            }
            
            QMenu::item {
                padding: 6px 20px;
            }
            
            QMenu::item:selected {
                background-color: #4a9eff;
                color: #ffffff;
            }
            
            /* Toolbar */
            QToolBar {
                background-color: #f5f5f5;
                border: none;
                border-bottom: 1px solid #d0d0d0;
                spacing: 8px;
                padding: 8px;
            }
            
            QToolBar::separator {
                background-color: #d0d0d0;
                width: 1px;
                margin: 0 8px;
            }
            
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px;
                width: 32px;
                height: 32px;
                font-size: 16px;
            }
            
            QToolButton:hover {
                background-color: #e0e0e0;
            }
            
            QToolButton:pressed {
                background-color: #d0d0d0;
            }
            
            /* Tab Widget */
            QTabWidget::pane {
                border: none;
                background-color: #ffffff;
                top: -1px;
            }
            
            QTabBar {
                background-color: #f5f5f5;
                border-bottom: 1px solid #d0d0d0;
            }
            
            QTabBar::tab {
                background-color: transparent;
                color: #666666;
                border: none;
                padding: 10px 24px;
                margin-right: 0px;
                border-radius: 0px;
                font-size: 11pt;
                min-width: 140px;
            }
            
            QTabBar::tab:selected {
                background-color: #e0e0e0;
                color: #000000;
                font-weight: 500;
            }
            
            QTabBar::tab:hover {
                background-color: #e0e0e0;
                color: #000000;
            }
            
            /* Status Bar */
            QStatusBar {
                background-color: #f5f5f5;
                border-top: 1px solid #d0d0d0;
                color: #666666;
                font-size: 9pt;
                padding: 4px 8px;
            }
            
            QStatusBar::item {
                border: none;
            }
        """)

    # ---- File ops ----
    def _default_floorplan_dir(self):
        # same directory as this file, /assets/floorplans
        here = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(here, "assets", "floorplans")
    
    def _center_default_floorplan(self):
        """Center the default floorplan in the new coordinate system."""
        if not hasattr(self, 'shared_floorplan') or not self.shared_floorplan:
            return
        
        try:
            # Get image dimensions
            if not self.shared_floorplan.image_path:
                return
            
            import cv2
            img = cv2.imread(self.shared_floorplan.image_path)
            if img is None:
                return
            
            h, w = img.shape[:2]
            
            # Calculate centered corners for the new 600x480 coordinate system
            # Center the image within the world bounds
            margin_x = 0.1 * w  # 10% margin
            margin_y = 0.1 * h  # 10% margin
            
            centered_corners = [
                (margin_x, margin_y),              # Top-left
                (w - margin_x, margin_y),          # Top-right  
                (w - margin_x, h - margin_y),      # Bottom-right
                (margin_x, h - margin_y)           # Bottom-left
            ]
            
            # Set corners and compute homography
            self.shared_floorplan.corners = centered_corners
            if self.shared_floorplan._compute_homography():
                print(f"[MainWindow] Centered floorplan with corners: {centered_corners}")
            else:
                print("[MainWindow] Failed to compute homography for centered floorplan")
                
        except Exception as e:
            print(f"[MainWindow] Error centering floorplan: {e}")
            import traceback
            traceback.print_exc()

    def _default_load_floorplan(self):
        """Load default floorplan into shared instance (called on startup)."""
        # First try to load the specific floorplan.JPG
        here = os.path.abspath(os.path.dirname(__file__))
        repo_root = os.path.abspath(os.path.join(here, "..", ".."))
        specific_floorplan = os.path.join(repo_root, "packages", "viz_floorplan", "assets", "floorplan.JPG")
        
        if os.path.exists(specific_floorplan):
            # Load the specific floorplan.JPG
            if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
                try:
                    ok = self.shared_floorplan.load_image(specific_floorplan)
                    if ok:
                        # Auto-center the floorplan for the new coordinate system
                        self._center_default_floorplan()
                        self.statusBar().showMessage(f"Loaded default floorplan: {os.path.basename(specific_floorplan)} (centered)")
                        return
                except Exception as e:
                    self.statusBar().showMessage(f"Failed to load specific floorplan: {e}")
        
        # Fallback to original behavior
        candidates = []
        fdir = self._default_floorplan_dir()
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
            candidates.extend(glob.glob(os.path.join(fdir, ext)))
        if not candidates:
            self.statusBar().showMessage(f"No floorplan image found in {fdir}.")
            return
        img = sorted(candidates)[0]
        # Load into shared floorplan instance
        if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
            try:
                ok = self.shared_floorplan.load_image(img)
                if ok:
                    # Auto-center the fallback floorplan as well
                    self._center_default_floorplan()
                    self.statusBar().showMessage(f"Loaded floorplan: {os.path.basename(img)} (centered)")
            except Exception as e:
                self.statusBar().showMessage(f"Failed to load default image: {e}")
    
    def _load_default_floorplan(self):
        """Load default floorplan (called from toolbar button)."""
        # Check if custom default path is set
        default_path = self.settings.value("floorplan/default_path", "", type=str)
        if default_path and os.path.exists(default_path):
            # Use custom default path
            if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
                try:
                    ok = self.shared_floorplan.load_image(default_path)
                    if ok:
                        self.statusBar().showMessage(f"Loaded default floorplan: {os.path.basename(default_path)}")
                    else:
                        QMessageBox.warning(self, "Load Failed", f"Failed to load default floorplan from:\n{default_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to load default floorplan:\n{e}")
            return
        
        # Fallback to default directory
        self._default_load_floorplan()

    def _open_image(self):
        """Open floorplan image - loads into shared floorplan instance."""
        start_dir = self._default_floorplan_dir()
        fn, _ = QFileDialog.getOpenFileName(self, "Open floorplan image", start_dir, "Images (*.png *.jpg *.jpeg *.bmp)")
        if not fn:
            return
        # Load into shared floorplan instance
        if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
            try:
                ok = self.shared_floorplan.load_image(fn)
                if ok:
                    self.statusBar().showMessage(f"Loaded: {os.path.basename(fn)}")
                else:
                    QMessageBox.warning(self, "Load Failed", f"Failed to load image: {fn}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load image:\n{e}")
        else:
            # Fallback: try current plan
            plan = self._current_plan()
            if plan is None:
                QMessageBox.information(self, "No floorplan", "Switch to Adaptive Audio or Zone DJ to use this action.")
            return
        try:
            if plan.load_image(fn):
                self.statusBar().showMessage(f"Loaded: {os.path.basename(fn)}")
        except Exception as e:
            QMessageBox.critical(self, "Open failed", str(e))

    # ================================================================
    # POLLING METHODS (Server state → AppBus)
    # ================================================================

    def _poll_server_position(self):
        """Poll server position and emit to AppBus (data down)."""
        if self.server is None:
            return

        # Thread-safe attribute access
        try:
            if hasattr(self.server, '_position_lock'):
                with self.server._position_lock:
                    position = self.server.user_position
            else:
                position = getattr(self.server, 'user_position', None)
        except Exception as e:
            print(f"[MainWindow] Error reading position: {e}")
            return

        if position is not None:
            # Convert from cm to meters
            try:
                x_m = float(position[0]) / 100.0
                y_m = float(position[1]) / 100.0
            except (IndexError, TypeError, ValueError):
                return

            # Check if changed (avoid redundant updates)
            current_pos = np.array([x_m, y_m])
            if self._last_position is None or not np.allclose(current_pos, self._last_position, atol=0.001):
                ts = time.time()
                self.bus.pointerUpdated.emit(x_m, y_m, ts, "server")
                self._last_position = current_pos.copy()

                # Update floorplan pointer and status bar
                if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
                    self.shared_floorplan.map_pointer(x_m, y_m)
                    # Get pixel coordinates for status bar
                    pixel_coords = self.shared_floorplan.meter_to_pixel(x_m, y_m)
                    if pixel_coords:
                        self._update_status_bar_coords(
                            x_px=pixel_coords[0], 
                            y_px=pixel_coords[1],
                            x_m=x_m, 
                            y_m=y_m
                        )
                    else:
                        # Fallback if homography not available
                        self._update_status_bar_coords(x_m=x_m, y_m=y_m)
                else:
                    # Fallback if no floorplan
                    self._update_status_bar_coords(x_m=x_m, y_m=y_m)
    
    def _poll_speaker_volumes(self):
        """Poll speaker volumes and emit to AppBus (5Hz)."""
        if self.server is None:
            return
        
        try:
            # Get speaker volumes (thread-safe)
            volumes = self.server.get_speaker_volumes()
            if volumes:
                self.bus.speakerVolumesUpdated.emit(volumes)
            
            # Also set speaker positions in floorplan (only once, or when homography changes)
            if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
                if self.shared_floorplan.homography_matrix is not None:
                    # Get speaker positions from server
                    positions = self.server.get_speaker_positions()
                    if positions:
                        self.shared_floorplan.set_speaker_positions(positions)
        except Exception as e:
            print(f"[MainWindow] Error reading speaker volumes: {e}")

    def _poll_playback_state(self):
        """Poll queue and playback state, emit to AppBus (1Hz)."""
        if self.server is None:
            return

        try:
            # Queue preview
            if hasattr(self.server, 'get_queue_preview'):
                queue_preview = self.server.get_queue_preview(5)
                current_track = self.server.get_current_track() if hasattr(self.server, 'get_current_track') else ""
                self.bus.queueUpdated.emit(queue_preview, current_track)

            # Playback progress (only if playing)
            if hasattr(self.server, 'is_playing') and self.server.is_playing():
                if hasattr(self.server, 'get_playback_progress'):
                    progress = self.server.get_playback_progress()
                    self.bus.playbackProgressChanged.emit(progress)

            # Track changes
            if hasattr(self.server, 'get_current_track'):
                current_track = self.server.get_current_track()
                track_index = getattr(self.server, 'current_track_index', 0)
                self.bus.trackChanged.emit(current_track, track_index)

            # Volume states (emit only if changed)
            if hasattr(self.server, 'get_speaker_states'):
                speaker_states = self.server.get_speaker_states()
                for device_id, state in speaker_states.items():
                    volume = state.get('volume', 0) if isinstance(state, dict) else state
                    if device_id not in self._last_volumes or volume != self._last_volumes[device_id]:
                        self.bus.volumeUpdated.emit(device_id, volume)
                        self._last_volumes[device_id] = volume
        except Exception as e:
            print(f"[MainWindow] Error polling playback state: {e}")

    # ================================================================
    # APPBUS SIGNAL HANDLERS (Route to server methods)
    # ================================================================

    # --- Playback Control Handlers ---
    @pyqtSlot(str)
    def _on_play_requested(self, source: str):
        """Handle play request from widgets."""
        if self.server and hasattr(self.server, 'play'):
            self.server.play()
            self.bus.playbackStateChanged.emit(source, True)
            self.bus.serverStatusChanged.emit("playing")

    @pyqtSlot(str)
    def _on_pause_requested(self, source: str):
        """Handle pause request from widgets."""
        if self.server and hasattr(self.server, 'pause'):
            self.server.pause()
            self.bus.playbackStateChanged.emit(source, False)
            self.bus.serverStatusChanged.emit("paused")

    @pyqtSlot(str)
    def _on_stop_requested(self, source: str):
        """Handle stop request from widgets."""
        if self.server and hasattr(self.server, 'stop_playback'):
            self.server.stop_playback()
        elif self.server and hasattr(self.server, 'stop'):
            self.server.stop()
        self.bus.playbackStateChanged.emit(source, False)
        self.bus.serverStatusChanged.emit("stopped")

    @pyqtSlot(str)
    def _on_skip_requested(self, source: str):
        """Handle skip to next track request."""
        if self.server and hasattr(self.server, 'skip_track'):
            self.server.skip_track()
            # Emit track change
            if hasattr(self.server, 'get_current_track'):
                current_track = self.server.get_current_track()
                track_index = getattr(self.server, 'current_track_index', 0)
                self.bus.trackChanged.emit(current_track, track_index)

    @pyqtSlot(str)
    def _on_previous_requested(self, source: str):
        """Handle previous track request."""
        if self.server and hasattr(self.server, 'previous_track'):
            self.server.previous_track()
            if hasattr(self.server, 'get_current_track'):
                current_track = self.server.get_current_track()
                track_index = getattr(self.server, 'current_track_index', 0)
                self.bus.trackChanged.emit(current_track, track_index)

    @pyqtSlot(str, float)
    def _on_seek_requested(self, source: str, position: float):
        """Handle seek request."""
        if self.server and hasattr(self.server, 'seek'):
            self.server.seek(position)

    # --- Audio Mode Handlers ---
    @pyqtSlot(str, dict)
    def _on_audio_start_requested(self, mode: str, params: dict):
        """Handle audio mode start request (adaptive/zone_dj)."""
        if self.server is None:
            return
        if mode == "adaptive":
            if hasattr(self.server, 'adaptive_audio_demo'):
                # For adaptive audio, pass zone_id and position if available
                if params and "zone_id" in params:
                    # Log the zone registration event with position
                    zone_id = params.get("zone_id")
                    position = params.get("position", (0.0, 0.0))
                    print(f"[MainWindow] Adaptive Audio: Zone {zone_id} registered at position {position}")
                    # Call adaptive_audio_demo (it doesn't take parameters, but we log the event)
                    self.server.adaptive_audio_demo()
                else:
                    self.server.adaptive_audio_demo()
        elif mode == "zone_dj":
            if hasattr(self.server, 'zone_dj_demo'):
                # Zone DJ doesn't accept parameters yet (TODO in serverbringup)
                # For now, just log the event and call without parameters
                if params and "zone_id" in params:
                    zone_id = params.get("zone_id")
                    position = params.get("position", (0.0, 0.0))
                    print(f"[MainWindow] Zone DJ: Zone {zone_id} registered at position {position}")
                    print(f"[MainWindow] Warning: zone_dj_demo() doesn't accept parameters yet (serverbringup TODO)")
                # Call without parameters until serverbringup is updated
                self.server.zone_dj_demo()
        self.bus.serverStatusChanged.emit("audio_playing")

    @pyqtSlot(str)
    def _on_audio_stop_requested(self, mode: str):
        """Handle audio mode stop request."""
        if self.server is None:
            return
        if mode == "adaptive":
            if hasattr(self.server, 'stop_adaptive_audio_demo'):
                self.server.stop_adaptive_audio_demo()
        elif mode == "zone_dj":
            if hasattr(self.server, 'stop_zone_dj_demo'):
                self.server.stop_zone_dj_demo()
        self.bus.serverStatusChanged.emit("stopped")

    @pyqtSlot(bool)
    def _on_adaptive_audio_enabled(self, enabled: bool):
        """Enable/disable adaptive audio mode."""
        if self.server and hasattr(self.server, 'enable_adaptive_audio'):
            self.server.enable_adaptive_audio(enabled)

    @pyqtSlot(bool)
    def _on_zone_dj_enabled(self, enabled: bool):
        """Enable/disable zone DJ mode."""
        if self.server and hasattr(self.server, 'enable_zone_dj'):
            self.server.enable_zone_dj(enabled)

    @pyqtSlot(bool)
    def _on_bypass_audio_requested(self, bypass: bool):
        """Bypass all audio processing."""
        if self.server and hasattr(self.server, 'bypass_audio_processing'):
            self.server.bypass_audio_processing(bypass)

    # --- Playlist & Volume Handlers ---
    @pyqtSlot(int)
    def _on_playlist_change_requested(self, playlist_number: int):
        """Handle playlist change request."""
        if self.server and hasattr(self.server, 'set_playlist'):
            self.server.set_playlist(playlist_number)
            # Emit queue update
            self._poll_playback_state()

    @pyqtSlot(int, int)
    def _on_volume_change_requested(self, device_id: int, volume: int):
        """Handle volume change for specific device or all devices."""
        if self.server is None:
            return
        if device_id == -1:
            # Set volume for all devices
            if hasattr(self.server, 'set_global_volume'):
                self.server.set_global_volume(volume)
                self.bus.globalVolumeUpdated.emit(volume)
        else:
            if hasattr(self.server, 'set_volume'):
                self.server.set_volume(device_id, volume)
                self.bus.volumeUpdated.emit(device_id, volume)

    @pyqtSlot(int)
    def _on_global_volume_changed(self, volume: int):
        """Handle global volume change."""
        if self.server and hasattr(self.server, 'set_global_volume'):
            self.server.set_global_volume(volume)
            self.bus.globalVolumeUpdated.emit(volume)

    @pyqtSlot(bool)
    def _on_shuffle_toggled(self, enabled: bool):
        """Handle shuffle toggle."""
        # Server method may not exist yet, but signal is routed
        pass

    @pyqtSlot(bool)
    def _on_repeat_toggled(self, enabled: bool):
        """Handle repeat toggle."""
        # Server method may not exist yet, but signal is routed
        pass

    # --- Settings Dialog ---
    def _open_settings(self):
        """Open settings dialog."""
        dialog = _SettingsDialog(self.settings, self)
        if dialog.exec_() == QDialog.Accepted:
            # Update zone radius in shared floorplan if it exists
            new_radius = dialog.radius_spinbox.value()
            self.settings.setValue("zonedj/default_zone_radius_m", new_radius)
            if hasattr(self, 'shared_floorplan') and self.shared_floorplan:
                self.shared_floorplan.default_zone_radius_m = new_radius
                # Update Zone DJ widget if it's using the shared floorplan
                if hasattr(self.tab_zonedj, 'floorplan') and self.tab_zonedj.floorplan == self.shared_floorplan:
                    self.tab_zonedj.default_zone_radius_m = new_radius
            
            # Save default floorplan path
            default_path = dialog.path_edit.text()
            self.settings.setValue("floorplan/default_path", default_path)
            self.settings.sync()
            
            QMessageBox.information(self, "Settings", "Settings saved successfully.")

    # --- Zone Event Handlers (for logging/status) ---
    @pyqtSlot(object, float, float, float, str)
    def _on_zone_registered(self, zone_id, x_m, y_m, ts, source):
        """Handle zone registration event (for logging/status)."""
        # Log to console or update status bar
        print(f"[Zone] Registered: {zone_id} at ({x_m:.2f}, {y_m:.2f})")

    @pyqtSlot(object, float, float, float, str)
    def _on_zone_deregistered(self, zone_id, x_m, y_m, ts, source):
        """Handle zone deregistration event (for logging/status)."""
        # Log to console or update status bar
        print(f"[Zone] Deregistered: {zone_id}")

    @pyqtSlot(str)
    def _on_server_status_changed(self, status: str):
        """Handle server status change."""
        status_text = f"Server: {status}"
        current_msg = self.statusBar().currentMessage()
        # Preserve coordinate info if present
        if "Pixel:" in current_msg or "Meter:" in current_msg:
            # Extract coordinate parts (everything except server status)
            parts = [p.strip() for p in current_msg.split("|")]
            coord_parts = [p for p in parts if not p.startswith("Server:")]
            coord_parts.append(status_text)
            self.statusBar().showMessage(" | ".join(coord_parts))
        else:
            self.statusBar().showMessage(status_text)

    def closeEvent(self, event):
        """Cleanup on window close."""
        # Stop polling timers
        try:
            if hasattr(self, '_position_timer'):
                self._position_timer.stop()
            if hasattr(self, '_queue_timer'):
                self._queue_timer.stop()
        except Exception:
            pass

        # Stop server
        try:
            if self.server and hasattr(self.server, "stop"):
                self.server.stop()
        except Exception as e:
            print(f"[MainWindow] Error stopping server: {e}")

        super().closeEvent(event)

def main():
    # Pass through Qt flags (e.g. --style); no custom CLI beyond that.
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
