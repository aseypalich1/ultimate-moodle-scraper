import logging

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
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

        # Course selection
        courses_group = QGroupBox('Courses')
        courses_layout = QVBoxLayout()

        btn_row = QHBoxLayout()
        self.fetch_btn = QPushButton('Fetch Courses')
        self.fetch_btn.clicked.connect(self._on_fetch_courses)
        btn_row.addWidget(self.fetch_btn)

        self.select_all_btn = QPushButton('Select All')
        self.select_all_btn.clicked.connect(self._select_all_courses)
        self.select_all_btn.setEnabled(False)
        btn_row.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton('Deselect All')
        self.deselect_all_btn.clicked.connect(self._deselect_all_courses)
        self.deselect_all_btn.setEnabled(False)
        btn_row.addWidget(self.deselect_all_btn)

        btn_row.addStretch()
        courses_layout.addLayout(btn_row)

        self.courses_status = QLabel('Click "Fetch Courses" to load your course list.')
        courses_layout.addWidget(self.courses_status)

        # Course search/filter
        self.course_filter_input = QLineEdit()
        self.course_filter_input.setPlaceholderText('Filter courses\u2026')
        self.course_filter_input.setClearButtonEnabled(True)
        self.course_filter_input.textChanged.connect(self._on_filter_changed)
        courses_layout.addWidget(self.course_filter_input)

        # Hint label for course options
        hint_label = QLabel('Double-click a course to set custom name and options.')
        hint_label.setStyleSheet('color: #666; font-style: italic;')
        courses_layout.addWidget(hint_label)

        # Scrollable course list
        self.course_scroll = QScrollArea()
        self.course_scroll.setWidgetResizable(True)
        self.course_list_widget = QWidget()
        self.course_list_layout = QVBoxLayout(self.course_list_widget)
        self.course_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.course_scroll.setWidget(self.course_list_widget)
        courses_layout.addWidget(self.course_scroll)

        courses_group.setLayout(courses_layout)
        layout.addWidget(courses_group, 1)  # stretch factor so scroll area expands

        # Download options
        options_group = QGroupBox('Download Options')
        options_layout = QVBoxLayout()

        self.opt_submissions = QCheckBox('Download Submissions')
        self.opt_submissions.setToolTip('Download student assignment submissions.')
        self.opt_descriptions = QCheckBox('Download Descriptions')
        self.opt_descriptions.setToolTip('Download activity and resource descriptions as HTML files.')
        self.opt_links_in_desc = QCheckBox('Download Links in Descriptions')
        self.opt_links_in_desc.setToolTip('Download files linked within activity descriptions.')
        self.opt_databases = QCheckBox('Download Databases')
        self.opt_databases.setToolTip('Download Moodle database activity entries.')
        self.opt_forums = QCheckBox('Download Forums')
        self.opt_forums.setToolTip('Download forum posts and attachments.')
        self.opt_quizzes = QCheckBox('Download Quizzes')
        self.opt_quizzes.setToolTip('Download quiz attempts and results.')
        self.opt_lessons = QCheckBox('Download Lessons')
        self.opt_lessons.setToolTip('Download lesson activity content.')
        self.opt_workshops = QCheckBox('Download Workshops')
        self.opt_workshops.setToolTip('Download workshop submissions and assessments.')
        self.opt_books = QCheckBox('Download Books')
        self.opt_books.setToolTip('Download book resource content as HTML.')
        self.opt_calendars = QCheckBox('Download Calendars')
        self.opt_calendars.setToolTip('Download course calendar events.')
        self.opt_linked_files = QCheckBox('Download Linked Files')
        self.opt_linked_files.setToolTip('Download externally linked files referenced in courses.')
        self.opt_cookie_files = QCheckBox('Download Files Requiring Cookie')
        self.opt_cookie_files.setToolTip('Also download files that require browser cookies for access.')

        for cb in [
            self.opt_submissions,
            self.opt_descriptions,
            self.opt_links_in_desc,
            self.opt_databases,
            self.opt_forums,
            self.opt_quizzes,
            self.opt_lessons,
            self.opt_workshops,
            self.opt_books,
            self.opt_calendars,
            self.opt_linked_files,
            self.opt_cookie_files,
        ]:
            options_layout.addWidget(cb)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Save button
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.save_btn = QPushButton('Save Configuration')
        self.save_btn.clicked.connect(self._on_save)
        save_layout.addWidget(self.save_btn)
        layout.addLayout(save_layout)
        layout.addStretch()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        save_shortcut = QShortcut(QKeySequence('Ctrl+S'), self)
        save_shortcut.activated.connect(self._on_save)

    def on_show(self) -> None:
        """Called when this page becomes visible."""
        self._load_current_options()
        if not self._courses_loaded:
            self._on_fetch_courses()

    def _load_current_options(self) -> None:
        """Load current config options into checkboxes."""
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
        except (ValueError, ConfigHelper.NoConfigError):
            pass

    def _on_fetch_courses(self) -> None:
        """Fetch the course list from Moodle."""
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText('Fetching\u2026')
        self.setCursor(QCursor(Qt.CursorShape.BusyCursor))
        set_status_text(self.courses_status, 'Fetching courses\u2026', 'info')

        self._worker = FetchCoursesWorker(self.config, self.opts)
        self._worker.courses_fetched.connect(self._on_courses_fetched)
        self._worker.error_occurred.connect(self._on_fetch_error)
        self._worker.start()

    def _on_courses_fetched(self, courses: list) -> None:
        """Handle fetched course list."""
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText('Fetch Courses')
        self.unsetCursor()
        self._courses_loaded = True
        set_status_text(self.courses_status, f'Found {len(courses)} courses.', 'success')
        self.select_all_btn.setEnabled(True)
        self.deselect_all_btn.setEnabled(True)

        # Clear existing checkboxes
        for cb in self._course_checkboxes.values():
            self.course_list_layout.removeWidget(cb)
            cb.deleteLater()
        self._course_checkboxes.clear()
        self._checkbox_to_course.clear()

        # Get currently selected course IDs
        selected_ids = set(self.config.get_download_course_ids())
        # If no courses are selected yet, select all by default
        select_all_by_default = len(selected_ids) == 0

        # Add checkboxes for each course
        for course_info in courses:
            course_id = course_info['id']
            fullname = course_info['fullname']
            cb = QCheckBox(f'{fullname} (ID: {course_id})')
            cb.installEventFilter(self)
            self._checkbox_to_course[cb] = (course_id, fullname)
            if select_all_by_default or course_id in selected_ids:
                cb.setChecked(True)
            self.course_list_layout.addWidget(cb)
            self._course_checkboxes[course_id] = cb

        # Apply current filter
        self._on_filter_changed(self.course_filter_input.text())

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonDblClick and obj in self._checkbox_to_course:
            cid, name = self._checkbox_to_course[obj]
            self._on_course_double_clicked(cid, name)
            return True
        return super().eventFilter(obj, event)

    def _on_fetch_error(self, error_msg: str) -> None:
        """Handle course fetch error."""
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText('Fetch Courses')
        self.unsetCursor()
        set_status_text(self.courses_status, f'Error: {error_msg}', 'error')
        logging.error('Failed to fetch courses: %s', error_msg)

    def _on_filter_changed(self, text: str) -> None:
        """Filter course checkboxes by search text."""
        needle = text.strip().lower()
        for cb in self._course_checkboxes.values():
            cb.setVisible(needle in cb.text().lower() if needle else True)

    def _on_course_double_clicked(self, course_id: int, course_name: str) -> None:
        """Open per-course options dialog."""
        from moodle_dl.gui.dialogs.course_options_dialog import CourseOptionsDialog

        dialog = CourseOptionsDialog(self.config, course_id, course_name, self)
        dialog.exec()

    def _select_all_courses(self) -> None:
        """Select all visible course checkboxes."""
        for cb in self._course_checkboxes.values():
            if cb.isVisible():
                cb.setChecked(True)

    def _deselect_all_courses(self) -> None:
        """Deselect all visible course checkboxes."""
        for cb in self._course_checkboxes.values():
            if cb.isVisible():
                cb.setChecked(False)

    def _on_save(self) -> None:
        """Save course selection and download options."""
        # Save selected course IDs
        selected_ids = []
        for course_id, cb in self._course_checkboxes.items():
            if cb.isChecked():
                selected_ids.append(course_id)

        if self._course_checkboxes and not selected_ids:
            QMessageBox.warning(self, 'No courses selected', 'Please select at least one course.')
            return

        self.config.set_property('download_course_ids', selected_ids)

        # Save download options
        self.config.set_property('download_submissions', self.opt_submissions.isChecked())
        self.config.set_property('download_descriptions', self.opt_descriptions.isChecked())
        self.config.set_property('download_links_in_descriptions', self.opt_links_in_desc.isChecked())
        self.config.set_property('download_databases', self.opt_databases.isChecked())
        self.config.set_property('download_forums', self.opt_forums.isChecked())
        self.config.set_property('download_quizzes', self.opt_quizzes.isChecked())
        self.config.set_property('download_lessons', self.opt_lessons.isChecked())
        self.config.set_property('download_workshops', self.opt_workshops.isChecked())
        self.config.set_property('download_books', self.opt_books.isChecked())
        self.config.set_property('download_calendars', self.opt_calendars.isChecked())
        self.config.set_property('download_linked_files', self.opt_linked_files.isChecked())
        self.config.set_property('download_also_with_cookie', self.opt_cookie_files.isChecked())

        QMessageBox.information(self, 'Saved', 'Configuration saved successfully.')
        self.config_saved.emit()
