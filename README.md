Über dieses Repository
Dieses Repository enthält den vollständigen Quellcode und alle Konfigurationsdateien meiner Bachelorarbeit zum Thema "Automatisierte Überwachung von Desktop-Linuxsystemen" an der HTW Berlin.
Projektbeschreibung
Implementierung eines automatisierten Monitoring-Systems für 17 Linux-Arbeitsplätze im Hochschul-Labor basierend auf:

Zabbix 7.0 LTS als zentrale Monitoring-Plattform
Matrix/Element für mobile Echtzeit-Benachrichtigungen
PostgreSQL 16 als Datenbank
Rocky Linux 9 als Betriebssystem

Implementierte Use Cases
Das System überwacht 10 definierte Bereiche:

PC-Verfügbarkeit - Erkennung von System-Ausfällen
Login-Events - SSH-Login/Logout-Überwachung via rsyslog
Sicherheit - fail2ban-Integration ohne D-Bus
Lange Sessions - Erkennung überlanger Benutzersitzungen
Ressourcen - CPU/RAM-Überwachung
Speicherplatz - Festplatten-Monitoring
Netzwerk-Traffic - Bandbreiten-Überwachung
System-Updates - RPM-Package-Monitoring
File-Integrity - AIDE-Integration und Echtzeit-Überwachung
Wochenberichte - Automatische Report-Generierung

Repository-Struktur

installation_guide.txt - Komplette Installationsanleitung für Server und Clients
matrix_smart.py - Intelligentes Alert-Routing für Matrix
zabbix_weekly_report.py - Automatische Wochenbericht-Generierung
file_integrity_monitoring.sh - Echtzeit-Überwachung kritischer Systemdateien
rpm-monitor.sh - Package-Management-Überwachung
Konfigurationsdateien für rsyslog, fail2ban, AIDE, nftables

Besonderheiten

100% Open-Source-Lösung ohne Lizenzkosten
On-Premises-Betrieb ohne Cloud-Abhängigkeiten
TLS-verschlüsselte Kommunikation
SELinux-gehärtete Sicherheitsarchitektur
Mobile Benachrichtigung über F-Droid App (ohne Google Services)

Autor
Stefan Anhalt - HTW Berlin, Fachbereich 2, Ingenieurinformatik
Lizenz
Dieser Code wird zu Bildungszwecken zur Verfügung gestellt.