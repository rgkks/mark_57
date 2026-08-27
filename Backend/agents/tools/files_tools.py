#!/usr/bin/env python3
"""File tools for JARVIS."""

from __future__ import annotations

import datetime
import os
import shutil


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _resolve(path: str) -> str:
    """Resolve path, handling ~ and relative paths."""
    return os.path.abspath(os.path.expanduser(path))


def _perm(path: str) -> bool:
    """Check if path is readable."""
    return os.access(path, os.R_OK)


def list_dir(path: str = ".") -> dict:
    ...

def search_files(pattern: str, root: str = None, max_results: int = 50) -> dict:
    ...

def folder_size(path: str) -> dict:
    ...


def organize_directory(path: str) -> dict:
    try:
        p = _resolve(path)
        if not os.path.isdir(p):
            return {"ok": False, "error": f"Not a directory: {path}"}
        organized = {}
        for f in os.listdir(p):
            if os.path.isfile(os.path.join(p, f)):
                ext = os.path.splitext(f)[1]
                ext_key = ext[1:] if ext else "no_ext"
                organized.setdefault(ext_key, []).append(f)
        for ext, files in organized.items():
            ext_dir = os.path.join(p, ext)
            os.makedirs(ext_dir, exist_ok=True)
            for f in files:
                src = os.path.join(p, f)
                dst = os.path.join(ext_dir, f)
                try:
                    shutil.move(src, dst)
                except OSError:
                    pass
        return {"ok": True, "path": p, "organized": len(organized)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def backup_directory(path: str) -> dict:
    try:
        p = _resolve(path)
        if not os.path.isdir(p):
            return {"ok": False, "error": f"Not a directory: {path}"}
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{ts}"
        backup_path = os.path.join(os.path.dirname(p), backup_name)
        shutil.copytree(p, backup_path)
        return {"ok": True, "path": path, "backup": backup_path}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def copy_file(src: str, dst: str) -> dict:
    try:
        shutil.copy2(src, dst)
        return {"ok": True, "src": src, "dst": dst}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def move_file(src: str, dst: str) -> dict:
    try:
        shutil.move(src, dst)
        return {"ok": True, "src": src, "dst": dst}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def delete_file(path: str) -> dict:
    """Delete a file."""
    try:
        os.remove(path)
        return {"ok": True, "path": path}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def delete(path: str, confirm: bool = False) -> dict:
    """Delete a file with optional confirmation."""
    if confirm:
        # In a real app, would ask for confirmation
        # For now, just delete
        pass
    try:
        os.remove(path)
        return {"ok": True, "path": path}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def write_file(path: str, content: str, confirmed: bool = False) -> dict:
    """Write content to a file with confirmation."""
    if confirmed:
        try:
            with open(path, "w") as f:
                f.write(content)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    else:
        return {"ok": False}

def copy(src: str, dst: str, confirmed: bool = False) -> dict:
    """Copy a file with confirmation."""
    if confirmed:
        try:
            shutil.copy2(src, dst)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    else:
        return {"ok": False}

def delete(path: str, confirm: bool = False) -> dict:
    """Delete a file with confirmation."""
    if confirm:
        try:
            os.remove(path)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    else:
        return {"ok": False}

def read_file(path: str) -> dict:
    """Read a file and return its content."""
    try:
        with open(path, "r") as f:
            content = f.read()
        return {"ok": True, "content": content}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def metadata(path: str) -> dict:
    """Get file metadata."""
    try:
        st = os.path.getsize(path)
        return {"ok": True, "size": st}
    except Exception as e:
        return {"ok": False, "error": str(e)}
