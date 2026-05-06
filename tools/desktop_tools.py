import os
import time

# --- Setup PyAutoGUI with Safety ---
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    # Add a tiny delay between actions to make them look more natural
    pyautogui.PAUSE = 0.5
except ImportError:
    pass # Handled gracefully in functions if missing

def get_screen_info() -> str:
    """Returns the screen resolution and current mouse coordinates."""
    try:
        width, height = pyautogui.size()
        x, y = pyautogui.position()
        return f"Screen Resolution: {width}x{height}. Current Mouse Position: (X: {x}, Y: {y})"
    except Exception as e:
        return f"Error getting screen info: {e}"

def mouse_move_and_click(x: int, y: int, button: str = "left", double_click: bool = False) -> str:
    """Moves the mouse to specific coordinates and clicks. button can be 'left' or 'right'."""
    try:
        x, y = int(x), int(y)
        pyautogui.moveTo(x, y, duration=0.5, tween=pyautogui.easeInOutQuad)
        if double_click:
            pyautogui.doubleClick(button=button)
            return f"Double-clicked {button} button at ({x}, {y})."
        else:
            pyautogui.click(button=button)
            return f"Clicked {button} button at ({x}, {y})."
    except pyautogui.FailSafeException:
        return "ERROR: Action aborted! User triggered PyAutoGUI corner failsafe."
    except Exception as e:
        return f"Error clicking mouse: {e}"

def keyboard_type(text: str, press_enter: bool = False) -> str:
    """Types a string of text. Optional: press Enter afterwards."""
    try:
        pyautogui.write(text, interval=0.05)
        if press_enter:
            pyautogui.press('enter')
            return f"Typed text and pressed Enter."
        return f"Typed text successfully."
    except pyautogui.FailSafeException:
        return "ERROR: Action aborted! User triggered PyAutoGUI corner failsafe."
    except Exception as e:
        return f"Error typing: {e}"

def keyboard_press(key: str) -> str:
    """Presses a specific keyboard key (e.g., 'enter', 'win', 'tab', 'up', 'down')."""
    try:
        pyautogui.press(key)
        return f"Pressed key '{key}'."
    except pyautogui.FailSafeException:
        return "ERROR: Action aborted! User triggered PyAutoGUI corner failsafe."
    except Exception as e:
        return f"Error pressing key: {e}"

def keyboard_hotkey(key1: str, key2: str = "", key3: str = "") -> str:
    """Presses a combination of keys (e.g., key1='ctrl', key2='c')."""
    try:
        keys = [k for k in [key1, key2, key3] if k]
        pyautogui.hotkey(*keys)
        return f"Pressed hotkey: {' + '.join(keys)}."
    except pyautogui.FailSafeException:
        return "ERROR: Action aborted! User triggered PyAutoGUI corner failsafe."
    except Exception as e:
        return f"Error pressing hotkey: {e}"

def analyze_screen(query: str) -> str:
    """
    Takes a live screenshot of the computer screen and uses Gemini 2.5 Flash to analyze it.
    Use this to 'see' what is on the screen, read text, or find approximate coordinates of elements.
    """
    try:
        from PIL import ImageGrab
        from google import genai
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "Error: GEMINI_API_KEY is not set in .env."
            
        # Take a screenshot
        screenshot = ImageGrab.grab()
        
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        You are Alfred, examining a screenshot of the user's computer screen.
        The screen resolution is {screenshot.width}x{screenshot.height}.
        The user asks: "{query}"
        
        If the user is asking for the location of something, try to provide approximate (X, Y) pixel coordinates based on the resolution.
        Be extremely concise and direct in your answer.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[screenshot, prompt]
        )
        
        return f"Screen Vision Analysis: {response.text}"
    except Exception as e:
        return f"Error analyzing screen: {e}"
