import os
import shutil
import subprocess
from pathlib import Path

# --- Setup Sandboxes ---
USER_HOME = Path.home()
ALLOWED_DIRECTORIES = [
    (USER_HOME / "Downloads").resolve(),
    (USER_HOME / "Documents").resolve(),
    Path(os.path.join(os.path.dirname(__file__), "..", "Alfred_Workspace")).resolve()
]

def _is_safe_path(target_path: str) -> bool:
    """
    Ensures that the requested file path lies within an allowed directory.
    Prevents path traversal attacks (e.g. '../../Windows/System32')
    """
    try:
        req_path = Path(target_path).resolve()
        for safe_dir in ALLOWED_DIRECTORIES:
            # Check if req_path is a subdirectory or file within safe_dir
            if req_path.is_relative_to(safe_dir):
                return True
        return False
    except Exception:
        return False

# --- File Operations ---

def create_file(filepath: str, content: str = "") -> str:
    """Creates a new file with the specified text content."""
    if not _is_safe_path(filepath):
        return f"Error: Access denied. I am only permitted to operate within Downloads, Documents, and Alfred_Workspace."
    
    try:
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully created file: {filepath}"
    except Exception as e:
        return f"Error creating file: {e}"

def delete_file(filepath: str) -> str:
    """Deletes a file or completely empty directory."""
    if not _is_safe_path(filepath):
        return f"Error: Access denied. Cannot delete outside of sandbox directories."
    
    try:
        path = Path(filepath)
        if not path.exists():
            return f"Error: '{filepath}' does not exist."
            
        if path.is_file():
            path.unlink()
            return f"Successfully deleted file: {filepath}"
        elif path.is_dir():
            # Only allow deleting empty directories for safety
            path.rmdir()
            return f"Successfully deleted empty directory: {filepath}"
    except Exception as e:
        return f"Error deleting: {e}"

def rename_file(old_filepath: str, new_filepath: str) -> str:
    """Renames a file in-place."""
    if not _is_safe_path(old_filepath) or not _is_safe_path(new_filepath):
        return f"Error: Access denied. Both source and destination must be inside the sandbox."
        
    try:
        os.rename(old_filepath, new_filepath)
        return f"Successfully renamed '{old_filepath}' to '{new_filepath}'."
    except Exception as e:
        return f"Error renaming file: {e}"

def move_file(source_filepath: str, dest_directory: str) -> str:
    """Moves a file to a new directory."""
    if not _is_safe_path(source_filepath) or not _is_safe_path(dest_directory):
        return f"Error: Access denied. Paths must be in the sandbox."
        
    try:
        os.makedirs(dest_directory, exist_ok=True)
        shutil.move(source_filepath, dest_directory)
        return f"Successfully moved file to '{dest_directory}'."
    except Exception as e:
        return f"Error moving file: {e}"


# =============================================
# DEEP OS CONTROL TOOLS (Hardened)
# =============================================

