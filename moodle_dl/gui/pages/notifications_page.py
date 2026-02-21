from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from moodle_dl.config import ConfigHelper
from moodle_dl.gui.style_utils import set_status_text
from moodle_dl.gui.workers import TestDiscordWorker, TestTelegramWorker


class NotificationsPage(QWidget):

    def __init__(self, config: ConfigHelper, opts) -> None:
        super().__init__()
        self.config = config
        self.opts = opts
        self._telegram_worker = None
        self._discord_worker = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- Telegram Tab ---
        telegram_tab = QWidget()
        tg_layout = QVBoxLayout(telegram_tab)

        tg_group = QGroupBox('Telegram Configuration')
        tg_form = QFormLayout()

        self.tg_token_input = QLineEdit()
        self.tg_token_input.setPlaceholderText('123456:ABC-DEF...')
        self.tg_token_input.setToolTip('Bot token from @BotFather.')
        tg_form.addRow('Bot Token:', self.tg_token_input)

        self.tg_chat_id_input = QLineEdit()
        self.tg_chat_id_input.setPlaceholderText('e.g. 123456789')
        self.tg_chat_id_input.setToolTip('Your Telegram chat ID. Send /start to @userinfobot to find it.')
        tg_form.addRow('Chat ID:', self.tg_chat_id_input)

        self.tg_send_errors = QCheckBox('Send Error Reports')
        self.tg_send_errors.setToolTip('Also send error notifications via Telegram.')
        tg_form.addRow(self.tg_send_errors)

        tg_group.setLayout(tg_form)
        tg_layout.addWidget(tg_group)

        tg_btn_row = QHBoxLayout()
        self.tg_test_btn = QPushButton('Test')
        self.tg_test_btn.clicked.connect(self._on_test_telegram)
        tg_btn_row.addWidget(self.tg_test_btn)

        self.tg_save_btn = QPushButton('Save')
        self.tg_save_btn.clicked.connect(self._on_save_telegram)
        tg_btn_row.addWidget(self.tg_save_btn)

        self.tg_disable_btn = QPushButton('Disable')
        self.tg_disable_btn.clicked.connect(self._on_disable_telegram)
        tg_btn_row.addWidget(self.tg_disable_btn)

        tg_btn_row.addStretch()
        tg_layout.addLayout(tg_btn_row)

        self.tg_status = QLabel('')
        tg_layout.addWidget(self.tg_status)
        tg_layout.addStretch()

        self.tabs.addTab(telegram_tab, 'Telegram')

        # --- Discord Tab ---
        discord_tab = QWidget()
        dc_layout = QVBoxLayout(discord_tab)

        dc_group = QGroupBox('Discord Configuration')
        dc_form_layout = QVBoxLayout()

        dc_label = QLabel('Webhook URLs (one per line):')
        dc_form_layout.addWidget(dc_label)

        self.dc_webhooks_input = QTextEdit()
        self.dc_webhooks_input.setPlaceholderText('https://discord.com/api/webhooks/...')
        self.dc_webhooks_input.setToolTip('Enter one Discord webhook URL per line.')
        self.dc_webhooks_input.setMaximumHeight(120)
        dc_form_layout.addWidget(self.dc_webhooks_input)

        dc_group.setLayout(dc_form_layout)
        dc_layout.addWidget(dc_group)

        dc_btn_row = QHBoxLayout()
        self.dc_test_btn = QPushButton('Test')
        self.dc_test_btn.clicked.connect(self._on_test_discord)
        dc_btn_row.addWidget(self.dc_test_btn)

        self.dc_save_btn = QPushButton('Save')
        self.dc_save_btn.clicked.connect(self._on_save_discord)
        dc_btn_row.addWidget(self.dc_save_btn)

        self.dc_disable_btn = QPushButton('Disable')
        self.dc_disable_btn.clicked.connect(self._on_disable_discord)
        dc_btn_row.addWidget(self.dc_disable_btn)

        dc_btn_row.addStretch()
        dc_layout.addLayout(dc_btn_row)

        self.dc_status = QLabel('')
        dc_layout.addWidget(self.dc_status)
        dc_layout.addStretch()

        self.tabs.addTab(discord_tab, 'Discord')

        layout.addStretch()

    def on_show(self) -> None:
        """Load current notification configuration."""
        # Telegram
        tg_token = self.config.get_property_or('telegram_token', '')
        tg_chat_id = self.config.get_property_or('telegram_chatid', '')
        tg_send_errors = self.config.get_property_or('telegram_send_error_reports', False)
        self.tg_token_input.setText(tg_token or '')
        self.tg_chat_id_input.setText(tg_chat_id or '')
        self.tg_send_errors.setChecked(bool(tg_send_errors))

        # Discord
        dc_webhooks = self.config.get_property_or('discord_webhook_urls', [])
        if isinstance(dc_webhooks, list):
            self.dc_webhooks_input.setPlainText('\n'.join(dc_webhooks))
        else:
            self.dc_webhooks_input.setPlainText('')

    # --- Telegram ---

    def _on_test_telegram(self) -> None:
        """Send a test message via Telegram."""
        token = self.tg_token_input.text().strip()
        chat_id = self.tg_chat_id_input.text().strip()
        if not token or not chat_id:
            set_status_text(self.tg_status, 'Please enter both Bot Token and Chat ID.', 'error')
            return

        self.tg_test_btn.setEnabled(False)
        self.tg_test_btn.setText('Sending\u2026')
        self.setCursor(QCursor(Qt.CursorShape.BusyCursor))
        set_status_text(self.tg_status, 'Sending test message\u2026', 'info')

        self._telegram_worker = TestTelegramWorker(token, chat_id)
        self._telegram_worker.test_successful.connect(self._on_telegram_test_success)
        self._telegram_worker.test_failed.connect(self._on_telegram_test_failed)
        self._telegram_worker.start()

    def _on_telegram_test_success(self) -> None:
        """Handle successful Telegram test."""
        self.tg_test_btn.setEnabled(True)
        self.tg_test_btn.setText('Test')
        self.unsetCursor()
        set_status_text(self.tg_status, 'Test message sent successfully!', 'success')

    def _on_telegram_test_failed(self, error_msg: str) -> None:
        """Handle failed Telegram test."""
        self.tg_test_btn.setEnabled(True)
        self.tg_test_btn.setText('Test')
        self.unsetCursor()
        set_status_text(self.tg_status, f'Test failed: {error_msg}', 'error')

    def _on_save_telegram(self) -> None:
        """Save Telegram configuration."""
        token = self.tg_token_input.text().strip()
        chat_id = self.tg_chat_id_input.text().strip()
        if not token or not chat_id:
            set_status_text(self.tg_status, 'Please enter both Bot Token and Chat ID.', 'error')
            return

        self.config.set_property('telegram_token', token)
        self.config.set_property('telegram_chatid', chat_id)
        self.config.set_property('telegram_send_error_reports', self.tg_send_errors.isChecked())
        set_status_text(self.tg_status, 'Telegram configuration saved.', 'success')

    def _on_disable_telegram(self) -> None:
        """Disable Telegram notifications."""
        self.config.set_property('telegram_token', '')
        self.config.set_property('telegram_chatid', '')
        self.config.set_property('telegram_send_error_reports', False)
        self.tg_token_input.clear()
        self.tg_chat_id_input.clear()
        self.tg_send_errors.setChecked(False)
        set_status_text(self.tg_status, 'Telegram notifications disabled.', 'info')

    # --- Discord ---

    def _get_discord_webhooks(self) -> list:
        """Parse webhook URLs from the text area."""
        text = self.dc_webhooks_input.toPlainText().strip()
        if not text:
            return []
        return [url.strip() for url in text.splitlines() if url.strip()]

    def _on_test_discord(self) -> None:
        """Send a test message via Discord."""
        webhooks = self._get_discord_webhooks()
        if not webhooks:
            set_status_text(self.dc_status, 'Please enter at least one webhook URL.', 'error')
            return

        self.dc_test_btn.setEnabled(False)
        self.dc_test_btn.setText('Sending\u2026')
        self.setCursor(QCursor(Qt.CursorShape.BusyCursor))
        set_status_text(self.dc_status, 'Sending test message\u2026', 'info')

        self._discord_worker = TestDiscordWorker(webhooks)
        self._discord_worker.test_successful.connect(self._on_discord_test_success)
        self._discord_worker.test_failed.connect(self._on_discord_test_failed)
        self._discord_worker.start()

    def _on_discord_test_success(self) -> None:
        """Handle successful Discord test."""
        self.dc_test_btn.setEnabled(True)
        self.dc_test_btn.setText('Test')
        self.unsetCursor()
        set_status_text(self.dc_status, 'Test message sent successfully!', 'success')

    def _on_discord_test_failed(self, error_msg: str) -> None:
        """Handle failed Discord test."""
        self.dc_test_btn.setEnabled(True)
        self.dc_test_btn.setText('Test')
        self.unsetCursor()
        set_status_text(self.dc_status, f'Test failed: {error_msg}', 'error')

    def _on_save_discord(self) -> None:
        """Save Discord configuration."""
        webhooks = self._get_discord_webhooks()
        if not webhooks:
            set_status_text(self.dc_status, 'Please enter at least one webhook URL.', 'error')
            return

        self.config.set_property('discord_webhook_urls', webhooks)
        set_status_text(self.dc_status, 'Discord configuration saved.', 'success')

    def _on_disable_discord(self) -> None:
        """Disable Discord notifications."""
        self.config.set_property('discord_webhook_urls', [])
        self.dc_webhooks_input.clear()
        set_status_text(self.dc_status, 'Discord notifications disabled.', 'info')
