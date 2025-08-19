#!/usr/bin/env python3
import json
import urllib.request
import ssl
import configparser
from datetime import datetime, timedelta
import html

# Konfigurationspfade
MATRIX_INI = '/etc/zabbix/secret.d/matrix.ini'
ZABBIX_API_INI = '/etc/zabbix/secret.d/zabbix_api.ini'

def load_config():
    """Konfiguration aus INI-Dateien laden"""
    # Matrix Konfiguration
    matrix_cfg = configparser.ConfigParser()
    matrix_cfg.read(MATRIX_INI)

    matrix_server = (matrix_cfg['server'].get('base_url') or
                    matrix_cfg['server'].get('MATRIX_SERVER')).rstrip('/')
    matrix_token = (matrix_cfg['server'].get('access_token') or
                   matrix_cfg['server'].get('MATRIX_TOKEN')).strip()
    weekly_room = matrix_cfg['rooms'].get('weekly_reports',
                                          matrix_cfg['rooms'].get('default'))

    # Zabbix API Konfiguration
    zabbix_cfg = configparser.ConfigParser()
    zabbix_cfg.read(ZABBIX_API_INI)

    zabbix_url = zabbix_cfg['zabbix'].get('url')
    zabbix_token = zabbix_cfg['zabbix'].get('token')
    verify_tls = zabbix_cfg['zabbix'].get('verify_tls', 'true').lower() == 'true'
    cafile = zabbix_cfg['zabbix'].get('cafile')

    return {
        'matrix_server': matrix_server,
        'matrix_token': matrix_token,
        'weekly_room': weekly_room,
        'zabbix_url': zabbix_url,
        'zabbix_token': zabbix_token,
        'verify_tls': verify_tls,
        'cafile': cafile
    }

def create_ssl_context(verify_tls, cafile):
    """SSL-Kontext für API-Aufrufe erstellen"""
    if verify_tls and cafile:
        ctx = ssl.create_default_context(cafile=cafile)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
    elif not verify_tls:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context()
    return ctx

def zabbix_api_call(config, method, params):
    """Zabbix API-Aufruf durchführen"""
    data = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "auth": config['zabbix_token'] if method != "apiinfo.version" else None,
        "id": 1
    }).encode('utf-8')

    req = urllib.request.Request(
        config['zabbix_url'],
        data=data,
        headers={"Content-Type": "application/json-rpc"}
    )

    ctx = create_ssl_context(config['verify_tls'], config['cafile'])

    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except Exception as e:
        print(f"[{datetime.now()}] API-Aufruf fehlgeschlagen: {e}")
        raise

def categorize_problem(name):
    """Problem basierend auf Name/Beschreibung kategorisieren"""
    name_lower = name.lower()

    categories = {
        'PC/Agent Issues': [
            'not available', 'unreachable', 'timeout', 'agent down',
            'connection lost', 'no data'
        ],
        'Login Events': [
            'ssh login:', 'accepted password', 'logout',
            'session opened', 'session closed', 'login:'
        ],
        'Login Failures': [
            'failed password', 'authentication failure', 'ssh login failed',
            'fail2ban found', 'invalid user', 'failed login'
        ],
        'Long Sessions': [
            'logged in over', 'long session', 'session duration'
        ],
        'Disk Space': [
            'space is low', 'free inodes', 'read-only', 'disk space',
            'filesystem', 'volume full'
        ],
        'Resource Usage': [
            'high cpu', 'memory utilization', 'swap', 'process limit',
            'load average', 'cpu load', 'ram usage'
        ],
        'Network': [
            'bandwidth', 'error rate', 'lower speed', 'interface',
            'link down', 'packet loss', 'network'
        ],
        'System Updates': [
            'package installed', 'package removed', 'package updated',
            'update available', 'patch'
        ],
        'File Integrity': [
            'file integrity', 'checksum', '/etc/passwd', 'file changed',
            'permission changed'
        ]
    }

    for category, keywords in categories.items():
        if any(kw in name_lower for kw in keywords):
            return category

    return 'Other/Uncategorized'

