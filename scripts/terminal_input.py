import sys
from dataclasses import dataclass
from typing import Optional


MENU_ACTIONS = ("newline", "start_now", "start_5s", "start_custom", "clear", "exit")
MENU_LABELS = {
    "newline": "New Line",
    "start_now": "Start Now",
    "start_5s": "Start After 5s",
    "start_custom": "Start After Custom Delay",
    "clear": "Clear",
    "exit": "Exit",
}


@dataclass(frozen=True)
class TaskPromptResult:
    text: str
    delay_seconds: float = 5.0


@dataclass
class MenuState:
    selected_index: int = 0

    def select_previous(self):
        self.selected_index = (self.selected_index - 1) % len(MENU_ACTIONS)

    def select_next(self):
        self.selected_index = (self.selected_index + 1) % len(MENU_ACTIONS)

    def selected_action(self) -> str:
        return MENU_ACTIONS[self.selected_index]


def parse_delay_seconds(value: str) -> Optional[float]:
    try:
        seconds = float(value.strip())
    except ValueError:
        return None
    if seconds < 0:
        return None
    return seconds


def _fallback_prompt() -> Optional[TaskPromptResult]:
    lines = []
    while True:
        print("Enter task text. Submit an empty line to open the action menu.")
        while True:
            try:
                line = input("> ")
            except EOFError:
                return None
            if line == "":
                break
            lines.append(line)

        task_text = "\n".join(lines)
        print("\n1. New Line\n2. Start Now\n3. Start After 5s\n4. Start After Custom Delay\n5. Clear\n6. Exit")
        choice = input("Choose an action: ").strip()
        if choice == "1":
            lines.append("")
            continue
        if choice == "2":
            return TaskPromptResult(task_text, delay_seconds=0) if task_text.strip() else None
        if choice == "3":
            return TaskPromptResult(task_text, delay_seconds=5) if task_text.strip() else None
        if choice == "4":
            seconds = parse_delay_seconds(input("Delay seconds: "))
            if seconds is not None and task_text.strip():
                return TaskPromptResult(task_text, delay_seconds=seconds)
            print("Invalid delay or empty task.")
            continue
        if choice == "5":
            lines = []
            continue
        if choice == "6":
            return None


def _run_prompt_toolkit_editor(logo_text: str = "") -> Optional[TaskPromptResult]:
    from prompt_toolkit.application import Application
    from prompt_toolkit.document import Document
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    from prompt_toolkit.widgets import Frame, TextArea

    state = MenuState()
    status = {"text": ""}

    logo_lines = [line for line in logo_text.strip().splitlines() if line.strip()]

    def header_fragments():
        fragments = []
        for line in logo_lines[:6]:
            fragments.append(("class:logo", f"{line}\n"))
        if logo_lines:
            fragments.append(("", "\n"))
        fragments.extend(
            [
                ("class:title", "Iris Task Launcher\n"),
                ("class:hint", "Use Up/Down to choose an action, then press Enter.\n"),
                ("class:hint", "New Line is selected by default, so Enter normally inserts a line break."),
            ]
        )
        return fragments

    text_area = TextArea(
        text="",
        multiline=True,
        wrap_lines=True,
        prompt="> ",
    )
    delay_area = TextArea(
        text="",
        multiline=False,
        height=1,
        prompt="Custom delay seconds > ",
    )

    def menu_fragments():
        descriptions = {
            "newline": "insert a blank line",
            "start_now": "run immediately",
            "start_5s": "prepare screen for five seconds",
            "start_custom": "use the delay field",
            "clear": "reset task text",
            "exit": "close launcher",
        }
        fragments = []
        if status["text"]:
            fragments.extend([("class:status", status["text"]), ("", "\n")])
        fragments.append(("class:menu-title", "Actions\n"))
        for index, action in enumerate(MENU_ACTIONS):
            label_style = "class:selected" if index == state.selected_index else "class:action"
            desc_style = "class:selected" if index == state.selected_index else "class:muted"
            marker = ">" if index == state.selected_index else " "
            fragments.append((label_style, f" {marker} {MENU_LABELS[action]:<28}"))
            fragments.append((desc_style, f"{descriptions[action]}\n"))
        return fragments

    key_bindings = KeyBindings()

    @key_bindings.add("up", eager=True)
    def _select_previous(event):
        state.select_previous()
        status["text"] = ""
        event.app.invalidate()

    @key_bindings.add("down", eager=True)
    def _select_next(event):
        state.select_next()
        status["text"] = ""
        event.app.invalidate()

    def confirm_selected(event):
        action = state.selected_action()
        if action == "newline":
            event.app.layout.focus(text_area)
            text_area.buffer.insert_text("\n")
            return
        if action == "clear":
            clear_task(event)
            return
        if action == "exit":
            event.app.exit(result=None)
            return
        if action == "start_custom":
            seconds = parse_delay_seconds(delay_area.text)
            if seconds is None:
                status["text"] = "Enter a non-negative number in Custom delay seconds."
                event.app.layout.focus(delay_area)
                event.app.invalidate()
                return
            start_task(event, delay_seconds=seconds)
            return
        if action == "start_now":
            start_task(event, delay_seconds=0)
            return
        if action == "start_5s":
            start_task(event, delay_seconds=5)

    def start_task(event, delay_seconds: float):
        if not text_area.text.strip():
            status["text"] = "Task description is empty."
            event.app.invalidate()
            return
        event.app.exit(result=TaskPromptResult(text_area.text, delay_seconds=delay_seconds))

    def clear_task(event):
        state.selected_index = 0
        text_area.buffer.document = Document("", cursor_position=0)
        delay_area.buffer.document = Document("", cursor_position=0)
        status["text"] = ""
        event.app.layout.focus(text_area)
        event.app.invalidate()

    @key_bindings.add("enter", eager=True)
    def _confirm_selected(event):
        confirm_selected(event)

    root = Frame(
        HSplit(
            [
                Window(FormattedTextControl(header_fragments), height=len(logo_lines[:6]) + 4),
                text_area,
                delay_area,
                Window(FormattedTextControl(menu_fragments), height=8),
            ]
        ),
        title="Iris Task Launcher",
    )
    style = Style.from_dict(
        {
            "frame.border": "fg:#60a5fa",
            "frame.label": "fg:#60a5fa bold",
            "logo": "fg:#60a5fa bold",
            "title": "fg:#bfdbfe bold",
            "hint": "fg:#94a3b8",
            "menu-title": "fg:#fbbf24 bold",
            "action": "fg:#dbeafe",
            "muted": "fg:#94a3b8",
            "selected": "bg:#2563eb fg:#ffffff bold",
            "status": "fg:#fbbf24 bold",
        }
    )
    app = Application(
        layout=Layout(root, focused_element=text_area),
        key_bindings=key_bindings,
        full_screen=True,
        style=style,
    )
    return app.run()


def prompt_for_task(logo_text: str = "") -> Optional[TaskPromptResult]:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return _fallback_prompt()

    try:
        return _run_prompt_toolkit_editor(logo_text)
    except ImportError:
        return _fallback_prompt()
