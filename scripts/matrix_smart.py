#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Matrix Smart Router für Zabbix
# Liest Token & Räume aus /etc/zabbix/secret.d/matrix.ini
# Routing: 1) Trigger-Tag route=XYZ (aus {EVENT.TAGS})
#          2) Fallback per Subject-Matching
# Aufruf (Zabbix): matrix_smart.py <to> <tags> <subject> <message>
# Rückwärtskompatibel: matrix_smart.py <to> <subject> <message>

import sys, json, urllib.request, urllib.error, configparser, html, re
from datetime import datetime

INI_PATH = '/etc/zabbix/secret.d/matrix.ini'

# ---- Konfiguration laden ----
cfg = configparser.ConfigParser()
if not cfg.read(INI_PATH):
    print(f"ERROR: Cannot read {INI_PATH}")
    sys.exit(2)

MATRIX_SERVER = cfg['server']['MATRIX_SERVER'].rstrip('/')
MATRIX_TOKEN  = cfg['server']['MATRIX_TOKEN']

# Raum-Mapping: Keys konsequent lowercase
ROOM_MAPPING = {k.strip().lower(): v.strip() for k, v in cfg['rooms'].items()}

def _room(key_lc: str) -> str:
    """Sichere Auswahl inkl. Fallback auf 'default'."""
    return ROOM_MAPPING.get(key_lc, ROOM_MAPPING.get('default', ''))

# ---- Tag-Routing ----
ROUTE_TAG_RE = re.compile(r'\broute\s*[:=\s]\s*([A-Za-z0-9_]+)', re.I)
def pick_by_tag(tags_str: str) -> str:
    if not tags_str:
        return ""
    m = ROUTE_TAG_RE.search(tags_str)
    if not m:
        return ""
    key = m.group(1).lower()
    return _room(key)

# ---- Fallback: Subject-basierte Regeln ----
def determine_room(tags_str: str, subject: str, message: str) -> str:
    # 0) Tag hat Priorität
    r = pick_by_tag(tags_str)
    if r:
        return r

    s = (subject or "").lower()

    # Verfügbarkeit / Agent down
    if "zabbix agent is not available" in s or "unreachable" in s or "kein netzwerk" in s:
        return _room("pc_down")

    # Fehlgeschlagene Logins (vor Login-Erfolg prüfen!)
    if ("ssh failed login" in s or "failed login attempt" in s or
        "failed password" in s or "authentication failure" in s):
        return _room("login_failures")

    # fail2ban Aktion (Ban/Unban)
    if "fail2ban action" in s or re.search(r'\bban\b|\bunban\b', s):
        return _room("login_failures")

    # Login / Logout / Sessions geöffnet/geschlossen
    if ("ssh login" in s or "accepted password" in s or "session opened" in s):
        return _room("login_events")
    if ("ssh logout" in s or "session closed" in s):
        return _room("login_events")

    # Lange Sessions
    if "user logged in over" in s or "user zu lange eingeloggt" in s:
        return _room("long_sessions")

    # Disk Space (/ und /boot)
    if ("space is low" in s or "space is critically low" in s or
        "filesystem has become read-only" in s or "free inodes" in s or
        s.startswith("mounted filesystem discovery: linux: fs") or
        s.startswith("linux: fs ")):
        return _room("disk_space")

    # CPU/RAM/Swap/Proc-Limit/Load
    if ("cpu utilization" in s or "cpu-überlastung" in s or
        "high memory utilization" in s or "lack of available memory" in s or
        "high swap space" in s or "getting closer to process limit" in s or
        "load average is too high" in s):
        return _room("resource_usage")

    # Netzwerk
    if ("interface" in s and ("bandwidth" in s or "error rate" in s or
        "link down" in s or "has changed to lower speed" in s)):
        return _room("network_traffic")

    # Updates/Packages
    if ("package installed" in s or "package removed" in s or
        "system update performed" in s or
        "number of installed packages has been changed" in s or
        "updates installation" in s):
        return _room("updates")

    # File Integrity
    if ("file security" in s or "file integrity" in s or
        "/etc/passwd has been changed" in s):
        return _room("file_integrity")

    # Fallback
    return _room("default")

def send_matrix_message(tags: str, subject: str, message: str) -> bool:
    room_id = determine_room(tags, subject, message)
    if not room_id:
        print("ERROR: No room mapping (missing 'default' in INI?)")
        return False

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    body  = f"ZABBIX ALERT\n[{ts}]\nSUBJECT: {subject}\n\n{message}"
    fbody = (
        f"<h3>ZABBIX ALERT</h3>"
        f"<p><b>[{ts}]</b></p>"
        f"<p><b>SUBJECT:</b> {html.escape(subject)}</p>"
        f"<pre>{html.escape(message)}</pre>"
    )

    url = f"{MATRIX_SERVER}/_matrix/client/r0/rooms/{room_id}/send/m.room.message"
    data = json.dumps({
        "msgtype": "m.text",
        "body": body,
        "format": "org.matrix.custom.html",
        "formatted_body": fbody
    }).encode('utf-8')

    headers = {
        "Authorization": f"Bearer {MATRIX_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 300:
                print(f"ok route={room_id}")
                return True
            print(f"http_error status={resp.status} route={room_id}")
            return False
    except urllib.error.HTTPError as e:
        try:
            details = e.read().decode('utf-8')
        except Exception:
            details = str(e)
        print(f"HTTPError {e.code} route={room_id} resp={details}")
        return False
    except Exception as e:
        print(f"Error route={room_id} err={e}")
        return False

def main():
    # Kompatibel zu 3- oder 4-Param-Aufruf
    if len(sys.argv) >= 5:
        to, tags, subject, message = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    elif len(sys.argv) == 4:
        to, tags, subject, message = sys.argv[1], "", sys.argv[2], sys.argv[3]
    else:
        print("Usage: matrix_smart.py <to> <tags> <subject> <message>  OR  <to> <subject> <message>")
        sys.exit(2)

    ok = send_matrix_message(tags, subject, message)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
