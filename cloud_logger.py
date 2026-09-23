import os
import sys
import json
import time
import random
import threading
from datetime import datetime, timezone, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials

# --- GLOBAL ENCODING FIX ---
if sys.platform.startswith('win'):
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        try: sys.stdout.reconfigure(encoding='utf-8')
        except Exception: pass
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        try: sys.stderr.reconfigure(encoding='utf-8')
        except Exception: pass
# ---------------------------

# Default headers matching specification
DEFAULT_HEADERS = [
    "Timestamp",
    "Date (Local)",
    "Time (Local)",
    "Surah / Ayah",
    "Topic",
    "Interval Since Last Post",
    "YouTube Video ID",
    "Status"
]

# Thread-safe in-memory cache to prevent 429 quota exhaustion
_CACHE_LOCK = threading.Lock()
_SPREADSHEET_CACHE = {}  # (sheet_key, creds_path) -> {"doc": doc, "client": client, "expires_at": float, "worksheets": {tab_title: ws}}
_LAST_POST_CACHE = {}    # (sheet_key, profile_name) -> {"last_post_time": dt, "checked_at": float}
CACHE_TTL = 300.0        # 5 minutes cache for worksheets

class PostElapsed(timedelta):
    """
    Subclass of timedelta that carries the original last_post_time attribute
    and supports tuple unpacking: (last_post_time, elapsed).
    """
    def __new__(cls, days=0, seconds=0, microseconds=0, milliseconds=0, minutes=0, hours=0, weeks=0, last_post_time=None):
        instance = super().__new__(cls, days, seconds, microseconds, milliseconds, minutes, hours, weeks)
        instance.last_post_time = last_post_time
        return instance

    def __iter__(self):
        yield self.last_post_time
        yield self


