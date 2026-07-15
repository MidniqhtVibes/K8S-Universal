# Proxmox Kubernetes Cluster Builder

Webbasierter Builder für HA-Kubernetes-Cluster auf Proxmox. Die Anwendung erzeugt aus einem Wizard Terraform- und Ansible-Konfigurationen, erstellt die Proxmox-VMs und installiert Kubernetes, Calico und optional Traefik.

Die Anwendung wird als fertige Container-Images über die GitHub Container Registry (GHCR) bereitgestellt. Für den normalen Betrieb müssen die Images daher nicht lokal gebaut werden. Installationsabhängige Werte wie Passwörter, Secrets, Ports und Laufzeiteinstellungen werden über eine eigene `.env` konfiguriert.

## Funktionen

- Proxmox-Cluster-Erzeugung mit Load Balancern, Control Planes und Workern
- Terraform Plan, Apply, Destroy Plan und Destroy über die Weboberfläche
- Provisionierung über Terraform, Ansible und kubeadm
- HAProxy und Keepalived für die Kubernetes-API-VIP
- Calico als CNI und optional Traefik als Ingress Controller
- Credentials für Proxmox API und SSH-Schlüsselverwaltung
- Kubernetes-Web-Konsole für `kubectl`
- Anwendungsvorlagen und Manifest-Bundles
- Job-Recovery nach Worker-Neustart
- Fertige Web- und Worker-Images über GHCR
- Versionsbasierte Updates über `BUILDER_VERSION`

## Voraussetzungen

Für den Betrieb:

- Docker und Docker Compose
- Ein erreichbarer Proxmox-Host oder Proxmox-Cluster
- Ein cloud-init-fähiges QEMU-VM-Template auf dem ausgewählten Proxmox-Node
- Proxmox API Token mit Rechten zum Erstellen, Lesen und Löschen von VMs
- Freie IP-Adressen und VM-IDs für Load Balancer, Control Planes und Worker
- Netzwerkzugriff vom Builder/Worker zu Proxmox
- Netzwerkzugriff der erzeugten VMs ins Internet
- Zugriff auf `ghcr.io`, sofern die Images direkt aus der GitHub Container Registry bezogen werden

Für die lokale Entwicklung zusätzlich:

- Git
- Ein Checkout des vollständigen Repositories

## Proxmox-Template vorbereiten

Das Repository enthält mit `proxmox/create-template.sh` ein einmaliges Host-Setupwerkzeug. Es wird direkt als `root` auf genau dem Proxmox-Node ausgeführt, der später im Wizard ausgewählt wird.

Das Skript läuft nicht im Builder-Container und wird weder von der Webanwendung noch von Ansible automatisch gestartet.

Es lädt ein offizielles Ubuntu-Cloud-Image über HTTPS, prüft dessen SHA-256-Wert, installiert Cloud-Init, SSH und den QEMU Guest Agent und erzeugt daraus ein QEMU-Template.

Die VM-ID besitzt keinen festen Standardwert und muss im gesamten Proxmox-Cluster frei sein. Vorhandene VMs werden nicht überschrieben.

Das Skript zuerst aus dem Repository auf den Zielnode kopieren:

```bash
scp proxmox/create-template.sh root@pve-node:/root/create-template.sh
ssh root@pve-node
```

Danach auf dem Proxmox-Host ausführen. `9100` ist hier nur eine Beispiel-ID:

```bash
bash /root/create-template.sh \
  --vm-id 9100 \
  --storage local-lvm \
  --bridge vmbr0 \
  --ubuntu-release noble \
  --install-dependencies
```

Ohne `--install-dependencies` verändert das Skript keine Hostpakete und bricht bei fehlenden Werkzeugen mit einer Erklärung ab.

Alle Optionen zeigt:

```bash
bash /root/create-template.sh --help
```

Nach erfolgreichem Abschluss kann das Template später im Builder ausgewählt werden.

## Setup mit fertigen Container-Images

Für den normalen Betrieb werden die Images nicht mehr lokal gebaut.

