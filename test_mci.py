import ctypes, os

def get_short_path_name(long_name):
    """
    Gets the short path name of a given long path.
    http://stackoverflow.com/a/23598461/200291
    """
    import ctypes
    from ctypes import wintypes
    _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
    _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    _GetShortPathNameW.restype = wintypes.DWORD
    
    output_buf_size = 0
    while True:
        output_buf = ctypes.create_unicode_buffer(output_buf_size)
        needed = _GetShortPathNameW(long_name, output_buf, output_buf_size)
        if output_buf_size >= needed:
            return output_buf.value
        else:
            output_buf_size = needed

mci = ctypes.windll.winmm.mciSendStringW
tmp = r'c:\VS Code\JARVIS\Alfred_Workspace\audio_cache\9efebe9052f789adb1f4fa21a20e5fe3\000.wav'

print("Attempting to open with original path...")
err = mci(f'open "{tmp}" type mpegvideo alias alfred_audio', None, 0, 0)
print(f"MCI open result (original): {err}")

if err != 0:
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.winmm.mciGetErrorStringW(err, buf, 256)
    print(f"Error meaning: {buf.value}")

short_tmp = get_short_path_name(tmp)
print(f"\nAttempting to open with short path: {short_tmp}")
err = mci(f'open "{short_tmp}" type mpegvideo alias alfred_audio', None, 0, 0)
print(f"MCI open result (short path): {err}")

if err != 0:
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.winmm.mciGetErrorStringW(err, buf, 256)
    print(f"Error meaning: {buf.value}")
