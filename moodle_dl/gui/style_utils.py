"""Helpers for color-coded status labels in the GUI."""

from PySide6.QtWidgets import QLabel

_LEVEL_COLORS = {
    'info': '#333333',
    'success': '#2e7d32',
    'error': '#c62828',
    'warning': '#e65100',
}


def set_status_text(label: QLabel, text: str, level: str = 'info') -> None:
    """Set *label* text with color and bold styling based on *level*."""
    color = _LEVEL_COLORS.get(level, _LEVEL_COLORS['info'])
    label.setText(f'<span style="color:{color}; font-weight:bold">{text}</span>')
