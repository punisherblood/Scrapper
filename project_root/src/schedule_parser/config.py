# ===============================
# Base
# ===============================
BASE_URL = "https://nmknf.ru/html/"

# ===============================
# HTTP
# ===============================
HTTP_TIMEOUT = 10
HTTP_RETRIES = 2
HTTP_RETRY_DELAY = 1.5

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ScheduleParser/1.0)"
}

# ===============================
# Parsing window
# ===============================
DEFAULT_DAYS_AHEAD = 14

# ===============================
# Behaviour flags
# ===============================
LOG_SUSPICIOUS_CASES = True

# ===============================
# Logging
# ===============================
LOG_LEVEL = "INFO"
LOG_DIR = "logs"

LOG_FILES = {
    "main": "parser.log",
    "suspicious": "suspicious_cases.log",
    "http": "http_errors.log",
}

# ===============================
# Storage / export
# ===============================
EXPORT_DIR = "exports"

# ===============================
# Database
# ===============================
#DB_DSN = "sqlite:///schedule.db"
DB_DSN = "postgresql://schedule_app:1@localhost:5432/schedule_db"