def get_weekly_stats(config):
    """Problemstatistiken für die vergangene Woche abrufen"""
    end_time = int(datetime.now().timestamp())
    start_time = int((datetime.now() - timedelta(days=7)).timestamp())

    # Zuerst versuchen ALLE aktuellen Events abzurufen (gelöste und ungelöste)
    try:
        response = zabbix_api_call(config, "event.get", {
            "output": ["eventid", "name", "severity", "clock", "value"],
            "time_from": start_time,
            "time_till": end_time,
            "selectHosts": ["host"],
            "selectTags": ["tag", "value"],
            "source": 0,  # 0 = Trigger Events
            "sortfield": ["clock"],
            "sortorder": "DESC",
            "limit": 1000
        })

        events = response.get('result', [])
    except Exception:
        events = []

    # Auch problem.get für aktuelle Probleme als Fallback versuchen
    if len(events) == 0:
        try:
            response = zabbix_api_call(config, "problem.get", {
                "output": "extend",
                "selectHosts": ["host"],
                "selectTags": ["tag", "value"],
                "recent": True  # Kürzlich gelöste Probleme einschließen
            })

            problems = response.get('result', [])
        except Exception:
            problems = []
    else:
        problems = []

    # Events verwenden wenn vorhanden, ansonsten Probleme
    data_to_process = events if len(events) > 0 else problems

    # Statistiken
    stats = {
        'total': len(data_to_process),
        'by_category': {},
        'by_severity': {
            '0': 0,  # Nicht klassifiziert
            '1': 0,  # Information
            '2': 0,  # Warnung
            '3': 0,  # Durchschnitt
            '4': 0,  # Hoch
            '5': 0   # Katastrophe
        },
        'by_host': {}
    }

    # Jedes Problem/Event verarbeiten
    for item in data_to_process:
        name = item.get('name', 'Unknown')

        # Kategorie
        category = categorize_problem(name)
        stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

        # Schweregrad
        severity = str(item.get('severity', '0'))
        if severity in stats['by_severity']:
            stats['by_severity'][severity] += 1

        # Host
        if item.get('hosts'):
            hostname = item['hosts'][0]['host']
            stats['by_host'][hostname] = stats['by_host'].get(hostname, 0) + 1

    return stats

def format_report(stats):
    """Wochenbericht formatieren"""
    now = datetime.now()
    week_start = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    week_end = now.strftime('%Y-%m-%d')

    # Klartext-Version
    plain = f"""ZABBIX WEEKLY REPORT
====================
Period: {week_start} to {week_end}
Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY
-------
Total Problems: {stats['total']}

BY CATEGORY
-----------"""

    # HTML-Version
    html_content = f"""<h2>ZABBIX WEEKLY REPORT</h2>
<p><strong>Period:</strong> {week_start} to {week_end}<br>
<strong>Generated:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')}</p>

<h3>SUMMARY</h3>
<p><strong>Total Problems:</strong> {stats['total']}</p>

<h3>BY CATEGORY</h3>
<pre>"""

    if stats['total'] == 0:
        plain += "\nNo problems detected in the last 7 days."
        html_content += "No problems detected in the last 7 days."
    else:
        # Kategorien nach Anzahl sortieren
        sorted_cats = sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True)

        for category, count in sorted_cats:
            line = f"{category:<25} {count:>5}"
            plain += f"\n{line}"
            html_content += f"{html.escape(line)}\n"

        # Schweregrad-Aufschlüsselung
        severity_names = {
            '0': 'Not classified',
            '1': 'Information',
            '2': 'Warning',
            '3': 'Average',
            '4': 'High',
            '5': 'Disaster'
        }

        plain += "\n\nBY SEVERITY\n-----------"
        html_content += "</pre>\n<h3>BY SEVERITY</h3>\n<pre>"

        for sev_code, sev_name in severity_names.items():
            count = stats['by_severity'].get(sev_code, 0)
            if count > 0:
                line = f"{sev_name:<25} {count:>5}"
                plain += f"\n{line}"
                html_content += f"{html.escape(line)}\n"

        # Top 10 Hosts
        if stats['by_host']:
            plain += "\n\nTOP 10 HOSTS\n------------"
            html_content += "</pre>\n<h3>TOP 10 HOSTS</h3>\n<pre>"

            sorted_hosts = sorted(stats['by_host'].items(), key=lambda x: x[1], reverse=True)[:10]

            for hostname, count in sorted_hosts:
                line = f"{hostname:<30} {count:>5}"
                plain += f"\n{line}"
                html_content += f"{html.escape(line)}\n"

    html_content += "</pre>"

    # Fußzeile
    plain += "\n\n" + "="*50
    plain += "\nEnd of Report"

    html_content += f"<hr><p><small>Report generated automatically by Zabbix Weekly Report Script</small></p>"

    return plain, html_content

def send_to_matrix(config, plain_text, html_content):
    """Bericht an Matrix-Raum senden"""
    room_id = config['weekly_room']

    data = json.dumps({
        "msgtype": "m.text",
        "body": plain_text,
        "format": "org.matrix.custom.html",
        "formatted_body": html_content
    }).encode('utf-8')

    url = f"{config['matrix_server']}/_matrix/client/r0/rooms/{room_id}/send/m.room.message"

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {config['matrix_token']}",
            "Content-Type": "application/json"
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status >= 200 and response.status < 300
    except Exception as e:
        print(f"[{datetime.now()}] Fehler beim Senden an Matrix: {e}")
        return False

def main():
    """Hauptfunktion"""
    try:
        print(f"[{datetime.now()}] Starte Wochenbericht-Generierung...")

        # Konfiguration laden
        config = load_config()

        # Statistiken abrufen
        stats = get_weekly_stats(config)

        # Bericht formatieren
        plain_text, html_content = format_report(stats)

        # An Matrix senden
        if send_to_matrix(config, plain_text, html_content):
            print(f"[{datetime.now()}] Bericht erfolgreich gesendet")
            return 0
        else:
            print(f"[{datetime.now()}] Fehler beim Senden des Berichts")
            return 1

    except Exception as e:
        print(f"[{datetime.now()}] Fehler: {e}")
        return 1

if __name__ == "__main__":
    exit(main())