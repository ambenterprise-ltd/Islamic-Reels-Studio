"""
Cross-platform stub for winreg.
On Windows, provides access to the native Windows registry.
On Linux/macOS, provides safe dummy stubs that raise FileNotFoundError / return safely.
"""
import sys
import os

HKEY_CURRENT_USER = 1
HKEY_LOCAL_MACHINE = 2
KEY_ALL_ACCESS = 0xF003F
KEY_READ = 0x20019
REG_SZ = 1

if sys.platform == "win32":
    try:
        # Bypass local directory shadowing to load Python's built-in C winreg module
        import importlib
        _orig_path = list(sys.path)
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path = [p for p in sys.path if os.path.abspath(p or ".") != cur_dir]
        import winreg as _builtin_winreg
        sys.path = _orig_path
        # Expose all built-in symbols
        for _name in dir(_builtin_winreg):
            if not _name.startswith("__"):
                globals()[_name] = getattr(_builtin_winreg, _name)
    except Exception:
        pass

def OpenKey(*args, **kwargs):
    if sys.platform == "win32" and "_builtin_winreg" in globals():
        return _builtin_winreg.OpenKey(*args, **kwargs)
    raise FileNotFoundError("Windows Registry is not present on non-Windows platforms.")

def QueryValueEx(*args, **kwargs):
    if sys.platform == "win32" and "_builtin_winreg" in globals():
        return _builtin_winreg.QueryValueEx(*args, **kwargs)
    raise FileNotFoundError("Windows Registry is not present on non-Windows platforms.")

def SetValueEx(*args, **kwargs):
    if sys.platform == "win32" and "_builtin_winreg" in globals():
        return _builtin_winreg.SetValueEx(*args, **kwargs)
    pass

def DeleteValue(*args, **kwargs):
    if sys.platform == "win32" and "_builtin_winreg" in globals():
        return _builtin_winreg.DeleteValue(*args, **kwargs)
    pass

def CloseKey(*args, **kwargs):
    if sys.platform == "win32" and "_builtin_winreg" in globals():
        return _builtin_winreg.CloseKey(*args, **kwargs)
    pass