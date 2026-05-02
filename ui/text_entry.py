"""Text-entry helpers with familiar keyboard shortcuts."""

from __future__ import annotations

import pygame
import pygame_gui
from pygame_gui._constants import UI_TEXT_ENTRY_CHANGED


_FALLBACK_CLIPBOARD_TEXT = ""


class ShortcutTextEntryLine(pygame_gui.elements.UITextEntryLine):
    """UITextEntryLine with Ctrl/Cmd+Z and browser-safe clipboard shortcuts."""

    MAX_UNDO_STATES = 80

    def __init__(self, *args, use_browser_clipboard: bool = False, **kwargs) -> None:
        self.use_browser_clipboard = use_browser_clipboard
        self._undo_stack: list[tuple[str, int, list[int]]] = []
        self._restoring_undo = False
        super().__init__(*args, **kwargs)

    def set_text(self, text: str | None):
        super().set_text(text)
        if not getattr(self, "_restoring_undo", False):
            self.clear_undo_history()

    def clear_undo_history(self) -> None:
        self._undo_stack = []

    def process_event(self, event: pygame.event.Event) -> bool:
        if self._should_process_undo(event):
            return self._undo_last_edit()

        before_text = self.text
        before_cursor = self.edit_position
        before_selection = list(self.select_range)
        consumed_event = super().process_event(event)

        if self.text != before_text and not self._restoring_undo:
            self._push_undo_state(before_text, before_cursor, before_selection)

        return consumed_event

    def _should_process_undo(self, event: pygame.event.Event) -> bool:
        return bool(
            self.is_enabled
            and self.is_focused
            and event.type == pygame.KEYDOWN
            and event.key == pygame.K_z
            and (event.mod & pygame.KMOD_CTRL or event.mod & pygame.KMOD_META)
            and not (event.mod & pygame.KMOD_ALT)
        )

    def _push_undo_state(self, text: str, cursor: int, selection: list[int]) -> None:
        state = (text, cursor, selection)
        if self._undo_stack and self._undo_stack[-1] == state:
            return
        self._undo_stack.append(state)
        if len(self._undo_stack) > self.MAX_UNDO_STATES:
            self._undo_stack.pop(0)

    def _undo_last_edit(self) -> bool:
        if not self._undo_stack:
            return True

        text, cursor, selection = self._undo_stack.pop()
        self._restoring_undo = True
        try:
            self.set_text(text)
            self.edit_position = max(0, min(cursor, len(self.text)))
            self.select_range = [
                max(0, min(selection[0], len(self.text))),
                max(0, min(selection[1], len(self.text))),
            ]
            if (
                self.drawable_shape is not None
                and self.drawable_shape.text_box_layout is not None
            ):
                self.drawable_shape.text_box_layout.set_cursor_position(self.edit_position)
                self.drawable_shape.apply_active_text_changes()
        finally:
            self._restoring_undo = False

        self.cursor_has_moved_recently = True
        self._post_text_event(UI_TEXT_ENTRY_CHANGED)
        return True

    def _do_copy(self):
        if self.use_browser_clipboard:
            selected_text = self._get_selected_text()
            if selected_text and not self.is_text_hidden:
                _browser_clipboard_write(selected_text)
            return
        super()._do_copy()

    def _do_cut(self):
        if not self.use_browser_clipboard:
            super()._do_cut()
            return

        bounds = self._get_selection_bounds()
        if bounds is None or self.is_text_hidden:
            return

        low_end, high_end = bounds
        _browser_clipboard_write(self.text[low_end:high_end])
        final_text = self.text[:low_end] + self.text[high_end:]
        self._replace_selection_with_new_text_in_drawable_shape(final_text, "", low_end)

    def _do_paste(self):
        if self.use_browser_clipboard:
            self._paste_text(_browser_clipboard_read())
            return
        super()._do_paste()

    def _paste_text(self, new_text: str) -> None:
        new_text = str(new_text or "")
        if not new_text or not self.validate_text_string(new_text):
            return

        bounds = self._get_selection_bounds()
        if bounds is not None:
            low_end, high_end = bounds
            final_text = self.text[:low_end] + new_text + self.text[high_end:]
            if self._within_length_limit(final_text):
                self._replace_selection_with_new_text_in_drawable_shape(
                    final_text,
                    new_text,
                    low_end,
                )
            return

        final_text = (
            self.text[: self.edit_position]
            + new_text
            + self.text[self.edit_position :]
        )
        if self._within_length_limit(final_text):
            self._insert_new_text_to_shape_at_edit_position(final_text, new_text)

    def _within_length_limit(self, text: str) -> bool:
        return self.length_limit is None or len(text) <= self.length_limit

    def _get_selection_bounds(self) -> tuple[int, int] | None:
        if abs(self.select_range[0] - self.select_range[1]) <= 0:
            return None
        return (
            min(self.select_range[0], self.select_range[1]),
            max(self.select_range[0], self.select_range[1]),
        )

    def _get_selected_text(self) -> str:
        bounds = self._get_selection_bounds()
        if bounds is None:
            return ""
        low_end, high_end = bounds
        return self.text[low_end:high_end]


def _browser_clipboard_write(text: str) -> None:
    global _FALLBACK_CLIPBOARD_TEXT

    _FALLBACK_CLIPBOARD_TEXT = str(text or "")
    try:
        import platform

        clipboard = getattr(platform.window, "panTrialClipboard", None)
        if clipboard is not None:
            clipboard.writeText(_FALLBACK_CLIPBOARD_TEXT)
    except Exception:
        pass


def _browser_clipboard_read() -> str:
    try:
        import platform

        clipboard = getattr(platform.window, "panTrialClipboard", None)
        if clipboard is not None:
            return str(clipboard.readText(_FALLBACK_CLIPBOARD_TEXT) or "")
    except Exception:
        pass
    return _FALLBACK_CLIPBOARD_TEXT
