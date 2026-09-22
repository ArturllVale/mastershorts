import os
import sys

def to_long_path(path: str) -> str:
    """Normalize path and prepend \\\\?\\ on Windows if not already present,
    allowing file operations to bypass the 260-character MAX_PATH limit."""
    if not path or not isinstance(path, str):
        return path
    if os.name != 'nt':
        return path
    
    # Already a Windows extended path
    if path.startswith('\\\\?\\') or path.startswith('//?/'):
        return path
        
    abs_path = os.path.abspath(path)
    # Check if network share UNC path
    if abs_path.startswith('\\\\'):
        return '\\\\?\\UNC\\' + abs_path[2:]
    return '\\\\?\\' + abs_path

def safe_exists(path: str) -> bool:
    try:
        return os.path.exists(to_long_path(path))
    except Exception:
        return False

def safe_getsize(path: str) -> int:
    try:
        return os.path.getsize(to_long_path(path))
    except Exception:
        return 0

def safe_getmtime(path: str) -> float:
    try:
        return os.path.getmtime(to_long_path(path))
    except Exception:
        return 0.0
