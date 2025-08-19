#!/bin/bash
LOG="/var/log/zabbix-monitor/rpm-changes.log"
STATE="/var/lib/zabbix/rpm.state"
TEMP="/tmp/rpm.current"

mkdir -p /var/lib/zabbix

# Aktuelle Packages
rpm -qa --qf "%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n" | sort > "$TEMP"

# Erster Lauf?
if [ ! -f "$STATE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S'): INITIAL: RPM monitoring initialized" >> "$LOG"
    cp "$TEMP" "$STATE"
    exit 0
fi

# Nur wenn Änderungen
if ! diff -q "$STATE" "$TEMP" > /dev/null; then
    # Entfernte Packages
    comm -23 "$STATE" "$TEMP" | while read pkg; do
        echo "$(date '+%Y-%m-%d %H:%M:%S'): REMOVED: $pkg" >> "$LOG"
    done

    # Neue Packages
    comm -13 "$STATE" "$TEMP" | while read pkg; do
        echo "$(date '+%Y-%m-%d %H:%M:%S'): INSTALLED: $pkg" >> "$LOG"
    done

    # Updates erkennen (gleicher Package-Name)
    while read pkg; do
        name=$(echo "$pkg" | rev | cut -d- -f3- | rev)
        # Wurde ein Package mit gleichem Namen entfernt UND installiert?
        if grep -q "^${name}-" "$STATE" && [ "$pkg" != "$(grep "^${name}-" "$STATE")" ]; then
            old_ver=$(grep "^${name}-" "$STATE")
            echo "$(date '+%Y-%m-%d %H:%M:%S'): UPDATED: $old_ver -> $pkg" >> "$LOG"
        fi
    done < <(comm -13 "$STATE" "$TEMP")
fi

# State updaten
cp "$TEMP" "$STATE"
rm -f "$TEMP"
