import logging

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from moodle_dl.config import ConfigHelper


class SettingsPage(QWidget):

    config_saved = Signal()

    def __init__(self, config: ConfigHelper, opts) -> None:
        super().__init__()
        self.config = config
        self.opts = opts
        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # ── Что скачивать ──────────────────────────────────────────────
        dl_group = QGroupBox('Что скачивать')
        dl_grid = QGridLayout()
        dl_grid.setHorizontalSpacing(20)
        dl_grid.setVerticalSpacing(4)

        self.opt_submissions   = QCheckBox('Работы студентов')
        self.opt_descriptions  = QCheckBox('Описания активностей')
        self.opt_links_in_desc = QCheckBox('Файлы из описаний')
        self.opt_databases     = QCheckBox('Базы данных')
        self.opt_forums        = QCheckBox('Форумы')
        self.opt_quizzes       = QCheckBox('Тесты')
        self.opt_lessons       = QCheckBox('Уроки')
        self.opt_workshops     = QCheckBox('Семинары')
        self.opt_books         = QCheckBox('Книги (mod_book)')
        self.opt_calendars     = QCheckBox('Календарь событий')
        self.opt_linked_files  = QCheckBox('Внешние файлы по ссылкам')
        self.opt_cookie_files  = QCheckBox('Файлы, требующие Cookie')
        self.opt_mhtml_capture = QCheckBox('MHTML-захват страниц (Playwright)')

        self.opt_mhtml_capture.setToolTip(
            'Сохранять страницы книг, заданий и форумов как полные .mhtml файлы\n'
            'через headless браузер. Требует: playwright + установленных cookies.'
        )

        checkboxes = [
            self.opt_submissions, self.opt_descriptions, self.opt_links_in_desc,
            self.opt_databases,   self.opt_forums,       self.opt_quizzes,
            self.opt_lessons,     self.opt_workshops,    self.opt_books,
            self.opt_calendars,   self.opt_linked_files, self.opt_cookie_files,
            self.opt_mhtml_capture,
        ]
        for i, cb in enumerate(checkboxes):
            dl_grid.addWidget(cb, i // 2, i % 2)

        dl_group.setLayout(dl_grid)
        layout.addWidget(dl_group)

        # ── Пути ──────────────────────────────────────────────────────
        paths_group = QGroupBox('Пути')
        paths_layout = QFormLayout()

        path_row = QHBoxLayout()
        self.download_path_input = QLineEdit()
        self.download_path_input.setReadOnly(True)
        path_row.addWidget(self.download_path_input)
        self.browse_dl_btn = QPushButton('Обзор…')
        self.browse_dl_btn.clicked.connect(self._browse_download_path)
        path_row.addWidget(self.browse_dl_btn)
        paths_layout.addRow('Папка загрузки:', path_row)

        misc_row = QHBoxLayout()
        self.misc_path_input = QLineEdit()
        self.misc_path_input.setReadOnly(True)
        misc_row.addWidget(self.misc_path_input)
        self.browse_misc_btn = QPushButton('Обзор…')
        self.browse_misc_btn.clicked.connect(self._browse_misc_path)
        misc_row.addWidget(self.browse_misc_btn)
        paths_layout.addRow('Папка конфига:', misc_row)

        paths_group.setLayout(paths_layout)
        layout.addWidget(paths_group)

        # ── Производительность ────────────────────────────────────────
        perf_group = QGroupBox('Производительность')
        perf_layout = QFormLayout()

        self.spin_api_calls = QSpinBox()
        self.spin_api_calls.setRange(1, 50)
        self.spin_api_calls.setValue(self.opts.max_parallel_api_calls)
        perf_layout.addRow('Параллельных API-запросов:', self.spin_api_calls)

        self.spin_downloads = QSpinBox()
        self.spin_downloads.setRange(1, 50)
        self.spin_downloads.setValue(self.opts.max_parallel_downloads)
        perf_layout.addRow('Параллельных загрузок:', self.spin_downloads)

        self.spin_ytdlp = QSpinBox()
        self.spin_ytdlp.setRange(1, 32)
        self.spin_ytdlp.setValue(self.opts.max_parallel_yt_dlp)
        perf_layout.addRow('Параллельных yt-dlp:', self.spin_ytdlp)

        self.spin_chunk = QSpinBox()
        self.spin_chunk.setRange(1024, 10485760)
        self.spin_chunk.setSingleStep(102400)
        self.spin_chunk.setValue(self.opts.download_chunk_size)
        self.spin_chunk.setSuffix(' байт')
        perf_layout.addRow('Размер чанка:', self.spin_chunk)

        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        # ── Фильтры файлов ────────────────────────────────────────────
        filters_group = QGroupBox('Фильтры файлов')
        filters_layout = QFormLayout()

        self.exclude_extensions_input = QLineEdit()
        self.exclude_extensions_input.setPlaceholderText('.exe, .msi, .iso')
        filters_layout.addRow('Исключить расширения:', self.exclude_extensions_input)

        self.spin_max_file_size = QSpinBox()
        self.spin_max_file_size.setRange(0, 102400)
        self.spin_max_file_size.setValue(0)
        self.spin_max_file_size.setSuffix(' МБ (0 = без ограничения)')
        filters_layout.addRow('Макс. размер файла:', self.spin_max_file_size)

        filters_group.setLayout(filters_layout)
        layout.addWidget(filters_group)

        # ── Домены ────────────────────────────────────────────────────
        domain_group = QGroupBox('Фильтрация доменов')
        domain_layout = QVBoxLayout()

        domain_layout.addWidget(QLabel('Белый список (по одному домену, пусто = всё разрешено):'))
        self.domain_whitelist_input = QTextEdit()
        self.domain_whitelist_input.setPlaceholderText('el.istu.edu')
        self.domain_whitelist_input.setMaximumHeight(70)
        domain_layout.addWidget(self.domain_whitelist_input)

        domain_layout.addWidget(QLabel('Чёрный список (домены, которые блокировать):'))
        self.domain_blacklist_input = QTextEdit()
        self.domain_blacklist_input.setMaximumHeight(70)
        domain_layout.addWidget(self.domain_blacklist_input)

        domain_group.setLayout(domain_layout)
        layout.addWidget(domain_group)

        # ── SSL / Прочее ──────────────────────────────────────────────
        ssl_group = QGroupBox('SSL и прочее')
        ssl_layout = QGridLayout()
        ssl_layout.setHorizontalSpacing(20)
        ssl_layout.setVerticalSpacing(4)

        self.cb_allow_insecure      = QCheckBox('Разрешить небезопасный SSL')
        self.cb_all_ciphers         = QCheckBox('Использовать все шифры')
        self.cb_skip_cert           = QCheckBox('Не проверять сертификат')
        self.cb_restricted_filenames= QCheckBox('Только ASCII-имена файлов')
        self.cb_verbose             = QCheckBox('Подробное логирование')

        ssl_cbs = [self.cb_allow_insecure, self.cb_all_ciphers,
                   self.cb_skip_cert, self.cb_restricted_filenames, self.cb_verbose]
        for i, cb in enumerate(ssl_cbs):
            ssl_layout.addWidget(cb, i // 2, i % 2)

        ssl_group.setLayout(ssl_layout)
        layout.addWidget(ssl_group)

        layout.addStretch()

        # ── Кнопка сохранения ─────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.addStretch()
        self.save_btn = QPushButton('💾  Сохранить настройки')
        self.save_btn.setFixedHeight(32)
        self.save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self.save_btn)
        outer.addLayout(save_row)
        outer.setContentsMargins(8, 4, 8, 8)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence('Ctrl+S'), self).activated.connect(self._on_save)

    def on_show(self) -> None:
        self.download_path_input.setText(self.config.get_download_path())
        self.misc_path_input.setText(self.config.get_misc_files_path())

        self.spin_api_calls.setValue(
            self.config.get_property_or('max_parallel_api_calls', self.opts.max_parallel_api_calls))
        self.spin_downloads.setValue(
            self.config.get_property_or('max_parallel_downloads', self.opts.max_parallel_downloads))
        self.spin_ytdlp.setValue(
            self.config.get_property_or('max_parallel_yt_dlp', self.opts.max_parallel_yt_dlp))
        self.spin_chunk.setValue(
            self.config.get_property_or('download_chunk_size', self.opts.download_chunk_size))

        self.cb_allow_insecure.setChecked(
            self.config.get_property_or('allow_insecure_ssl', self.opts.allow_insecure_ssl))
        self.cb_all_ciphers.setChecked(
            self.config.get_property_or('use_all_ciphers', self.opts.use_all_ciphers))
        self.cb_skip_cert.setChecked(
            self.config.get_property_or('skip_cert_verify', self.opts.skip_cert_verify))
        self.cb_restricted_filenames.setChecked(self.config.get_restricted_filenames())
        self.cb_verbose.setChecked(self.config.get_property_or('verbose', self.opts.verbose))

        ext = self.config.get_property_or('exclude_file_extensions', '')
        if isinstance(ext, list):
            ext = ', '.join(ext)
        self.exclude_extensions_input.setText(ext)

        max_mb = self.config.get_property_or('max_file_size', 0)
        self.spin_max_file_size.setValue(int(max_mb / (1024 * 1024)) if isinstance(max_mb, (int, float)) else 0)

        wl = self.config.get_download_domains_whitelist()
        self.domain_whitelist_input.setPlainText('\n'.join(wl) if wl else '')
        bl = self.config.get_download_domains_blacklist()
        self.domain_blacklist_input.setPlainText('\n'.join(bl) if bl else '')

        # Download Options (moved here from Courses page)
        try:
            self.opt_submissions.setChecked(self.config.get_download_submissions())
            self.opt_descriptions.setChecked(self.config.get_download_descriptions())
            self.opt_links_in_desc.setChecked(self.config.get_download_links_in_descriptions())
            self.opt_databases.setChecked(self.config.get_download_databases())
            self.opt_forums.setChecked(self.config.get_download_forums())
            self.opt_quizzes.setChecked(self.config.get_download_quizzes())
            self.opt_lessons.setChecked(self.config.get_download_lessons())
            self.opt_workshops.setChecked(self.config.get_download_workshops())
            self.opt_books.setChecked(self.config.get_download_books())
            self.opt_calendars.setChecked(self.config.get_download_calendars())
            self.opt_linked_files.setChecked(self.config.get_download_linked_files())
            self.opt_cookie_files.setChecked(self.config.get_download_also_with_cookie())
            self.opt_mhtml_capture.setChecked(self.config.get_enable_mhtml_capture())
        except (ValueError, ConfigHelper.NoConfigError):
            pass

    def _browse_download_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, 'Выберите папку загрузки')
        if path:
            self.download_path_input.setText(path)

    def _browse_misc_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, 'Выберите папку конфига')
        if path:
            self.misc_path_input.setText(path)

    def _on_save(self) -> None:
        # Paths
        dl_path = self.download_path_input.text().strip()
        if dl_path:
            self.config.set_property('download_path', dl_path)
        misc_path = self.misc_path_input.text().strip()
        if misc_path:
            self.config.set_property('misc_files_path', misc_path)

        # Download Options
        self.config.set_property('download_submissions',          self.opt_submissions.isChecked())
        self.config.set_property('download_descriptions',         self.opt_descriptions.isChecked())
        self.config.set_property('download_links_in_descriptions',self.opt_links_in_desc.isChecked())
        self.config.set_property('download_databases',            self.opt_databases.isChecked())
        self.config.set_property('download_forums',               self.opt_forums.isChecked())
        self.config.set_property('download_quizzes',              self.opt_quizzes.isChecked())
        self.config.set_property('download_lessons',              self.opt_lessons.isChecked())
        self.config.set_property('download_workshops',            self.opt_workshops.isChecked())
        self.config.set_property('download_books',                self.opt_books.isChecked())
        self.config.set_property('download_calendars',            self.opt_calendars.isChecked())
        self.config.set_property('download_linked_files',         self.opt_linked_files.isChecked())
        self.config.set_property('download_also_with_cookie',     self.opt_cookie_files.isChecked())
        self.config.set_property('enable_mhtml_capture',          self.opt_mhtml_capture.isChecked())

        # Performance
        self.opts.max_parallel_api_calls  = self.spin_api_calls.value()
        self.opts.max_parallel_downloads  = self.spin_downloads.value()
        self.opts.max_parallel_yt_dlp     = self.spin_ytdlp.value()
        self.opts.download_chunk_size     = self.spin_chunk.value()
        self.config.set_property('max_parallel_api_calls', self.opts.max_parallel_api_calls)
        self.config.set_property('max_parallel_downloads', self.opts.max_parallel_downloads)
        self.config.set_property('max_parallel_yt_dlp',    self.opts.max_parallel_yt_dlp)
        self.config.set_property('download_chunk_size',    self.opts.download_chunk_size)

        # SSL / Misc
        self.opts.allow_insecure_ssl = self.cb_allow_insecure.isChecked()
        self.opts.use_all_ciphers    = self.cb_all_ciphers.isChecked()
        self.opts.skip_cert_verify   = self.cb_skip_cert.isChecked()
        self.config.set_property('allow_insecure_ssl', self.opts.allow_insecure_ssl)
        self.config.set_property('use_all_ciphers',    self.opts.use_all_ciphers)
        self.config.set_property('skip_cert_verify',   self.opts.skip_cert_verify)
        self.config.set_property('restricted_filenames', self.cb_restricted_filenames.isChecked())

        self.opts.verbose = self.cb_verbose.isChecked()
        self.config.set_property('verbose', self.opts.verbose)
        logging.getLogger().setLevel(logging.DEBUG if self.opts.verbose else logging.INFO)

        # Filters
        ext_text = self.exclude_extensions_input.text().strip()
        self.config.set_property('exclude_file_extensions',
            [e.strip() for e in ext_text.split(',') if e.strip()] if ext_text else [])
        self.config.set_property('max_file_size', self.spin_max_file_size.value() * 1024 * 1024)

        # Domains
        wl = [d.strip() for d in self.domain_whitelist_input.toPlainText().splitlines() if d.strip()]
        bl = [d.strip() for d in self.domain_blacklist_input.toPlainText().splitlines() if d.strip()]
        self.config.set_property('download_domains_whitelist', wl)
        self.config.set_property('download_domains_blacklist', bl)

        QMessageBox.information(self, 'Сохранено', 'Настройки сохранены.')
        self.config_saved.emit()
