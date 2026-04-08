import logging

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QToolBar,
)

from moodle_dl.config import ConfigHelper
from moodle_dl.gui.pages.archive_viewer import EmbeddedViewer
from moodle_dl.gui.pages.config_page import ConfigPage
from moodle_dl.gui.pages.download_page import DownloadPage
from moodle_dl.gui.pages.login_page import LoginPage
from moodle_dl.gui.pages.notifications_page import NotificationsPage
from moodle_dl.gui.pages.settings_page import SettingsPage
from moodle_dl.version import __version__

# Глобальная тема приложения
APP_STYLE = """
QMainWindow, QWidget {
    background-color: #f5f5f5;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QToolBar {
    background: #1565c0;
    border: none;
    padding: 4px 6px;
    spacing: 2px;
}
QToolBar QToolButton {
    color: #ffffff;
    background: transparent;
    border: none;
    padding: 5px 12px;
    border-radius: 4px;
    font-size: 13px;
}
QToolBar QToolButton:hover {
    background: rgba(255,255,255,0.18);
}
QToolBar QToolButton:checked,
QToolBar QToolButton[active="true"] {
    background: rgba(255,255,255,0.28);
    font-weight: bold;
}
QToolBar::separator {
    background: rgba(255,255,255,0.3);
    width: 1px;
    margin: 4px 4px;
}
QPushButton {
    background-color: #1976d2;
    color: white;
    border: none;
    padding: 5px 16px;
    border-radius: 4px;
    font-size: 13px;
    min-height: 28px;
}
QPushButton:hover  { background-color: #1565c0; }
QPushButton:pressed{ background-color: #0d47a1; }
QPushButton:disabled{ background-color: #bdbdbd; color: #757575; }
QGroupBox {
    font-weight: bold;
    border: 1px solid #ddd;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    background: white;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #1565c0;
}
QLineEdit, QSpinBox, QTextEdit {
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 4px 6px;
    background: white;
}
QLineEdit:focus, QSpinBox:focus, QTextEdit:focus {
    border-color: #1976d2;
}
QScrollArea { border: none; background: transparent; }
QCheckBox { spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #aaa; border-radius: 3px;
    background: white;
}
QCheckBox::indicator:checked {
    background: #1976d2;
    border-color: #1976d2;
    image: url(none);
}
QProgressBar {
    border: 1px solid #ccc; border-radius: 4px;
    background: #e0e0e0; text-align: center;
    height: 18px;
}
QProgressBar::chunk { background: #1976d2; border-radius: 3px; }
QTableView {
    border: 1px solid #ddd; border-radius: 4px;
    background: white; gridline-color: #f0f0f0;
    alternate-background-color: #fafafa;
}
QHeaderView::section {
    background: #e8eaf6; border: none;
    border-right: 1px solid #ddd;
    padding: 4px 8px; font-weight: bold;
}
QStatusBar { background: #e8eaf6; color: #333; font-size: 12px; }
"""