def get_battery_status() -> str:
    """Returns current battery percentage, charging status, and estimated time remaining."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return "No battery detected. This may be a desktop PC."
        percent = battery.percent
        plugged = "charging" if battery.power_plugged else "on battery"
        if battery.secsleft == psutil.POWER_TIME_UNLIMITED:
            time_info = "fully charged"
        elif battery.secsleft == psutil.POWER_TIME_UNKNOWN:
            time_info = "time remaining unknown"
        else:
            hours = battery.secsleft // 3600
            minutes = (battery.secsleft % 3600) // 60
            time_info = f"about {hours} hours {minutes} minutes remaining"
        return f"Battery is at {percent}%, {plugged}, {time_info}."
    except Exception as e:
        return f"Error reading battery: {e}"

def set_brightness(level: int) -> str:
    """Sets screen brightness to a value between 0 and 100. Verifies the change."""
    try:
        level = max(0, min(100, int(level)))
        
        # Primary method: WMI
        cmd = f'(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})'
        result = subprocess.run(
            ['powershell', '-Command', cmd],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode != 0:
            # Fallback: PowerShell direct method
            fallback_cmd = f'powershell -Command "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"'
            subprocess.run(
                fallback_cmd, shell=True, capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        
        # Verify the change
        verify = get_brightness()
        return f"Screen brightness set to {level}%. {verify}"
    except subprocess.TimeoutExpired:
        return f"Brightness command timed out. The change may still have been applied."
    except Exception as e:
        return f"Error setting brightness: {e}"

def get_brightness() -> str:
    """Gets the current screen brightness level."""
    try:
        cmd = '(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness'
        result = subprocess.run(
            ['powershell', '-Command', cmd],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        brightness = result.stdout.strip()
        if brightness.isdigit():
            return f"Current screen brightness is {brightness}%."
        return f"Could not read brightness level (raw output: {brightness})."
    except subprocess.TimeoutExpired:
        return "Brightness read timed out."
    except Exception as e:
        return f"Error reading brightness: {e}"

def toggle_wifi(action: str) -> str:
    """Enables or disables WiFi. action: 'enable' or 'disable'."""
    try:
        cmd_action = 'disabled' if action.lower().strip() in ('disable', 'off', 'turn off') else 'enabled'
        
        # Try common Wi-Fi interface names
        interface_names = ['Wi-Fi', 'WiFi', 'Wireless Network Connection', 'WLAN']
        
        for iface in interface_names:
            result = subprocess.run(
                ['netsh', 'interface', 'set', 'interface', iface, cmd_action],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return f"WiFi has been {cmd_action} (interface: {iface})."
        
        # If none worked, try with the first one and report error
        error_output = result.stderr.strip() if result else "Unknown error"
        return f"WiFi toggle attempted but may have failed. Make sure your WiFi adapter is named one of: {', '.join(interface_names)}. Error: {error_output}"
    except subprocess.TimeoutExpired:
        return "WiFi toggle timed out."
    except Exception as e:
        return f"Error toggling WiFi: {e}"

def toggle_bluetooth(action: str) -> str:
    """Enables or disables Bluetooth. action: 'enable' or 'disable'."""
    try:
        state = 'Off' if action.lower().strip() in ('disable', 'off', 'turn off') else 'On'
        ps_script = f'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$radios = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync().GetAwaiter().GetResult()
$bt = $radios | Where-Object {{ $_.Kind -eq 'Bluetooth' }}
if ($bt) {{ $bt.SetStateAsync('{state}').GetAwaiter().GetResult() }}
'''
        result = subprocess.run(
            ['powershell', '-Command', ps_script],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        friendly_state = 'enabled' if state == 'On' else 'disabled'
        if result.returncode == 0:
            return f"Bluetooth has been {friendly_state}."
        else:
            return f"Bluetooth toggle attempted. It may require administrator privileges. {result.stderr.strip()[:100]}"
    except subprocess.TimeoutExpired:
        return "Bluetooth toggle timed out."
    except Exception as e:
        return f"Error toggling Bluetooth: {e}"

def lock_pc() -> str:
    """Locks the PC immediately."""
    try:
        import memory_engine
        memory_engine.log_system_event("INFO", "PC locked via Alfred command.")
        
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "PC is now locked."
    except Exception as e:
        return f"Error locking PC: {e}"

def sleep_pc() -> str:
    """Puts the PC to sleep."""
    try:
        import memory_engine
        memory_engine.log_system_event("INFO", "PC put to sleep via Alfred command.")
        
        subprocess.run(
            ['powershell', '-Command',
             'Add-Type -Assembly System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState("Suspend", $false, $false)'],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return "PC is going to sleep."
    except Exception as e:
        return f"Error putting PC to sleep: {e}"

def shutdown_pc(minutes: int = 0) -> str:
    """Shuts down the PC. Optionally delay by X minutes."""
    try:
        import memory_engine
        memory_engine.log_system_event("WARNING", f"PC shutdown initiated via Alfred (delay: {minutes} min).")
        
        seconds = int(minutes) * 60
        subprocess.run(
            ['shutdown', '/s', '/t', str(seconds)],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return f"PC will shut down in {minutes} minutes." if int(minutes) > 0 else "PC is shutting down now."
    except Exception as e:
        return f"Error initiating shutdown: {e}"

def cancel_shutdown() -> str:
    """Cancels a pending scheduled shutdown."""
    try:
        subprocess.run(
            ['shutdown', '/a'],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return "Shutdown has been cancelled."
    except Exception as e:
        return f"Error cancelling shutdown: {e}"

def set_volume(level: int) -> str:
    """Sets system volume to a value between 0 and 100 using pycaw for precise control."""
    try:
        level = max(0, min(100, int(level)))
        
        # Primary method: pycaw (precise, reliable)
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            
            # pycaw uses scalar (0.0 to 1.0)
            scalar = level / 100.0
            volume.SetMasterVolumeLevelScalar(scalar, None)
            
            # Verify
            actual = round(volume.GetMasterVolumeLevelScalar() * 100)
            return f"System volume set to {actual}%."
        except ImportError:
            pass  # Fall through to SendKeys method
        
        # Fallback: SendKeys method (less precise)
        ps_script = f'''
$obj = New-Object -ComObject WScript.Shell
$obj.SendKeys([char]173); Start-Sleep -Milliseconds 200; $obj.SendKeys([char]173); Start-Sleep -Milliseconds 200
for ($i = 0; $i -lt 50; $i++) {{ $obj.SendKeys([char]174) }}; Start-Sleep -Milliseconds 200
$steps = [math]::Round({level} / 2)
for ($i = 0; $i -lt $steps; $i++) {{ $obj.SendKeys([char]175) }}
'''
        subprocess.run(
            ['powershell', '-Command', ps_script],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return f"System volume set to approximately {level}% (SendKeys fallback)."
    except Exception as e:
        return f"Error setting volume: {e}"

def take_screenshot() -> str:
    """Takes a screenshot and saves it to Alfred_Workspace."""
    try:
        from datetime import datetime as dt
        workspace = Path(os.path.join(os.path.dirname(__file__), "..", "Alfred_Workspace")).resolve()
        os.makedirs(workspace, exist_ok=True)
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        filepath = workspace / f"screenshot_{timestamp}.png"
        
        # Primary method: PIL/Pillow (faster, more reliable)
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.save(str(filepath))
            if filepath.exists() and filepath.stat().st_size > 0:
                return f"Screenshot saved to {filepath}"
        except ImportError:
            pass  # Fall through to PowerShell method
        
        # Fallback: PowerShell
        ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing
$s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$b = New-Object System.Drawing.Bitmap($s.Width,$s.Height)
$g = [System.Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen($s.Location,[System.Drawing.Point]::Empty,$s.Size)
$b.Save("{filepath}"); $g.Dispose(); $b.Dispose()
'''
        subprocess.run(
            ['powershell', '-Command', ps_script],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Verify file was created
        if filepath.exists() and filepath.stat().st_size > 0:
            return f"Screenshot saved to {filepath}"
        return f"Screenshot command ran but the file was not created at {filepath}."
    except Exception as e:
        return f"Error taking screenshot: {e}"

def organize_workspace(directory: str) -> str:
    """
    Safely organizes a directory by moving files into categorized subfolders based on extension.
    SAFETY RULES:
    1. NEVER deletes files, only moves them.
    2. Completely ignores files created or modified within the last 24 hours.
    """
    import time
    from pathlib import Path
    import shutil
    
    # Categories
    CATEGORIES = {
        "Images": ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'],
        "Documents": ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.xls', '.xlsx', '.csv', '.ppt', '.pptx'],
        "Installers": ['.exe', '.msi', '.apk'],
        "Archives": ['.zip', '.rar', '.7z', '.tar', '.gz'],
        "Code": ['.py', '.js', '.ts', '.html', '.css', '.json', '.xml', '.cpp', '.c', '.h', '.java'],
        "Video": ['.mp4', '.mkv', '.avi', '.mov'],
        "Audio": ['.mp3', '.wav', '.flac', '.m4a']
    }
    
    if not _is_safe_path(directory):
        return f"Error: Access denied. Cannot organize outside of sandbox directories."
        
    try:
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return f"Error: '{directory}' is not a valid directory."
            
        now = time.time()
        DAY_IN_SECONDS = 24 * 60 * 60
        
        moved_count = 0
        skipped_count = 0
        
        for item in path.iterdir():
            if item.is_dir():
                continue
                
            # Smart Ignore: skip recently modified files (last 24 hours)
            if (now - item.stat().st_mtime) < DAY_IN_SECONDS:
                skipped_count += 1
                continue
                
            ext = item.suffix.lower()
            category_name = "Other"
            for cat, exts in CATEGORIES.items():
                if ext in exts:
                    category_name = cat
                    break
                    
            dest_folder = path / category_name
            dest_folder.mkdir(exist_ok=True)
            
            # Handle naming collisions
            dest_file = dest_folder / item.name
            counter = 1
            while dest_file.exists():
                dest_file = dest_folder / f"{item.stem}_{counter}{item.suffix}"
                counter += 1
                
            shutil.move(str(item), str(dest_file))
            moved_count += 1
            
        return f"Workspace organized successfully. Moved {moved_count} old files into categories. Skipped {skipped_count} recently modified files."
    except Exception as e:
        return f"Error organizing workspace: {e}"
