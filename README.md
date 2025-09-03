# Lock Monitor Application

Automatisches Monitoring-System für Cloud Smartlocks mit Strike-Management.

## 🎯 Funktionen

- **Automatische Lock-Überwachung** über E-Schloss Cloud API
- **3-Strike-System** mit E-Mail-Benachrichtigungen
- **Excel-Integration** für Benutzerdaten
- **Gästekarten-Support** mit Supervisor-Benachrichtigung
- **Automatische Cleanup-Routinen** für alte Strikes
- **Docker-Ready** für einfache Bereitstellung

## 📋 Voraussetzungen

- Python 3.11+
- Docker & Docker Compose (optional)
- E-Schloss Cloud API Zugang
- SMTP-Server für E-Mail-Versand

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

### 3. Mit Docker starten
```bash
docker-compose up -d
```

### 4. Ohne Docker starten
```bash
pip install -r requirements.txt
python -m app.main
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
│   │   ├── lock_api.py      # E-Schloss Cloud API
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
