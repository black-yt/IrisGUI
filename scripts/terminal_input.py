import sys
from dataclasses import dataclass
from typing import Optional


MENU_ACTIONS = ("newline", "start_now", "start_5s", "start_custom", "clear", "exit")
TASK_MENU_LABELS = {
    "newline": "New Line",
    "start_now": "Start Now",
    "start_5s": "Start After 5s",
    "start_custom": "Start After Custom Delay",
    "clear": "Clear",
    "exit": "Exit",
}
USER_INPUT_MENU_LABELS = {
    "newline": "New Line",
    "start_now": "Submit Now",
    "start_5s": "Submit After 5s",
    "start_custom": "Submit After Custom Delay",
    "clear": "Clear",
    "exit": "Cancel",
}


@dataclass(frozen=True)
class PromptEditorConfig:
    title: str
    header_title: str
    empty_message: str
    delay_prompt: str
    input_prompt: str = "> "
    logo_text: str = ""
    question: str = ""
    menu_labels: dict[str, str] = None
    menu_descriptions: dict[str, str] = None

    def labels(self):
        return self.menu_labels or TASK_MENU_LABELS

    def descriptions(self):
        return self.menu_descriptions or {
            "newline": "insert a blank line",
            "start_now": "run immediately",
            "start_5s": "prepare screen for five seconds",
            "start_custom": "use the delay field",
            "clear": "reset task text",
            "exit": "close launcher",
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


def _fallback_prompt(config: PromptEditorConfig) -> Optional[TaskPromptResult]:
    lines = []
    labels = config.labels()
    while True:
        print(config.header_title)
        if config.question:
            print(config.question)
        print("Submit an empty line to open the action menu.")
        while True:
            try:
                line = input(config.input_prompt)
            except EOFError:
                return None
            if line == "":
                break
            lines.append(line)

        text = "\n".join(lines)
        print(
            f"\n1. {labels['newline']}\n"
            f"2. {labels['start_now']}\n"
            f"3. {labels['start_5s']}\n"
            f"4. {labels['start_custom']}\n"
            f"5. {labels['clear']}\n"
            f"6. {labels['exit']}"
        )
        choice = input("Choose an action: ").strip()
        if choice == "1":
            lines.append("")
            continue
        if choice == "2":
            return TaskPromptResult(text, delay_seconds=0) if text.strip() else None
        if choice == "3":
            return TaskPromptResult(text, delay_seconds=5) if text.strip() else None
        if choice == "4":
            seconds = parse_delay_seconds(input(config.delay_prompt))
            if seconds is not None and text.strip():
                return TaskPromptResult(text, delay_seconds=seconds)
            print(f"Invalid delay or {config.empty_message.lower()}")
            continue
        if choice == "5":
            lines = []
            continue
        if choice == "6":
            return None


def _run_prompt_toolkit_editor(config: PromptEditorConfig) -> Optional[TaskPromptResult]:
    from prompt_toolkit.application import Application
    from prompt_toolkit.document import Document
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    from prompt_toolkit.widgets import Frame, TextArea

    state = MenuState()
    status = {"text": ""}
    menu_labels = config.labels()
    menu_descriptions = config.descriptions()

    logo_lines = [line for line in config.logo_text.strip().splitlines() if line.strip()]

    def header_fragments():
        fragments = []
        for line in logo_lines[:6]:
            fragments.append(("class:logo", f"{line}\n"))
        if logo_lines:
            fragments.append(("", "\n"))
        fragments.extend(
            [
                ("class:title", f"{config.header_title}\n"),
                ("class:hint", "Use Up/Down to choose an action, then press Enter.\n"),
                ("class:hint", "New Line is selected by default, so Enter normally inserts a line break."),
            ]
        )
        if config.question:
            fragments.extend(
                [
                    ("", "\n\n"),
                    ("class:menu-title", "Question\n"),
                    ("class:question", f"{config.question}\n"),
                ]
            )
        return fragments

    text_area = TextArea(
        text="",
        multiline=True,
        wrap_lines=True,
        prompt=config.input_prompt,
    )
    delay_area = TextArea(
        text="",
        multiline=False,
        height=1,
        prompt=config.delay_prompt,
    )

    def menu_fragments():
        fragments = []
        if status["text"]:
            fragments.extend([("class:status", status["text"]), ("", "\n")])
        fragments.append(("class:menu-title", "Actions\n"))
        for index, action in enumerate(MENU_ACTIONS):
            label_style = "class:selected" if index == state.selected_index else "class:action"
            desc_style = "class:selected" if index == state.selected_index else "class:muted"
            marker = ">" if index == state.selected_index else " "
            fragments.append((label_style, f" {marker} {menu_labels[action]:<28}"))
            fragments.append((desc_style, f"{menu_descriptions[action]}\n"))
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
                status["text"] = "Enter a non-negative number in the delay field."
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
            status["text"] = config.empty_message
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
                Window(
                    FormattedTextControl(header_fragments),
                    height=len(logo_lines[:6]) + (len(config.question.splitlines()) + 7 if config.question else 4),
                ),
                text_area,
                delay_area,
                Window(FormattedTextControl(menu_fragments), height=8),
            ]
        ),
        title=config.title,
    )
    style = Style.from_dict(
        {
            "frame.border": "fg:#60a5fa",
            "frame.label": "fg:#60a5fa bold",
            "logo": "fg:#60a5fa bold",
            "title": "fg:#bfdbfe bold",
            "hint": "fg:#94a3b8",
            "menu-title": "fg:#fbbf24 bold",
            "question": "fg:#dbeafe",
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
    config = PromptEditorConfig(
        title="Iris Task Launcher",
        header_title="Iris Task Launcher",
        empty_message="Task description is empty.",
        delay_prompt="Custom delay seconds > ",
        logo_text=logo_text,
    )
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return _fallback_prompt(config)

    try:
        return _run_prompt_toolkit_editor(config)
    except ImportError:
        return _fallback_prompt(config)


def prompt_for_user_input(question: str) -> Optional[TaskPromptResult]:
    config = PromptEditorConfig(
        title="Iris User Input",
        header_title="Iris Needs Your Input",
        empty_message="Response is empty.",
        delay_prompt="Custom submit delay seconds > ",
        question=question,
        menu_labels=USER_INPUT_MENU_LABELS,
        menu_descriptions={
            "newline": "insert a blank line",
            "start_now": "submit immediately",
            "start_5s": "submit after five seconds",
            "start_custom": "use the delay field",
            "clear": "reset response text",
            "exit": "cancel user input",
        },
    )
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return _fallback_prompt(config)

    try:
        return _run_prompt_toolkit_editor(config)
    except ImportError:
        return _fallback_prompt(config)
