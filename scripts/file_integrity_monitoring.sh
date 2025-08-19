#!/bin/bash
LOG_FILE="/var/log/file_integrity.zabbix.log"
STATE_DIR="/var/lib/zabbix/file_states"

# Verzeichnis für State-Files erstellen
mkdir -p $STATE_DIR

# TIER 1: Kritische Dateien für Real-Time Monitoring
FILES=(
    "/etc/passwd"
    "/etc/shadow"
    "/etc/sudoers"
    "/etc/ssh/sshd_config"
    "/etc/hosts"
    "/etc/fstab"
    "/etc/group"
    "/root/.ssh/authorized_keys"
)

# Dynamisch alle User authorized_keys finden
for user_home in /home/*; do
    if [ -f "$user_home/.ssh/authorized_keys" ]; then
        FILES+=("$user_home/.ssh/authorized_keys")
    fi
done

# Aktuelle eingeloggte Benutzer
LOGGED_USERS=$(who | awk '{print $1}' | sort -u | tr '\n' ',' | sed 's/,$//')

for FILE in "${FILES[@]}"; do
    if [ -f "$FILE" ]; then
        CURRENT_HASH=$(sha256sum "$FILE" | cut -d' ' -f1)
        CURRENT_PERMS=$(stat -c "%a" "$FILE")
        CURRENT_OWNER=$(stat -c "%U:%G" "$FILE")
        CURRENT_SIZE=$(stat -c "%s" "$FILE")

        STATE_BASE="$STATE_DIR/$(echo $FILE | tr '/' '_')"

        if [ -f "${STATE_BASE}.hash" ]; then
            OLD_HASH=$(cat "${STATE_BASE}.hash" 2>/dev/null)
            OLD_PERMS=$(cat "${STATE_BASE}.perms" 2>/dev/null)
            OLD_OWNER=$(cat "${STATE_BASE}.owner" 2>/dev/null)
            OLD_SIZE=$(cat "${STATE_BASE}.size" 2>/dev/null)

            DETAILS=""
            RISKS=""

            if [ "$CURRENT_HASH" != "$OLD_HASH" ]; then
                DETAILS="${DETAILS}CONTENT[${OLD_SIZE}b→${CURRENT_SIZE}b,SHA:${OLD_HASH:0:8}→${CURRENT_HASH:0:8}] "

                if [[ "$FILE" == "/etc/sudoers" ]]; then
                    RISKS="${RISKS}SECURITY-RISK:PRIVILEGE-ESCALATION "
                elif [[ "$FILE" == "/etc/passwd" ]]; then
                    RISKS="${RISKS}SECURITY-RISK:USER-ACCOUNTS "
                elif [[ "$FILE" == "/etc/shadow" ]]; then
                    RISKS="${RISKS}SECURITY-RISK:PASSWORDS "
                elif [[ "$FILE" =~ authorized_keys ]]; then
                    RISKS="${RISKS}SECURITY-RISK:SSH-ACCESS "
                fi
            fi

            if [ "$CURRENT_PERMS" != "$OLD_PERMS" ]; then
                DETAILS="${DETAILS}PERMS[${OLD_PERMS}→${CURRENT_PERMS}] "

                if [[ "$CURRENT_PERMS" =~ [24567] ]]; then
                    RISKS="${RISKS}SECURITY-RISK:WORLD-WRITABLE "
                fi
            fi

            if [ "$CURRENT_OWNER" != "$OLD_OWNER" ]; then
                DETAILS="${DETAILS}OWNER[${OLD_OWNER}→${CURRENT_OWNER}] "

                if [[ "$CURRENT_OWNER" != "root:root" ]] && [[ "$FILE" =~ (passwd|shadow|sudoers) ]]; then
                    RISKS="${RISKS}SECURITY-RISK:NON-ROOT-OWNER "
                fi
            fi

            if [ ! -z "$DETAILS" ]; then
                echo "$(date '+%Y-%m-%d %H:%M:%S'): FILE-CHANGE $FILE - $DETAILS- ActiveUsers:[$LOGGED_USERS] $RISKS" >> $LOG_FILE
            fi
        fi

        echo "$CURRENT_HASH" > "${STATE_BASE}.hash"
        echo "$CURRENT_PERMS" > "${STATE_BASE}.perms"
        echo "$CURRENT_OWNER" > "${STATE_BASE}.owner"
        echo "$CURRENT_SIZE" > "${STATE_BASE}.size"
    fi
done
