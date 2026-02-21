import logging

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from moodle_dl.config import ConfigHelper


class SettingsPage(QWidget):

    def __init__(self, config: ConfigHelper, opts) -> None:
        super().__init__()
        self.config = config
        self.opts = opts

        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Paths
        paths_group = QGroupBox('Paths')
        paths_layout = QFormLayout()

        path_row = QHBoxLayout()
        self.download_path_input = QLineEdit()
        self.download_path_input.setReadOnly(True)
        path_row.addWidget(self.download_path_input)
        self.browse_dl_btn = QPushButton('Browse...')
        self.browse_dl_btn.clicked.connect(self._browse_download_path)
        path_row.addWidget(self.browse_dl_btn)
        paths_layout.addRow('Download Path:', path_row)

        misc_row = QHBoxLayout()
        self.misc_path_input = QLineEdit()
        self.misc_path_input.setReadOnly(True)
        misc_row.addWidget(self.misc_path_input)
        self.browse_misc_btn = QPushButton('Browse...')
        self.browse_misc_btn.clicked.connect(self._browse_misc_path)
        misc_row.addWidget(self.browse_misc_btn)
        paths_layout.addRow('Config/DB Path:', misc_row)

        paths_group.setLayout(paths_layout)
        layout.addWidget(paths_group)

        # Parallelism
        perf_group = QGroupBox('Performance')
        perf_layout = QFormLayout()

        self.spin_api_calls = QSpinBox()
        self.spin_api_calls.setRange(1, 50)
        self.spin_api_calls.setValue(self.opts.max_parallel_api_calls)
        self.spin_api_calls.setToolTip('Maximum number of concurrent API requests to the Moodle server.')
        perf_layout.addRow('Max Parallel API Calls:', self.spin_api_calls)

        self.spin_downloads = QSpinBox()
        self.spin_downloads.setRange(1, 50)
        self.spin_downloads.setValue(self.opts.max_parallel_downloads)
        self.spin_downloads.setToolTip('Maximum number of files to download simultaneously.')
        perf_layout.addRow('Max Parallel Downloads:', self.spin_downloads)

        self.spin_ytdlp = QSpinBox()
        self.spin_ytdlp.setRange(1, 32)
        self.spin_ytdlp.setValue(self.opts.max_parallel_yt_dlp)
        self.spin_ytdlp.setToolTip('Maximum number of concurrent yt-dlp video downloads.')
        perf_layout.addRow('Max Parallel yt-dlp:', self.spin_ytdlp)

        self.spin_chunk = QSpinBox()
        self.spin_chunk.setRange(1024, 10485760)
        self.spin_chunk.setSingleStep(102400)
        self.spin_chunk.setValue(self.opts.download_chunk_size)
        self.spin_chunk.setSuffix(' bytes')
        self.spin_chunk.setToolTip('Size of each download chunk in bytes. Larger values may improve speed.')
        perf_layout.addRow('Download Chunk Size:', self.spin_chunk)

        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        # Download Filters
        filters_group = QGroupBox('Download Filters')
        filters_layout = QFormLayout()

        self.exclude_extensions_input = QLineEdit()
        self.exclude_extensions_input.setPlaceholderText('.exe, .msi, .iso')
        self.exclude_extensions_input.setToolTip('Comma-separated list of file extensions to exclude from downloads.')
        filters_layout.addRow('Exclude Extensions:', self.exclude_extensions_input)

        self.spin_max_file_size = QSpinBox()
        self.spin_max_file_size.setRange(0, 102400)
        self.spin_max_file_size.setValue(0)
        self.spin_max_file_size.setSuffix(' MB')
        self.spin_max_file_size.setToolTip('Maximum file size to download in MB. Set to 0 for unlimited.')
        filters_layout.addRow('Max File Size:', self.spin_max_file_size)

        filters_group.setLayout(filters_layout)
        layout.addWidget(filters_group)

        # SSL / Misc Options
        ssl_group = QGroupBox('SSL / Misc')
        ssl_layout = QVBoxLayout()

        self.cb_allow_insecure = QCheckBox('Allow Insecure SSL')
        self.cb_allow_insecure.setToolTip('Allow connections to unpatched servers with old SSL.')
        ssl_layout.addWidget(self.cb_allow_insecure)

        self.cb_all_ciphers = QCheckBox('Use All Ciphers')
        self.cb_all_ciphers.setToolTip('Allow insecure ciphers for the connection.')
        ssl_layout.addWidget(self.cb_all_ciphers)

        self.cb_skip_cert = QCheckBox('Skip Certificate Verification')
        self.cb_skip_cert.setToolTip('Do not verify TLS certificates. Use only in non-production environments.')
        ssl_layout.addWidget(self.cb_skip_cert)

        self.cb_restricted_filenames = QCheckBox('Restrict Filenames (ASCII only)')
        self.cb_restricted_filenames.setToolTip('Replace non-ASCII characters in filenames with ASCII equivalents.')
        ssl_layout.addWidget(self.cb_restricted_filenames)

        self.cb_verbose = QCheckBox('Verbose Logging')
        self.cb_verbose.setToolTip('Enable debug-level logging for more detailed output.')
        ssl_layout.addWidget(self.cb_verbose)

        ssl_group.setLayout(ssl_layout)
        layout.addWidget(ssl_group)

        # Save button
        save_row = QHBoxLayout()
        save_row.addStretch()
        self.save_btn = QPushButton('Save Settings')
        self.save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self.save_btn)
        layout.addLayout(save_row)

        layout.addStretch()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        save_shortcut = QShortcut(QKeySequence('Ctrl+S'), self)
        save_shortcut.activated.connect(self._on_save)

    def on_show(self) -> None:
        """Called when this page becomes visible. Load current settings."""
        self.download_path_input.setText(self.config.get_download_path())
        self.misc_path_input.setText(self.config.get_misc_files_path())

        self.spin_api_calls.setValue(self.opts.max_parallel_api_calls)
        self.spin_downloads.setValue(self.opts.max_parallel_downloads)
        self.spin_ytdlp.setValue(self.opts.max_parallel_yt_dlp)
        self.spin_chunk.setValue(self.opts.download_chunk_size)

        self.cb_allow_insecure.setChecked(self.opts.allow_insecure_ssl)
        self.cb_all_ciphers.setChecked(self.opts.use_all_ciphers)
        self.cb_skip_cert.setChecked(self.opts.skip_cert_verify)

        self.cb_restricted_filenames.setChecked(self.config.get_restricted_filenames())
        self.cb_verbose.setChecked(self.opts.verbose)

        # Load download filters
        exclude_ext = self.config.get_property_or('exclude_file_extensions', '')
        if isinstance(exclude_ext, list):
            exclude_ext = ', '.join(exclude_ext)
        self.exclude_extensions_input.setText(exclude_ext)

        max_size = self.config.get_property_or('max_file_size_mb', 0)
        self.spin_max_file_size.setValue(max_size if isinstance(max_size, int) else 0)

    def _browse_download_path(self) -> None:
        """Open a directory chooser for the download path."""
        path = QFileDialog.getExistingDirectory(self, 'Select Download Directory')
        if path:
            self.download_path_input.setText(path)

    def _browse_misc_path(self) -> None:
        """Open a directory chooser for the config/DB path."""
        path = QFileDialog.getExistingDirectory(self, 'Select Config/Database Directory')
        if path:
            self.misc_path_input.setText(path)

    def _on_save(self) -> None:
        """Save all settings."""
        # Save paths
        dl_path = self.download_path_input.text().strip()
        if dl_path:
            self.config.set_property('download_path', dl_path)

        misc_path = self.misc_path_input.text().strip()
        if misc_path:
            self.config.set_property('misc_files_path', misc_path)

        # Update opts for current session
        self.opts.max_parallel_api_calls = self.spin_api_calls.value()
        self.opts.max_parallel_downloads = self.spin_downloads.value()
        self.opts.max_parallel_yt_dlp = self.spin_ytdlp.value()
        self.opts.download_chunk_size = self.spin_chunk.value()

        self.opts.allow_insecure_ssl = self.cb_allow_insecure.isChecked()
        self.opts.use_all_ciphers = self.cb_all_ciphers.isChecked()
        self.opts.skip_cert_verify = self.cb_skip_cert.isChecked()

        self.config.set_property('restricted_filenames', self.cb_restricted_filenames.isChecked())

        # Verbose logging toggle
        self.opts.verbose = self.cb_verbose.isChecked()
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if self.opts.verbose else logging.INFO)

        # Save download filters
        ext_text = self.exclude_extensions_input.text().strip()
        if ext_text:
            extensions = [e.strip() for e in ext_text.split(',') if e.strip()]
            self.config.set_property('exclude_file_extensions', extensions)
        else:
            self.config.set_property('exclude_file_extensions', [])

        max_size = self.spin_max_file_size.value()
        self.config.set_property('max_file_size_mb', max_size)

        QMessageBox.information(self, 'Saved', 'Settings saved successfully.')