Benötigt werden:

```text
compose.yaml
.env
```

Als Vorlage für die Konfiguration dient `.env.example`.

### 1. `.env` erstellen

Unter Linux:

```bash
cp .env.example .env
chmod 600 .env
```

Unter PowerShell:

```powershell
Copy-Item .env.example .env
```

Danach die Werte in `.env` anpassen.

Beispiel:

```env
COMPOSE_PROJECT_NAME=k8s-universal

BUILDER_VERSION=1.0.0

BUILDER_WEB_IMAGE=ghcr.io/midniqhtvibes/k8s-universal-web
BUILDER_WORKER_IMAGE=ghcr.io/midniqhtvibes/k8s-universal-worker

POSTGRES_PASSWORD=replace-with-a-long-random-url-safe-password
MASTER_KEY=replace-with-at-least-32-random-characters
SESSION_SECRET=replace-with-an-independent-long-random-value
INITIAL_ADMIN_PASSWORD=replace-on-first-start

BUILDER_BIND_ADDRESS=127.0.0.1
BUILDER_PORT=8000
SESSION_HTTPS_ONLY=false

TERRAFORM_PARALLELISM=2
ANSIBLE_FORKS=4

STALE_JOB_TIMEOUT_MINUTES=60
JOB_RETENTION_KEEP=100
MANIFEST_REVISION_RETENTION_KEEP=30
```

`MASTER_KEY` muss dauerhaft gleich bleiben. Wird der Wert geändert oder verloren, können gespeicherte verschlüsselte Credentials nicht mehr entschlüsselt werden.

Für `POSTGRES_PASSWORD` wird aktuell ein URL-sicherer Wert empfohlen, da das Passwort in der `DATABASE_URL` verwendet wird.

Zum Beispiel:

```bash
openssl rand -hex 32
```

### 2. Container-Images auswählen

Die Images werden standardmäßig aus GHCR geladen:

```text
ghcr.io/midniqhtvibes/k8s-universal-web
ghcr.io/midniqhtvibes/k8s-universal-worker
```

Die gewünschte Version wird über `BUILDER_VERSION` festgelegt.

Für eine feste Release-Version:

```env
BUILDER_VERSION=1.0.0
```

Für Tests des aktuellen `main`-Standes:

```env
BUILDER_VERSION=edge
```

`latest` verweist auf das zuletzt veröffentlichte Release.

Für produktive Installationen wird eine feste Versionsnummer empfohlen.

### 3. Images herunterladen

```bash
docker compose pull
```

Falls die GHCR-Packages privat sind, muss sich der Docker-Host vorher anmelden:

```bash
echo "$CR_PAT" | docker login ghcr.io -u MidniqhtVibes --password-stdin
```

Bei öffentlichen Images ist kein Login erforderlich.

### 4. Stack starten

```bash
docker compose up -d
```

Status prüfen:

```bash
docker compose ps
```

Logs prüfen:

```bash
docker compose logs -f web worker
```

Die Weboberfläche ist standardmäßig erreichbar unter:

```text
http://127.0.0.1:8000
```

Der initiale Login erfolgt mit dem Benutzer `admin` und dem Wert aus `INITIAL_ADMIN_PASSWORD`.

## Persistente Daten

Der Stack verwendet zwei Docker-Volumes:

```text
postgres-data
cluster-data
```

`postgres-data` enthält die PostgreSQL-Datenbank.

`cluster-data` enthält installationsabhängige Arbeitsdaten des Builders, darunter Cluster-Workspaces und generierte Dateien.

Die Volumes bleiben bei einem normalen Container-Update bestehen.

Sie werden erst entfernt, wenn Docker-Volumes ausdrücklich gelöscht werden.

## Update

Für ein Update auf eine neue Version wird kein lokaler Docker-Build benötigt.

In `.env` die gewünschte Version ändern:

```env
BUILDER_VERSION=1.1.0
```

Danach:

```bash
docker compose pull
docker compose up -d
```

Die Datenbankmigrationen laufen beim Start des `web`-Containers automatisch.

