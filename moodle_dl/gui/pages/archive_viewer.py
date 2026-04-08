"""Embedded viewer for archived files (HTML, PDF, images, text)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QLabel, QStackedWidget, QPlainTextEdit, QWidget


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".xml", ".log", ".py", ".html", ".htm"}
WEB_SUFFIXES = {".html", ".htm", ".pdf"}


class EmbeddedViewer(QStackedWidget):
    """Stack of HTML/PDF, image, and plain-text viewers."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.web = QWebEngineView(self)
        settings = self.web.settings()
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.PdfViewerEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)

        self.image = QLabel(self)
        self.image.setAlignment(self.image.alignment())
        self.image.setScaledContents(False)
        self.image.setText("Откройте файл из дерева слева.")

        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)

        self.addWidget(self.web)
        self.addWidget(self.image)
        self.addWidget(self.text)
        self.setCurrentWidget(self.image)

    def show_path(self, path: Path) -> None:
        if not path.exists():
            self.text.setPlainText(f"Файл не найден: {path}")
            self.setCurrentWidget(self.text)
            return

        suffix = path.suffix.lower()
        if suffix in WEB_SUFFIXES:
            self.web.load(QUrl.fromLocalFile(str(path)))
            self.setCurrentWidget(self.web)
            return

        if suffix in IMAGE_SUFFIXES:
            from PySide6.QtGui import QPixmap

            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.image.setPixmap(
                    pixmap.scaled(
                        self.image.size(),
                        aspectMode=1,  # KeepAspectRatio
                        mode=1,  # SmoothTransformation
                    )
                )
                self.setCurrentWidget(self.image)
                return

        if suffix in TEXT_SUFFIXES or path.stat().st_size < 1_000_000:
            try:
                self.text.setPlainText(path.read_text(encoding="utf-8", errors="replace"))
            except OSError as exc:
                self.text.setPlainText(f"Ошибка чтения: {exc}")
            self.setCurrentWidget(self.text)
            return

        # Fallback: пусть WebEngine сам решит (часто умеет PDF/изображения).
        self.web.load(QUrl.fromLocalFile(str(path)))
        self.setCurrentWidget(self.web)
