
#!/bin/bash
AIDE_LOG="/var/log/aide/aide.log"
ZABBIX_LOG="/var/log/aide-summary.zabbix.log"

# AIDE Check ausführen
sudo aide --check > $AIDE_LOG 2>&1

# Einfache Prüfung
if grep -q "AIDE found differences" $AIDE_LOG; then
    # Anzahl der Zeilen mit File-Änderungen zählen
    TOTAL=$(grep -E "^(File|Directory):" $AIDE_LOG | wc -l)

    if [ $TOTAL -gt 50 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S'): AIDE-SUMMARY: Total:$TOTAL files/directories changed - MASS-CHANGE-WARNING" >> $ZABBIX_LOG
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S'): AIDE-SUMMARY: Total:$TOTAL files/directories changed" >> $ZABBIX_LOG
    fi
else
    echo "$(date '+%Y-%m-%d %H:%M:%S'): AIDE-SUMMARY: No changes detected" >> $ZABBIX_LOG
fi
