from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from moodle_dl.config import ConfigHelper


class CourseOptionsDialog(QDialog):
    """Dialog for per-course customization (custom name, directory structure)."""

    def __init__(self, config: ConfigHelper, course_id: int, course_name: str, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.course_id = course_id
        self.course_name = course_name

        self.setWindowTitle(f'Options for: {course_name}')
        self.setMinimumWidth(400)

        self._setup_ui()
        self._load_options()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.custom_name_input = QLineEdit()
        self.custom_name_input.setPlaceholderText(self.course_name)
        self.custom_name_input.setToolTip('Override the course folder name. Leave empty to use the default.')
        form.addRow('Custom Name:', self.custom_name_input)

        self.cb_create_dir = QCheckBox('Create Directory Structure')
        self.cb_create_dir.setChecked(True)
        self.cb_create_dir.setToolTip('Create subdirectories matching the Moodle course section structure.')
        form.addRow(self.cb_create_dir)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_options(self) -> None:
        """Load existing per-course options from config."""
        options = self.config.get_property_or('options_of_courses', {})
        course_opts = options.get(str(self.course_id), {})
        self.custom_name_input.setText(course_opts.get('overwrite_name_with', ''))
        self.cb_create_dir.setChecked(course_opts.get('create_directory_structure', True))

    def _on_save(self) -> None:
        """Save per-course options to config."""
        options = self.config.get_property_or('options_of_courses', {})
        if not isinstance(options, dict):
            options = {}

        course_opts = {}
        custom_name = self.custom_name_input.text().strip()
        if custom_name:
            course_opts['overwrite_name_with'] = custom_name
        course_opts['create_directory_structure'] = self.cb_create_dir.isChecked()

        options[str(self.course_id)] = course_opts
        self.config.set_property('options_of_courses', options)
        self.accept()
