import os
import traceback
from datetime import datetime
from core.config import LOGS_DIR

ERROR_LOG_PATH = os.path.join(LOGS_DIR, "error.log")

def log_error(context: str, exc: Exception = None, details: str = None):
    os.makedirs(LOGS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [ERROR] [{context}]\n"
    if details:
        log_entry += f"Details: {details}\n"
    if exc:
        log_entry += f"Exception: {type(exc).__name__}: {str(exc)}\n"
        log_entry += traceback.format_exc() + "\n"
    log_entry += "-" * 60 + "\n"
    
    try:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Gagal menulis error log: {e}")
    print(log_entry)

def get_recent_logs(lines: int = 200) -> str:
    if not os.path.exists(ERROR_LOG_PATH):
        return "Belum ada catatan log error tersimpan."
    try:
        with open(ERROR_LOG_PATH, "r", encoding="utf-8") as f:
            content = f.readlines()
            return "".join(content[-lines:])
    except Exception as e:
        return f"Gagal membaca log: {e}"

def clear_logs() -> bool:
    if os.path.exists(ERROR_LOG_PATH):
        try:
            with open(ERROR_LOG_PATH, "w", encoding="utf-8") as f:
                f.write("")
            return True
        except Exception:
            return False
    return True
