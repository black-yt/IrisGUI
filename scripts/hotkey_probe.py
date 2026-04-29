import argparse
import time

import pyautogui

from scripts.tools import ActionExecutor


METHODS = ("executor", "pyautogui_hotkey", "pyautogui_down_up", "pynput")


def parse_keys(raw):
    keys = [part.strip().lower() for part in raw.replace(",", "+").split("+")]
    return [key for key in keys if key]


def countdown(seconds):
    for remaining in range(seconds, 0, -1):
        print(f"Focus the target window now. Sending hotkey in {remaining}s...", flush=True)
        time.sleep(1)


def send_with_executor(keys):
    executor = ActionExecutor()
    return executor.execute({"action_type": "hotkey", "keys": keys})


def send_with_pyautogui_hotkey(keys, interval):
    pyautogui.hotkey(*keys, interval=interval)
    return f"pyautogui.hotkey({keys}) sent."


def send_with_pyautogui_down_up(keys, interval):
    if not keys:
        return "No keys to send."

    held = keys[:-1]
    target = keys[-1]
    pressed = []
    try:
        for key in held:
            pyautogui.keyDown(key)
            pressed.append(key)
            time.sleep(interval)
        pyautogui.press(target)
        time.sleep(interval)
    finally:
        for key in reversed(pressed):
            pyautogui.keyUp(key)
            time.sleep(interval)
    return f"pyautogui keyDown/press/keyUp({keys}) sent."


def send_with_pynput(keys, interval):
    from pynput.keyboard import Controller, Key

    key_map = {
        "alt": Key.alt,
        "ctrl": Key.ctrl,
        "control": Key.ctrl,
        "shift": Key.shift,
        "win": Key.cmd,
        "cmd": Key.cmd,
        "command": Key.cmd,
        "enter": Key.enter,
        "return": Key.enter,
        "esc": Key.esc,
        "escape": Key.esc,
        "tab": Key.tab,
        "space": Key.space,
        "backspace": Key.backspace,
        "delete": Key.delete,
        "left": Key.left,
        "right": Key.right,
        "up": Key.up,
        "down": Key.down,
        "home": Key.home,
        "end": Key.end,
    }

    controller = Controller()
    converted = [key_map.get(key, key) for key in keys]
    pressed = []
    try:
        for key in converted:
            controller.press(key)
            pressed.append(key)
            time.sleep(interval)
    finally:
        for key in reversed(pressed):
            controller.release(key)
            time.sleep(interval)
    return f"pynput press/release({keys}) sent."


def send_hotkey(method, keys, interval):
    if method == "executor":
        return send_with_executor(keys)
    if method == "pyautogui_hotkey":
        return send_with_pyautogui_hotkey(keys, interval)
    if method == "pyautogui_down_up":
        return send_with_pyautogui_down_up(keys, interval)
    if method == "pynput":
        return send_with_pynput(keys, interval)
    raise ValueError(f"Unknown method: {method}")


def main():
    parser = argparse.ArgumentParser(
        description="Manual GUI hotkey probe. Run this from the real desktop session, not WSL/headless."
    )
    parser.add_argument("--keys", default="ctrl+l", help="Hotkey to send, for example ctrl+l or ctrl+shift+l.")
    parser.add_argument(
        "--method",
        choices=METHODS + ("all",),
        default="executor",
        help="executor matches the Iris ActionExecutor path. Use all to compare backends.",
    )
    parser.add_argument("--countdown", type=int, default=5, help="Seconds to switch focus before the first send.")
    parser.add_argument("--interval", type=float, default=0.05, help="Delay between key events for manual methods.")
    parser.add_argument("--pause-between", type=float, default=3.0, help="Seconds between methods when --method all.")
    parser.add_argument(
        "--probe-text",
        default="",
        help="Optional text typed after the hotkey. For ctrl+l in a browser, this should appear in the address bar if the hotkey worked. It does not press Enter.",
    )
    args = parser.parse_args()

    keys = parse_keys(args.keys)
    if not keys:
        parser.error("--keys must contain at least one key")

    methods = list(METHODS) if args.method == "all" else [args.method]

    print("Hotkey probe")
    print(f"Keys: {keys}")
    print(f"Methods: {methods}")
    print("Open the target app first. For ctrl+l, a browser window is the clearest target.")
    if args.probe_text:
        print(f"Probe text will be typed after each hotkey without pressing Enter: {args.probe_text!r}")

    countdown(max(0, args.countdown))

    for index, method in enumerate(methods, start=1):
        print(f"\n[{index}/{len(methods)}] Sending with {method}...", flush=True)
        try:
            result = send_hotkey(method, keys, args.interval)
            print(result, flush=True)
            if args.probe_text:
                time.sleep(0.2)
                pyautogui.write(args.probe_text, interval=0.01)
                print("Probe text typed.", flush=True)
        except Exception as exc:
            print(f"ERROR from {method}: {exc}", flush=True)

        if index < len(methods):
            print(f"Next method in {args.pause_between}s. Restore target focus if needed.", flush=True)
            time.sleep(args.pause_between)


if __name__ == "__main__":
    main()
