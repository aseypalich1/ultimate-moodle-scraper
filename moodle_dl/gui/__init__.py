def gui_main(opts):
    "Entry point for the GUI. Called from main.py when --gui is passed."
    import sys

    from PySide6.QtWidgets import (  # noqa: F401 - validates PySide6 availability
        QApplication,
    )

    from moodle_dl.gui.app import create_app

    app = create_app(opts)
    sys.exit(app.exec())
