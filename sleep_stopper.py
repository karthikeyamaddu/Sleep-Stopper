import sys
import time
from datetime import datetime

# Windows API for power management & input simulation
if sys.platform == "win32":
    import ctypes

    # Execution State Flags (kernel32.SetThreadExecutionState)
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002
    
    # Virtual Key code for F15 (safest key: resets idle timers, never types text)
    VK_F15 = 0x7E
    KEYEVENTF_KEYUP = 0x0002


try:
    import pyautogui
    pyautogui.FAILSAFE = True
except ImportError:
    pyautogui = None


def set_windows_awake_state(enable: bool = True):
    """
    Directly tells the Windows OS kernel to keep the system & display awake.
    This is the official Windows API used by media players and presentation apps.
    """
    if sys.platform == "win32":
        if enable:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def send_harmless_input():
    """
    Sends a harmless virtual F15 key event.
    This resets Windows GetLastInputInfo() so communication apps (Teams, Slack, etc.)
    and corporate idle monitors stay in 'Active' state without typing anything.
    """
    if sys.platform == "win32":
        ctypes.windll.user32.keybd_event(VK_F15, 0, 0, 0)
        time.sleep(0.02)
        ctypes.windll.user32.keybd_event(VK_F15, 0, KEYEVENTF_KEYUP, 0)


def nudge_cursor():
    """
    Subtly moves the cursor by +2 pixels and immediately back.
    Ensures zero drift, no clicks, and no interference with active windows.
    """
    if pyautogui:
        try:
            current_x, current_y = pyautogui.position()
            pyautogui.moveRel(2, 0, duration=0.08)
            time.sleep(0.03)
            pyautogui.moveTo(current_x, current_y, duration=0.08)
        except Exception:
            pass


def get_interval() -> int:
    """Prompt for or parse the interval in seconds."""
    default_interval = 60
    if len(sys.argv) > 1:
        try:
            return max(2, int(sys.argv[1]))
        except ValueError:
            pass

    print("=" * 60)
    print("                 SLEEP STOPPER PRO                 ")
    print("=" * 60)
    print("Keeps your PC awake using native Windows Power API + cursor nudge.")
    print(f"Default interval is {default_interval} seconds.")
    user_input = input(f"Enter interval in seconds [Press Enter for {default_interval}s]: ").strip()
    
    if not user_input:
        return default_interval
    try:
        val = int(user_input)
        return max(2, val)
    except ValueError:
        print(f"[!] Invalid input. Using default: {default_interval}s.")
        return default_interval


def main():
    interval = get_interval()
    
    # 1. Inform Windows OS power manager to stay awake
    set_windows_awake_state(True)

    print("\n" + "-" * 60)
    print(f"[*] Native Windows Awake State : ACTIVE (Display & System lock disabled)")
    print(f"[*] Interval                   : Every {interval} second(s)")
    print(f"[*] Activity Simulation        : 2px cursor nudge + F15 key signal")
    print(f"[*] Status                     : Zero screen drift, no clicks")
    print(f"[*] Stop Command               : Press Ctrl+C in this terminal anytime")
    print("-" * 60 + "\n")

    try:
        while True:
            # Countdown display
            for remaining in range(interval, 0, -1):
                sys.stdout.write(f"\r[~] Next ping in: {remaining:3d}s  (Ctrl+C to stop)...")
                sys.stdout.flush()
                time.sleep(1)

            # Re-assert Windows stay-awake state + trigger activity
            set_windows_awake_state(True)
            send_harmless_input()
            nudge_cursor()

            timestamp = datetime.now().strftime("%H:%M:%S")
            sys.stdout.write(f"\r[+] [{timestamp}] Activity ping sent! Timer reset.                       \n")
            sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("[*] Stopping Sleep Stopper...")
    finally:
        # Restore standard Windows power settings
        set_windows_awake_state(False)
        print("[*] Windows power settings restored to normal.")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    if "--web" in sys.argv:
        from app import run_server
        run_server()
    else:
        main()