def retry_gspread(max_retries=4, initial_backoff=2.0, max_backoff=30.0):
    """Decorator to retry Google Sheets API calls with exponential backoff on 429 / transient errors."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            backoff = initial_backoff
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    err_msg = str(e).lower()
                    is_rate_limit = any(k in err_msg for k in ["429", "quota", "too many requests", "rate limit", "resource_exhausted"])
                    is_transient = any(k in err_msg for k in ["500", "503", "timed out", "connection", "socket", "reset"]) or is_rate_limit
                    if attempt == max_retries - 1 or not is_transient:
                        raise e
                    sleep_time = min(max_backoff, backoff + random.uniform(0.5, 1.5))
                    print(f"   > ⏳ [GSpread Notice] {e}. Backing off {sleep_time:.1f}s (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(sleep_time)
                    backoff *= 2
        return wrapper
    return decorator


def _parse_timestamp_str(ts_str):
    """Robust parser for ISO and standard date-time string formats."""
    if not ts_str:
        return None
    ts_str = str(ts_str).strip()
    try:
        clean_iso = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_iso)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:
        pass

    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S"
    ]:
        try:
            return datetime.strptime(ts_str, fmt)
        except Exception:
            pass
    return None


def get_sheets_secret_path(profile_name=None):
    """
    Resilient Google Sheets credentials resolver.
    Searches profile-specific paths, then falls back to Main Page backup,
    root credentials directory, and CWD.
    """
    candidates = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if profile_name:
        clean_prof = str(profile_name).strip()
        candidates.append(os.path.join("credentials", clean_prof, "sheets_secret.json"))
        candidates.append(os.path.join(base_dir, "credentials", clean_prof, "sheets_secret.json"))
    candidates.extend([
        os.path.join("credentials", "Main Page", "sheets_secret.json"),
        os.path.join(base_dir, "credentials", "Main Page", "sheets_secret.json"),
        os.path.join("credentials", "sheets_secret.json"),
        os.path.join(base_dir, "credentials", "sheets_secret.json"),
        "sheets_secret.json",
        os.path.join(base_dir, "sheets_secret.json")
    ])
    for path in candidates:
        if path and os.path.exists(path):
            return os.path.abspath(path)
    raise FileNotFoundError(f"Google Sheets secret JSON not found in candidates: {candidates}")


def get_gspread_client(creds_path=None, profile_name=None):
    """Authorizes and returns a gspread Client instance using service account JSON."""
    if not creds_path or not os.path.exists(creds_path):
        try:
            creds_path = get_sheets_secret_path(profile_name)
        except Exception as e:
            if not creds_path:
                raise e
            alt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), creds_path)
            if os.path.exists(alt_path):
                creds_path = alt_path
            else:
                raise e

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    try:
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    except Exception:
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scopes)
    return gspread.authorize(creds)


@retry_gspread(max_retries=4)
def _open_spreadsheet_safe(client, sheet_url_or_key):
    """Opens a spreadsheet by URL or by Key."""
    sheet_str = sheet_url_or_key.strip()
    if "docs.google.com" in sheet_str or sheet_str.startswith("http"):
        return client.open_by_url(sheet_str)
    return client.open_by_key(sheet_str)


def get_spreadsheet(sheet_url, creds_path=None, profile_name=None):
    """
    Returns a cached gspread Spreadsheet instance with thread-safe locking and TTL.
    """
    if not sheet_url or "YOUR_" in sheet_url:
        print("   > ❌ Sheets Error: The Google Sheet URL/Key is empty or invalid.")
        return None

    if not creds_path or not os.path.exists(creds_path):
        try:
            creds_path = get_sheets_secret_path(profile_name)
        except Exception:
            pass

    cache_key = (sheet_url.strip(), creds_path or 'default')
    now = time.time()

    with _CACHE_LOCK:
        cached = _SPREADSHEET_CACHE.get(cache_key)
        if cached and now < cached["expires_at"]:
            return cached["doc"]

    try:
        client = get_gspread_client(creds_path, profile_name=profile_name)
        doc = _open_spreadsheet_safe(client, sheet_url)
        with _CACHE_LOCK:
            _SPREADSHEET_CACHE[cache_key] = {
                "doc": doc,
                "client": client,
                "expires_at": now + CACHE_TTL,
                "worksheets": {}
            }
        return doc
    except Exception as e:
        print(f"   > ❌ Google Sheets Spreadsheet Open Error ({sheet_url}): {e}")
        return None


def get_or_create_profile_worksheet(sheet_url, profile_name, creds_path=None):
    """
    Specification 1: Dynamic Worksheet Management.
    Fetches existing tabs using `available_tabs = [ws.title for ws in spreadsheet.worksheets()]`.
    If a tab with the profile's exact name does not exist, creates it:
    `ws = spreadsheet.add_worksheet(title=profile_name, rows=500, cols=10)`.
    Adds default header columns if new or empty.
    """
    clean_profile = str(profile_name).strip() or "Main Page"
    if not creds_path or not os.path.exists(creds_path):
        try:
            creds_path = get_sheets_secret_path(clean_profile)
        except Exception:
            pass

    spreadsheet = get_spreadsheet(sheet_url, creds_path, profile_name=clean_profile)
    if not spreadsheet:
        return None

    cache_key = (sheet_url.strip(), creds_path or 'default')
    clean_profile = str(profile_name).strip() or "Main Page"

    with _CACHE_LOCK:
        cached_entry = _SPREADSHEET_CACHE.get(cache_key)
        if cached_entry and clean_profile in cached_entry.get("worksheets", {}):
            return cached_entry["worksheets"][clean_profile]

    @retry_gspread(max_retries=4)
    def _fetch_or_create():
        available_tabs = [ws.title for ws in spreadsheet.worksheets()]
        if clean_profile in available_tabs:
            ws = spreadsheet.worksheet(clean_profile)
        else:
            print(f"   > 📑 [SHEETS] Creating dedicated worksheet tab '{clean_profile}' in master Google Sheet...")
            ws = spreadsheet.add_worksheet(title=clean_profile, rows=500, cols=10)

        # Check headers and format if empty or missing
        try:
            first_row = ws.row_values(1)
            if not first_row or len(first_row) < 3 or first_row[0] != "Timestamp":
                ws.insert_row(DEFAULT_HEADERS, 1)
                try:
                    ws.format('A1:H1', {
                        "backgroundColor": {"red": 0.15, "green": 0.68, "blue": 0.38},
                        "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True},
                        "horizontalAlignment": "CENTER"
                    })
                except Exception:
                    pass
        except Exception as head_err:
            print(f"   > ⚠️ Header setup notice for [{clean_profile}]: {head_err}")

        return ws

    try:
        ws = _fetch_or_create()
        with _CACHE_LOCK:
            if cache_key in _SPREADSHEET_CACHE:
                _SPREADSHEET_CACHE[cache_key]["worksheets"][clean_profile] = ws
        return ws
    except Exception as e:
        print(f"   > ❌ Google Sheets Worksheet Access Error [{clean_profile}]: {e}")
        return None


def setup_headers(sheet):
    """Ensures standard headers exist on the given worksheet."""
    try:
        first_row = sheet.row_values(1)
        if not first_row or first_row[0] != "Timestamp":
            sheet.insert_row(DEFAULT_HEADERS, 1)
            try:
                sheet.format('A1:H1', {
                    "backgroundColor": {"red": 0.15, "green": 0.68, "blue": 0.38},
                    "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True},
                    "horizontalAlignment": "CENTER"
                })
            except Exception: pass
    except Exception:
        pass


def get_last_post_timestamp(profile_name, sheet_url=None, creds_path=None):
    """
    Specification 2: Interval Calculation & Verification.
    - Reads the last populated data row in that profile's worksheet.
    - Parses the ISO or '%Y-%m-%d %H:%M:%S' string from the 'Timestamp' column.
    - Returns elapsed time: elapsed = datetime.now() - last_post_time (as PostElapsed).
    - If sheet is new/empty, returns None.
    - On API error, returns 'API_ERROR'.
    """
    clean_profile = str(profile_name).strip() or "Main Page"
    if not creds_path or not os.path.exists(creds_path):
        try:
            creds_path = get_sheets_secret_path(clean_profile)
        except Exception:
            pass

    if not sheet_url:
        sheet_url = "https://docs.google.com/spreadsheets/d/1Q5E6w4PkKR6vS__Fd8Go6rHBIG0nsKdeuly6lHTPVGE/edit?gid=0#gid=0"

    cache_key = (sheet_url.strip(), clean_profile)
    now_ts = time.time()
    now_dt = datetime.now()

    # In-memory rate-limit cache (60-second validity)
    with _CACHE_LOCK:
        cached = _LAST_POST_CACHE.get(cache_key)
        if cached and (now_ts - cached["checked_at"] < 60):
            cached_dt = cached.get("last_post_time")
            if cached_dt:
                if cached_dt > now_dt:
                    cached_dt = now_dt
                    elapsed = timedelta(0)
                else:
                    elapsed = now_dt - cached_dt
                return PostElapsed(days=elapsed.days, seconds=elapsed.seconds, microseconds=elapsed.microseconds, last_post_time=cached_dt)
            return None

    try:
        ws = get_or_create_profile_worksheet(sheet_url, clean_profile, creds_path=creds_path)
        if not ws:
            return "API_ERROR"

        @retry_gspread(max_retries=3)
        def _get_rows(w):
            return w.get_all_values()

        rows = _get_rows(ws)
        if not rows or len(rows) <= 1:
            with _CACHE_LOCK:
                _LAST_POST_CACHE[cache_key] = {"last_post_time": None, "checked_at": now_ts}
            return None

        headers = rows[0]
        ts_col = 0
        for idx, h in enumerate(headers):
            h_low = str(h).lower()
            if "timestamp" in h_low or "raw_iso" in h_low or "iso" in h_low:
                ts_col = idx
                break

        for row in reversed(rows[1:]):
            if len(row) > ts_col and row[ts_col].strip():
                parsed_dt = _parse_timestamp_str(row[ts_col].strip())
                if parsed_dt:
                    if parsed_dt > now_dt:
                        parsed_dt = now_dt
                        elapsed = timedelta(0)
                    else:
                        elapsed = now_dt - parsed_dt
                    with _CACHE_LOCK:
                        _LAST_POST_CACHE[cache_key] = {"last_post_time": parsed_dt, "checked_at": now_ts}
                    return PostElapsed(days=elapsed.days, seconds=elapsed.seconds, microseconds=elapsed.microseconds, last_post_time=parsed_dt)

        with _CACHE_LOCK:
            _LAST_POST_CACHE[cache_key] = {"last_post_time": None, "checked_at": now_ts}
        return None

    except Exception as e:
        print(f"   > ❌ Sheets Read Error for [{clean_profile}]: {e}")
        return "API_ERROR"


def get_last_post_time(sheet_url, profile_name="Main Page", creds_path=None, **kwargs):
    """
    Backward-compatible wrapper returning the last post datetime object directly,
    or None if empty, or 'API_ERROR' on failure.
    """
    # Handle older signature where post_type was 2nd positional argument
    if isinstance(profile_name, str) and profile_name.startswith("http"):
        sheet_url = profile_name
        profile_name = kwargs.get("profile_name", "Main Page")

    res = get_last_post_timestamp(profile_name, sheet_url=sheet_url, creds_path=creds_path)
    if res == "API_ERROR":
        return "API_ERROR"
    if res is None:
        return None
    return getattr(res, "last_post_time", None)


def log_post(sheet_url, profile_name, verse_target="Quran Recitation", topic_target="Islamic Reel",
             youtube_video_id="", status="Success", creds_path=None, **kwargs):
    """
    Specification 3: Automated Post Record Logging.
    Appends a row to that profile's worksheet:
    [
        datetime.now().isoformat(),
        datetime.now().strftime("%Y-%m-%d"),
        datetime.now().strftime("%I:%M %p"),
        verse_target,
        topic_target,
        f"{elapsed_minutes} mins",
        youtube_video_id,
        "Success"
    ]
    Using worksheet.append_row(row_data, value_input_option="USER_ENTERED").
    """
    # Backward compatibility with older signature: log_post(personal_sheet_url, master_sheet_url, reference, post_type, creds_path)
    if isinstance(profile_name, str) and profile_name.startswith("http"):
        master_url = profile_name
        ref = verse_target
        p_name = kwargs.get("profile_name", "Main Page")
        verse_target = ref
        topic_target = kwargs.get("topic_target") or kwargs.get("post_type") or "Quran Reel"
        profile_name = p_name

    clean_profile = str(profile_name).strip() or "Main Page"
    if not creds_path or not os.path.exists(creds_path):
        try:
            creds_path = get_sheets_secret_path(clean_profile)
        except Exception:
            pass

    ws = get_or_create_profile_worksheet(sheet_url, clean_profile, creds_path=creds_path)
    if not ws:
        print(f"   > ❌ Sheets Error: Could not access worksheet tab for profile '{clean_profile}'.")
        return False

    now = datetime.now()

    # Calculate interval since last post
    elapsed_minutes = 0
    try:
        last_info = get_last_post_timestamp(clean_profile, sheet_url=sheet_url, creds_path=creds_path)
        if last_info and last_info != "API_ERROR":
            last_dt = getattr(last_info, "last_post_time", None)
            if last_dt:
                if last_dt > now:
                    last_dt = now
                elapsed_minutes = max(0, int((now - last_dt).total_seconds() / 60))
    except Exception:
        pass

    row_data = [
        now.isoformat(),
        now.strftime("%Y-%m-%d"),
        now.strftime("%I:%M %p"),
        str(verse_target or "Quran Recitation"),
        str(topic_target or "Islamic Reel"),
        f"{elapsed_minutes} mins",
        str(youtube_video_id or ""),
        str(status or "Success")
    ]

    @retry_gspread(max_retries=4)
    def _append(target_ws, data):
        return target_ws.append_row(data, value_input_option="USER_ENTERED")

    try:
        _append(ws, row_data)
        # Update cache immediately with the new timestamp
        cache_key = (sheet_url.strip(), clean_profile)
        with _CACHE_LOCK:
            _LAST_POST_CACHE[cache_key] = {"last_post_time": now, "checked_at": time.time()}

        print(f"   > ☁️ [SHEETS] Logged post to tab '{clean_profile}': {verse_target} (Interval: {elapsed_minutes} mins, YT: {youtube_video_id or 'N/A'})")
        return True
    except Exception as e:
        print(f"   > ❌ Personal Sheets Write Error [{clean_profile}]: {e}")
        return False


def get_sheet(sheet_url, creds_path=None):
    """Backward-compatible helper returning sheet1 of the spreadsheet."""
    if not creds_path or not os.path.exists(creds_path):
        try:
            creds_path = get_sheets_secret_path("Main Page")
        except Exception:
            pass
    doc = get_spreadsheet(sheet_url, creds_path)
    if doc:
        return doc.sheet1
    return None


@retry_gspread(max_retries=3)
def push_settings_to_cloud(sheet_url, settings_dict, creds_path=None):
    """Backs up entire settings configuration to a dedicated 'Agency_Profile' worksheet tab."""
    print("   > ☁️ Pushing Agency Profile to Google Sheets...")
    if not creds_path or not os.path.exists(creds_path):
        try:
            creds_path = get_sheets_secret_path("Main Page")
        except Exception:
            pass
    spreadsheet = get_spreadsheet(sheet_url, creds_path)
    if not spreadsheet:
        return False
    try:
        available_tabs = [ws.title for ws in spreadsheet.worksheets()]
        if "Agency_Profile" in available_tabs:
            sheet = spreadsheet.worksheet("Agency_Profile")
        else:
            sheet = spreadsheet.add_worksheet(title="Agency_Profile", rows="100", cols="5")

        sheet.clear()
        header = [["⚙️ Setting Name", "📊 Current Value"]]
        sheet.update('A1:B1', header)
        sheet.format('A1:B1', {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.8, 'green': 0.9, 'blue': 1.0}})

        rows = []
        for key, value in settings_dict.items():
            rows.append([str(key), str(value)])
        sheet.update('A2', rows)

        sheet.update_acell('E1', 'DO_NOT_EDIT_RAW_JSON')
        sheet.update_acell('E2', json.dumps(settings_dict))
        print("   > ✅ Settings successfully backed up to the cloud!")
        return True
    except Exception as e:
        print(f"   > ❌ Cloud Sync Error: {e}")
        return False


@retry_gspread(max_retries=3)
def pull_settings_from_cloud(sheet_url, creds_path=None):
    """Restores entire settings configuration from the 'Agency_Profile' worksheet tab."""
    print("   > ☁️ Pulling Agency Profile from Google Sheets...")
    if not creds_path or not os.path.exists(creds_path):
        try:
            creds_path = get_sheets_secret_path("Main Page")
        except Exception:
            pass
    spreadsheet = get_spreadsheet(sheet_url, creds_path)
    if not spreadsheet:
        return None
    try:
        sheet = spreadsheet.worksheet("Agency_Profile")
        raw_json = sheet.acell('E2').value
        if raw_json:
            settings_dict = json.loads(raw_json)
            print("   > ✅ Settings successfully restored from the cloud!")
            return settings_dict
        return None
    except Exception as e:
        print(f"   > ❌ Cloud Restore Error: {e}")
        return None


@retry_gspread(max_retries=3)
def sync_lf_timestamp(sheet_url, timestamp_str, creds_path=None):
    """Syncs long-form timestamp to 'Long-Form Logs' worksheet tab."""
    print("   > ☁️ Syncing Long-Form timestamp to Google Sheets...")
    if not creds_path or not os.path.exists(creds_path):
        try:
            creds_path = get_sheets_secret_path("Main Page")
        except Exception:
            pass
    spreadsheet = get_spreadsheet(sheet_url, creds_path)
    if not spreadsheet:
        return False
    try:
        available_tabs = [ws.title for ws in spreadsheet.worksheets()]
        if "Long-Form Logs" in available_tabs:
            sheet = spreadsheet.worksheet("Long-Form Logs")
        else:
            sheet = spreadsheet.add_worksheet(title="Long-Form Logs", rows="100", cols="5")

        sheet.update_acell('A1', timestamp_str)
        print("   > ✅ Long-Form timestamp synced to 'Long-Form Logs!A1'")
        return True
    except Exception as e:
        print(f"   > ❌ Long-Form Timestamp Sync Error: {e}")
        return False
