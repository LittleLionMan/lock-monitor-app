# Lock Monitor Application

Automatisches Monitoring-System für Burg Cloud Smartlocks mit Strike-Management.

## 🎯 Funktionen

- **Automatische Lock-Überwachung** über Burg Cloud API
- **3-Strike-System** mit E-Mail-Benachrichtigungen
- **Excel-Integration** für Benutzerdaten
- **Gästekarten-Support** mit Supervisor-Benachrichtigung
- **Automatische Cleanup-Routinen** für alte Strikes
- **Docker-Ready** für einfache Bereitstellung

## 📋 Voraussetzungen

- Python 3.11+
- Docker & Docker Compose (optional)
- Burg Cloud API Zugang
- SMTP-Server für E-Mail-Versand
- Excel-Datei mit Benutzerdaten

## ⚡ Quick Start

### 1. Repository klonen
```bash
git clone <repository-url>
cd lock-monitor-app
```

### 2. Konfiguration erstellen
```bash
cp .env.example .env
nano .env  # Ihre Werte eintragen
```

### 3. Excel-Datenbank vorbereiten
Stellen Sie sicher, dass Ihre Excel-Datei die korrekte Struktur hat:
- **Spalte A:** Supervisor (Format: "Nachname, Vorname")
- **Spalte B:** Gender (w/m)
- **Spalte D:** Vorname
- **Spalte E:** Nachname
- **Spalte K:** Karten-UID

### 4. Mit Docker starten
```bash
docker-compose up -d
```

### 5. Ohne Docker starten
```bash
pip install -r requirements.txt
python -m app.main
```

## 🔧 Konfiguration

### Wichtige .env Variablen

```bash
# Burg Cloud API
BURG_EMAIL=ihre-email@domain.de
BURG_PASSWORD=ihr-passwort
BURG_BASE_URL=https://smartlocks.burgcloud.com/burg/rest

# Monitoring
MONITORED_UNITS=379,380,381
WHITELIST_LOCATIONS=7606,7607
VIOLATION_HOURS=48
STRIKE_CLEANUP_DAYS=90

# E-Mail
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=smtp-user@domain.de
EMAIL_PASSWORD=app-passwort

# Excel Database
EXCEL_USER_DATABASE=data/users.xlsx
EXCEL_COL_SUPERVISOR=A
EXCEL_COL_GENDER=B
EXCEL_COL_FIRSTNAME=D
EXCEL_COL_LASTNAME=E
EXCEL_COL_UID=K
EXCEL_WORKSHEETS=1,2
```

## 📊 Strike-System

### Strike 1
- **Auslöser:** Schloss 48h+ nicht verschlossen
- **Aktion:** E-Mail an User + CC Supervisor
- **Cooldown:** 48h (kein neuer Strike)

### Strike 2
- **Auslöser:** Erneuter Verstoß nach Strike 1
- **Aktion:** Warnungs-E-Mail an User + CC Supervisor

### Strike 3
- **Auslöser:** Dritter Verstoß
- **Aktion:**
  - Karte aus Cloud-System gelöscht
  - Karte aus Excel-DB gelöscht
  - E-Mail an User + CC Supervisor
  - Counter wird erhöht (für weitere Verstöße)

### Cleanup
- Automatisch alle Strikes löschen wenn jüngster Strike > 90 Tage alt

## 🐳 Docker

### Standard Deployment
```bash
docker-compose up -d
```

### Development
```bash
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

### Logs anzeigen
```bash
docker-compose logs -f lock-monitor
```

## 🛠️ Development

### Manuelle Tests
```bash
# Einmalige Ausführung (statt Scheduler)
python -m app.main --once

# Konfiguration validieren
python -m app.config

# Datenbank erstellen
python -m app.models.database

# Services testen
python -c "from app.services.excel_service import ExcelService; from app.config import config; service = ExcelService(config); print(service.test_connection())"
```

### Struktur
```
lock-monitor-app/
├── app/
│   ├── main.py              # Hauptanwendung
│   ├── config.py            # Konfiguration
│   ├── models/
│   │   └── database.py      # SQLite Models
│   ├── services/
│   │   ├── lock_api.py      # Burg Cloud API
│   │   ├── excel_service.py # Excel Integration
│   │   ├── email_service.py # E-Mail Versand
│   │   └── strike_service.py # Strike Management
│   └── utils/
│       └── logger.py        # Logging Setup
├── data/
│   ├── users.xlsx           # Excel Benutzerdatenbank
│   └── app_database.db      # SQLite App-DB
├── email_templates/         # E-Mail Templates
├── logs/                    # Log-Dateien
├── .env                     # Konfiguration
└── docker-compose.yml      # Docker Setup
```

## 📧 E-Mail Templates

Templates können angepasst werden in `email_templates/`:
- `strike_1.html` - Erste Warnung
- `strike_2.html` - Zweite Warnung
- `strike_3.html` - Kartensperrung

### Verfügbare Variablen
- `{{name}}` - Benutzername
- `{{anrede}}` - Geschlechtsspezifische Anrede
- `{{supervisor}}` - Vorgesetzter
- `{{card_uid}}` - Karten-UID
- `{{location}}` - Standort
- `{{lock_id}}` - Schloss-ID
- `{{violation_date}}` - Verstoß-Datum
- `{{current_date}}` - Aktuelles Datum
- `{{current_time}}` - Aktuelle Zeit

## 🔍 Monitoring

### Logs
```bash
# Live Logs
tail -f logs/lock_monitor.log

# Docker Logs
docker-compose logs -f
```

### Status prüfen
```bash
# Container Status
docker-compose ps

# Letzte Ausführung
grep "Lock check process completed" logs/lock_monitor.log | tail -1
```

## 🚨 Troubleshooting

### Häufige Probleme

**Excel-Datei nicht gefunden:**
```bash
# Pfad prüfen
ls -la data/users.xlsx
# Berechtigung prüfen
chmod 644 data/users.xlsx
```

**E-Mail-Versand fehlschlägt:**
```bash
# SMTP-Verbindung testen
python -c "from app.services.email_service import EmailService; from app.config import config; service = EmailService(config); print(service.test_connection())"
```

**API-Verbindung fehlschlägt:**
```bash
# Burg Cloud API testen
python -c "from app.services.lock_api import LockAPIService; from app.config import config; service = LockAPIService(config); print(service.test_connection())"
```

### Debug Mode
```bash
# .env
DEBUG=true
LOG_LEVEL=DEBUG

# Neustart
docker-compose restart
```

## 📝 Changelog

### v1.0.0
- Initiale Version
- 3-Strike-System implementiert
- Burg Cloud API Integration
- Excel-Datenbank Support
- E-Mail-Benachrichtigungen
- Docker Support

## 🤝 Support

Bei Fragen oder Problemen:
1. Logs prüfen (`logs/lock_monitor.log`)
2. Konfiguration validieren (`python -m app.config`)
3. Services einzeln testen
4. GitHub Issues erstellen

---

**Lock Monitor Application** - Automatisches Schloss-Monitoring für Burg Cloud Systeme