Bestehende Daten in `postgres-data` und `cluster-data` bleiben erhalten.

Vor größeren Versionssprüngen sollte trotzdem ein Backup der persistenten Daten angelegt werden.

## Rollback

Für ein einfaches Container-Rollback kann wieder eine ältere Image-Version gesetzt werden:

```env
BUILDER_VERSION=1.0.0
```

Danach:

```bash
docker compose pull
docker compose up -d
```

Ein Image-Rollback garantiert jedoch nicht automatisch, dass bereits ausgeführte Datenbankmigrationen rückwärtskompatibel sind.

## Lokale Entwicklung

Für die lokale Entwicklung werden `compose.yaml` und `compose.dev.yaml` gemeinsam verwendet.

Unter Linux:

```bash
docker compose \
  -f compose.yaml \
  -f compose.dev.yaml \
  up -d --build
```

Unter PowerShell:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

Im Development-Setup werden Web und Worker lokal aus dem Dockerfile gebaut und das Repository zusätzlich nach `/iac` eingebunden.

Dadurch kann weiterhin direkt mit den lokalen Terraform-, Ansible- und Anwendungdateien gearbeitet werden.

Lokale Tests können über das Test-Profil gestartet werden:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm test
```

## GitHub Actions und GHCR

Die CI/CD-Pipeline liegt unter:

```text
.github/workflows/containers.yml
```

Bei einem Pull Request gegen `main`:

- wird das Test-Image gebaut
- werden die Pytest-Tests ausgeführt
- werden Web- und Worker-Images testweise gebaut
- es erfolgt kein Push nach GHCR

Bei einem Push auf `main` werden nach erfolgreichen Tests unter anderem folgende Tags veröffentlicht:

```text
ghcr.io/midniqhtvibes/k8s-universal-web:edge
ghcr.io/midniqhtvibes/k8s-universal-worker:edge
```

Zusätzlich werden SHA-basierte Tags erzeugt.

Ein Release wird über einen Git-Tag ausgelöst:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Dadurch werden unter anderem veröffentlicht:

```text
ghcr.io/midniqhtvibes/k8s-universal-web:1.0.0
ghcr.io/midniqhtvibes/k8s-universal-web:latest

ghcr.io/midniqhtvibes/k8s-universal-worker:1.0.0
ghcr.io/midniqhtvibes/k8s-universal-worker:latest
```

## Wartung

Nützliche Befehle:

```bash
docker compose ps
docker compose logs -f web worker
docker compose restart web worker
```

Neue Images laden und Container aktualisieren:

```bash
docker compose pull
docker compose up -d
```

Container stoppen:

```bash
docker compose down
```

Die persistenten Volumes bleiben dabei erhalten.

## Sicherheit

Folgende Dateien und Daten dürfen nicht in Git eingecheckt oder in Container-Images eingebaut werden:

```text
.env
Kubeconfigs
Talos-Konfigurationen
Terraform State
Private Keys
Cluster-Workspaces
Datenbankdaten
```

Ins Repository gehört nur die Vorlage:

```text
.env.example
```

`MASTER_KEY`, `SESSION_SECRET`, `POSTGRES_PASSWORD` und `INITIAL_ADMIN_PASSWORD` müssen pro Installation individuell gesetzt werden.

## Hinweise

- Für produktive Installationen sollte `BUILDER_VERSION` auf eine feste Version gesetzt werden.
- `edge` eignet sich für Tests des aktuellen `main`-Branches.
- `latest` verweist auf das zuletzt veröffentlichte Release.
- `MASTER_KEY` muss dauerhaft gesichert und unverändert aufbewahrt werden.
- Bei privaten GHCR-Images ist vor `docker compose pull` eine Anmeldung bei `ghcr.io` erforderlich.
- Wenn externe Downloads rate-limitiert werden, den Vorgang später erneut starten.
- Bei DNS- oder APT-Fehlern zuerst Gateway, DNS und Internetzugriff der Ziel-VMs prüfen.
