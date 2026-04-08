import logging

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from moodle_dl.config import ConfigHelper
from moodle_dl.gui.style_utils import set_status_text
from moodle_dl.gui.workers import FetchCoursesWorker


class ConfigPage(QWidget):
    config_saved = Signal()

    def __init__(self, config: ConfigHelper, opts) -> None:
        super().__init__()
        self.config = config
        self.opts = opts
        self._worker = None
        self._course_checkboxes = {}
        self._checkbox_to_course = {}
        self._courses_loaded = False

        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Toolbar row ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.fetch_btn = QPushButton('🔄  Обновить список курсов')
        self.fetch_btn.setFixedHeight(32)
        self.fetch_btn.clicked.connect(self._on_fetch_courses)
        btn_row.addWidget(self.fetch_btn)

        self.select_all_btn = QPushButton('Выбрать все')
        self.select_all_btn.setFixedHeight(32)
        self.select_all_btn.clicked.connect(self._select_all_courses)
        self.select_all_btn.setEnabled(False)
        btn_row.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton('Снять все')
        self.deselect_all_btn.setFixedHeight(32)
        self.deselect_all_btn.clicked.connect(self._deselect_all_courses)
        self.deselect_all_btn.setEnabled(False)
        btn_row.addWidget(self.deselect_all_btn)

        btn_row.addStretch()

        self.save_btn = QPushButton('💾  Сохранить')
        self.save_btn.setFixedHeight(32)
        self.save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

        # ── Mode toggle ────────────────────────────────────────────────
        mode_row = QHBoxLayout()
        self.radio_whitelist = QRadioButton('Скачивать выбранные')
        self.radio_blacklist = QRadioButton('Скачивать все, кроме выбранных')
        self.radio_whitelist.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self.radio_whitelist)
        self._mode_group.addButton(self.radio_blacklist)
        mode_row.addWidget(self.radio_whitelist)
        mode_row.addWidget(self.radio_blacklist)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ── Status + filter ────────────────────────────────────────────
        self.courses_status = QLabel('Нажмите «Обновить» для загрузки курсов.')
        layout.addWidget(self.courses_status)

        self.course_filter_input = QLineEdit()
        self.course_filter_input.setPlaceholderText('🔍  Поиск курсов…')
        self.course_filter_input.setClearButtonEnabled(True)
        self.course_filter_input.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self.course_filter_input)

        hint = QLabel('Двойной клик по курсу — индивидуальные настройки.')
        hint.setStyleSheet('color: #888; font-style: italic; font-size: 11px;')
        layout.addWidget(hint)

        # ── Scrollable course list ─────────────────────────────────────
        self.course_scroll = QScrollArea()
        self.course_scroll.setWidgetResizable(True)
        self.course_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.course_list_widget = QWidget()
        self.course_list_layout = QVBoxLayout(self.course_list_widget)
        self.course_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.course_list_layout.setSpacing(2)
        self.course_scroll.setWidget(self.course_list_widget)
        layout.addWidget(self.course_scroll, 1)   # stretch = 1 → занимает всё свободное место

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence('Ctrl+S'), self).activated.connect(self._on_save)
        QShortcut(QKeySequence('Ctrl+R'), self).activated.connect(self._on_fetch_courses)

    # ── Public lifecycle ───────────────────────────────────────────────

    def on_show(self) -> None:
        if not self._courses_loaded:
            self._on_fetch_courses()

    # ── Slots ──────────────────────────────────────────────────────────

    def _on_fetch_courses(self) -> None:
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText('Загрузка…')
        set_status_text(self.courses_status, 'Загрузка курсов…', 'info')

        self._worker = FetchCoursesWorker(self.config, self.opts)
        self._worker.courses_fetched.connect(self._on_courses_fetched)
        self._worker.error_occurred.connect(self._on_fetch_error)
        self._worker.start()

    def _on_courses_fetched(self, courses: list) -> None:
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText('🔄  Обновить список курсов')
        self._courses_loaded = True
        set_status_text(self.courses_status, f'Найдено курсов: {len(courses)}.', 'success')
        self.select_all_btn.setEnabled(True)
        self.deselect_all_btn.setEnabled(True)

        for cb in self._course_checkboxes.values():
            self.course_list_layout.removeWidget(cb)
            cb.deleteLater()
        self._course_checkboxes.clear()
        self._checkbox_to_course.clear()

        download_ids = set(self.config.get_download_course_ids())
        dont_download_ids = set(self.config.get_dont_download_course_ids())
        use_blacklist = len(dont_download_ids) > 0 and len(download_ids) == 0
        first_time = len(download_ids) == 0 and len(dont_download_ids) == 0

        if use_blacklist:
            self.radio_blacklist.setChecked(True)
        else:
            self.radio_whitelist.setChecked(True)

        for course_info in courses:
            course_id = course_info['id']
            fullname = course_info['fullname']
            cb = QCheckBox(f'{fullname}  (ID: {course_id})')
            cb.setStyleSheet('QCheckBox { padding: 3px; }')
            cb.installEventFilter(self)
            self._checkbox_to_course[cb] = (course_id, fullname)
            if first_time:
                cb.setChecked(True)
            elif use_blacklist:
                cb.setChecked(course_id not in dont_download_ids)
            else:
                cb.setChecked(course_id in download_ids)
            self.course_list_layout.addWidget(cb)
            self._course_checkboxes[course_id] = cb

        self._on_filter_changed(self.course_filter_input.text())

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonDblClick and obj in self._checkbox_to_course:
            cid, name = self._checkbox_to_course[obj]
            self._on_course_double_clicked(cid, name)
            return True
        return super().eventFilter(obj, event)

    def _on_fetch_error(self, error_msg: str) -> None:
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText('🔄  Обновить список курсов')
        set_status_text(self.courses_status, f'Ошибка: {error_msg}', 'error')
        logging.error('Failed to fetch courses: %s', error_msg)

    def _on_filter_changed(self, text: str) -> None:
        needle = text.strip().lower()
        for cb in self._course_checkboxes.values():
            cb.setVisible(needle in cb.text().lower() if needle else True)

    def _on_course_double_clicked(self, course_id: int, course_name: str) -> None:
        from moodle_dl.gui.dialogs.course_options_dialog import CourseOptionsDialog
        dialog = CourseOptionsDialog(self.config, self.opts, course_id, course_name, self)
        dialog.exec()

    def _select_all_courses(self) -> None:
        for cb in self._course_checkboxes.values():
            if cb.isVisible():
                cb.setChecked(True)

    def _deselect_all_courses(self) -> None:
        for cb in self._course_checkboxes.values():
            if cb.isVisible():
                cb.setChecked(False)

    def _on_save(self) -> None:
        use_blacklist = self.radio_blacklist.isChecked()

        if use_blacklist:
            unchecked_ids = [cid for cid, cb in self._course_checkboxes.items() if not cb.isChecked()]
            self.config.set_property('dont_download_course_ids', unchecked_ids)
            self.config.remove_property('download_course_ids')
        else:
            selected_ids = [cid for cid, cb in self._course_checkboxes.items() if cb.isChecked()]
            if self._course_checkboxes and not selected_ids:
                QMessageBox.warning(self, 'Ничего не выбрано', 'Выберите хотя бы один курс.')
                return
            self.config.set_property('download_course_ids', selected_ids)
            self.config.remove_property('dont_download_course_ids')

        self.config_saved.emit()
        set_status_text(self.courses_status, 'Конфигурация сохранена.', 'success')