class MainWindow(QMainWindow):
    PAGE_LOGIN         = 0
    PAGE_CONFIG        = 1
    PAGE_DOWNLOAD      = 2
    PAGE_SETTINGS      = 3
    PAGE_NOTIFICATIONS = 4
    PAGE_ARCHIVE       = 5

    def __init__(self, opts) -> None:
        super().__init__()
        self.opts = opts
        self.config = ConfigHelper(opts)
        self._logged_in = False

        self.setWindowTitle(f'Moodle Загрузчик  v{__version__}')
        self.setMinimumSize(900, 640)

        self._settings = QSettings('Moodle-DL', 'Moodle-DL')
        geometry = self._settings.value('window/geometry')
        if geometry is not None:
            self.restoreGeometry(geometry)

        self.setStyleSheet(APP_STYLE)
        self._setup_ui()
        self._setup_shortcuts()
        self._try_auto_login()

    def _setup_ui(self) -> None:
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Страницы
        self.login_page         = LoginPage(self.config, self.opts)
        self.config_page        = ConfigPage(self.config, self.opts)
        self.download_page      = DownloadPage(self.config, self.opts)
        self.settings_page      = SettingsPage(self.config, self.opts)
        self.notifications_page = NotificationsPage(self.config, self.opts)
        self.archive_viewer     = EmbeddedViewer()

        for page in [
            self.login_page, self.config_page, self.download_page,
            self.settings_page, self.notifications_page, self.archive_viewer,
        ]:
            self.stack.addWidget(page)

        # ── Тулбар ────────────────────────────────────────────────────
        self.toolbar = QToolBar('Навигация')
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        def nav(label, page, tip=''):
            act = QAction(label, self)
            act.setToolTip(tip)
            act.triggered.connect(lambda: self._navigate(page))
            self.toolbar.addAction(act)
            return act

        self.act_login   = nav('🔑  Вход',        self.PAGE_LOGIN)
        self.act_config  = nav('📚  Курсы',        self.PAGE_CONFIG,
                               'Выбрать курсы для загрузки')
        self.act_download= nav('⬇️  Загрузка',     self.PAGE_DOWNLOAD,
                               'Запустить скачивание')
        self.act_settings= nav('⚙️  Настройки',    self.PAGE_SETTINGS,
                               'Что скачивать, производительность, пути')
        self.act_archive = nav('🗂️  Архив',         self.PAGE_ARCHIVE,
                               'Офлайн-просмотр скачанных материалов')

        self._nav_actions = [
            self.act_login, self.act_config, self.act_download,
            self.act_settings, self.act_archive,
        ]

        # После логина включаются
        for a in [self.act_config, self.act_download, self.act_settings]:
            a.setEnabled(False)

        self.toolbar.addSeparator()

        self.act_notifications = nav('🔔  Уведомления', self.PAGE_NOTIFICATIONS,
                                     'Настройка Telegram / Discord уведомлений')
        self.act_notifications.setEnabled(False)

        self.toolbar.addSeparator()

        # Инструменты — в конце
        self.act_manage_db = QAction('🔍  Потерянные файлы', self)
        self.act_manage_db.setEnabled(False)
        self.act_manage_db.setToolTip('Файлы в базе, которых нет на диске')
        self.act_manage_db.triggered.connect(self._on_manage_db)
        self.toolbar.addAction(self.act_manage_db)

        self.act_old_files = QAction('🗑️  Устаревшие копии', self)
        self.act_old_files.setEnabled(False)
        self.act_old_files.setToolTip('Старые версии файлов, замещённые новыми')
        self.act_old_files.triggered.connect(self._on_old_files)
        self.toolbar.addAction(self.act_old_files)

        self.toolbar.addSeparator()

        self.act_logout = QAction('🚪  Выход', self)
        self.act_logout.setEnabled(False)
        self.act_logout.triggered.connect(self._on_logout)
        self.toolbar.addAction(self.act_logout)

        # ── Статус-бар ────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('Войдите в аккаунт Moodle.')

        # Сигналы
        self.login_page.login_successful.connect(self._on_login_success)
        self.login_page.login_failed.connect(self._on_login_failed)
        self.config_page.config_saved.connect(self.download_page.invalidate)
        self.settings_page.config_saved.connect(self.download_page.invalidate)

    def _setup_shortcuts(self) -> None:
        for i, page in enumerate([
            self.PAGE_LOGIN, self.PAGE_CONFIG, self.PAGE_DOWNLOAD,
            self.PAGE_SETTINGS, self.PAGE_ARCHIVE,
        ]):
            QShortcut(QKeySequence(f'Alt+{i + 1}'), self).activated.connect(
                lambda idx=page: self._navigate(idx)
            )

    def _try_auto_login(self) -> None:
        try:
            self.config.load()
            if self.config.get_token():
                self._enable_navigation()
                self._navigate(self.PAGE_DOWNLOAD)
                self.status_bar.showMessage('Конфигурация загружена.')
                return
        except (ConfigHelper.NoConfigError, ValueError):
            pass

    def _on_login_success(self) -> None:
        logging.info('Login successful')
        try:
            self.config.load()
        except ConfigHelper.NoConfigError:
            pass
        self._enable_navigation()
        self._navigate(self.PAGE_CONFIG)
        self.status_bar.showMessage('Вход выполнен. Выберите курсы.')

    def _on_login_failed(self, error_msg: str) -> None:
        logging.error('Login failed: %s', error_msg)
        QMessageBox.critical(self, 'Ошибка входа', error_msg)
        self.status_bar.showMessage('Ошибка входа.')

    def _enable_navigation(self) -> None:
        self._logged_in = True
        for a in [self.act_config, self.act_download, self.act_settings,
                  self.act_notifications, self.act_manage_db,
                  self.act_old_files, self.act_logout]:
            a.setEnabled(True)

    def _navigate(self, page_index: int) -> None:
        self.stack.setCurrentIndex(page_index)
        for i, action in enumerate(self._nav_actions):
            f = QFont()
            f.setBold(i == page_index)
            action.setFont(f)
        if page_index == self.PAGE_CONFIG:
            self.config_page.on_show()
        elif page_index == self.PAGE_DOWNLOAD:
            self.download_page.on_show()
        elif page_index == self.PAGE_SETTINGS:
            self.settings_page.on_show()
        elif page_index == self.PAGE_NOTIFICATIONS:
            self.notifications_page.on_show()

    def _on_logout(self) -> None:
        reply = QMessageBox.question(
            self, 'Выход',
            'Выйти из аккаунта? Активные загрузки будут остановлены.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.download_page.cancel_all()
        self.config.remove_property('token')
        self.config.remove_property('privatetoken')
        self._logged_in = False
        for a in [self.act_config, self.act_download, self.act_settings,
                  self.act_notifications, self.act_manage_db,
                  self.act_old_files, self.act_logout]:
            a.setEnabled(False)
        self._navigate(self.PAGE_LOGIN)
        self.status_bar.showMessage('Выход выполнен.')

    def _on_manage_db(self) -> None:
        from moodle_dl.gui.dialogs.database_dialog import DatabaseManagementDialog
        DatabaseManagementDialog(self.config, self.opts, self).exec()

    def _on_old_files(self) -> None:
        from moodle_dl.gui.dialogs.old_files_dialog import OldFilesDialog
        OldFilesDialog(self.config, self.opts, self).exec()

    def closeEvent(self, event) -> None:
        self._settings.setValue('window/geometry', self.saveGeometry())
        self.download_page.cancel_all()
        self.login_page.cleanup()
        super().closeEvent(event)
