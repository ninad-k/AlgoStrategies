# PineConnector Deployment Guide

## Deployment Options

| Option | Use Case | Cost | Latency |
|--------|----------|------|---------|
| Local machine | Development/testing | Free | Lowest |
| Windows VPS | Production (recommended) | $20-50/mo | Low |
| Cloud VM (AWS/Azure) | Scalable production | $30-100/mo | Medium |

---

## Production Deployment on Windows VPS

### Step 1: Provision a Windows VPS

**Recommended providers**:
- Contabo (cheapest: Windows VPS from ~$10/mo)
- Vultr (Windows Cloud Compute from ~$24/mo)
- AWS Lightsail (Windows from ~$20/mo)

**Minimum specs**:
- 2 vCPU, 4GB RAM, 50GB SSD
- Windows Server 2019/2022
- Public IPv4 address

### Step 2: Install Prerequisites

```powershell
# Install Python 3.11
winget install Python.Python.3.11

# Install Rust
winget install Rustlang.Rust.MSVC

# Install Git
winget install Git.Git

# Install Visual C++ Build Tools (required for zmq)
winget install Microsoft.VisualStudio.2022.BuildTools
```

### Step 3: Install MetaTrader 5

1. Download MT5 from your broker
2. Install and log in to your trading account
3. Go to Tools → Options → Expert Advisors
4. Check "Allow algorithmic trading"
5. Check "Allow DLL imports" (for MQL5 EA mode)
6. Keep MT5 running at all times

### Step 4: Clone and Configure

```powershell
cd C:\
git clone https://github.com/ninad-k/AlgoStrategies.git
cd AlgoStrategies\tools\pineconnector

# Copy and edit config
copy .env.example .env
notepad .env
```

### Step 5: Install Python Dependencies

```powershell
pip install -r requirements.txt
```

### Step 6: Build Rust Engine

```powershell
cd rust
cargo build --release
```

### Step 7: Run as Windows Services

Use **NSSM** (Non-Sucking Service Manager) to run both processes as services:

```powershell
# Download NSSM
# https://nssm.cc/download

# Install Python server as service
nssm install PineConnector-Python "C:\Python311\python.exe" "C:\AlgoStrategies\tools\pineconnector\run.py"
nssm set PineConnector-Python AppDirectory "C:\AlgoStrategies\tools\pineconnector"
nssm set PineConnector-Python AppStdout "C:\AlgoStrategies\tools\pineconnector\data\python.log"
nssm set PineConnector-Python AppStderr "C:\AlgoStrategies\tools\pineconnector\data\python-error.log"

# Install Rust engine as service
nssm install PineConnector-Rust "C:\AlgoStrategies\tools\pineconnector\rust\target\release\pineconnector-engine.exe"
nssm set PineConnector-Rust AppDirectory "C:\AlgoStrategies\tools\pineconnector"
nssm set PineConnector-Rust AppStdout "C:\AlgoStrategies\tools\pineconnector\data\rust.log"
nssm set PineConnector-Rust AppStderr "C:\AlgoStrategies\tools\pineconnector\data\rust-error.log"

# Start services
nssm start PineConnector-Rust
nssm start PineConnector-Python
```

**Alternative**: Use Windows Task Scheduler with "Run at startup" trigger.

### Step 8: Configure Firewall

```powershell
# Allow inbound on port 8003 (webhook endpoint)
netsh advfirewall firewall add rule name="PineConnector Webhook" dir=in action=allow protocol=TCP localport=8003

# IMPORTANT: ZMQ ports (5555-5559) should NOT be exposed
# They are localhost-only by default
```

### Step 9: Configure TradingView

Set your webhook URL to:
```
http://YOUR_VPS_PUBLIC_IP:8003/webhook
```

---

## Security Hardening

### Use HTTPS (Recommended)

Use **Caddy** as a reverse proxy for automatic HTTPS:

```powershell
# Install Caddy
winget install Caddy.Caddy

# Create Caddyfile
echo "your-domain.com { reverse_proxy localhost:8003 }" > C:\Caddy\Caddyfile

# Run Caddy
caddy run --config C:\Caddy\Caddyfile
```

TradingView webhook URL becomes:
```
https://your-domain.com/webhook
```

### IP Whitelist

TradingView sends webhooks from specific IP ranges. Add firewall rules:

```powershell
# TradingView webhook IPs (check TradingView docs for current list)
# Example: restrict port 8003 to TradingView IPs only
netsh advfirewall firewall add rule name="TV Webhook" dir=in action=allow protocol=TCP localport=8003 remoteip=52.89.214.238,34.212.75.30
```

### Strong Webhook Token

Generate a cryptographically secure token:
```python
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Monitoring in Production

### Health Check Monitoring

Set up an external uptime monitor (UptimeRobot, Healthchecks.io) to ping:
```
http://YOUR_IP:8003/api/health
```

### Log Rotation

Use **NSSM** log rotation or Windows Task Scheduler to rotate logs:

```powershell
# Simple daily rotation script (schedule via Task Scheduler)
$date = Get-Date -Format "yyyy-MM-dd"
Move-Item C:\...\data\python.log C:\...\data\logs\python-$date.log
Move-Item C:\...\data\rust.log C:\...\data\logs\rust-$date.log
```

### Database Backup

```powershell
# Daily SQLite backup (schedule via Task Scheduler)
$date = Get-Date -Format "yyyy-MM-dd"
Copy-Item C:\...\data\pineconnector.db C:\...\data\backups\pineconnector-$date.db
```

---

## Auto-Start Configuration

Ensure all components start after VPS reboot:

1. **MT5**: Add to Windows Startup folder
2. **PineConnector Python**: NSSM service (auto-start)
3. **PineConnector Rust**: NSSM service (auto-start)

**Startup order matters:**
1. MT5 must start first (needs 10-30s to connect to broker)
2. Rust engine starts next (binds ZMQ sockets)
3. Python server starts last (connects to ZMQ sockets)

Add a startup delay in NSSM:
```powershell
nssm set PineConnector-Rust AppRestartDelay 30000   # 30s after boot
nssm set PineConnector-Python AppRestartDelay 45000  # 45s after boot
```

---

## Troubleshooting Production Issues

### Service won't start

```powershell
# Check service status
nssm status PineConnector-Python
nssm status PineConnector-Rust

# Check error logs
type C:\...\data\python-error.log
type C:\...\data\rust-error.log
```

### MT5 disconnects frequently

- Check VPS internet stability
- Enable MT5 "Keep alive" in settings
- Use MT5 auto-login (saved credentials)

### High memory usage

- SQLite WAL mode can grow large — run `PRAGMA wal_checkpoint(TRUNCATE)` weekly
- Set ZMQ high-water marks (already configured to 1000)

### Webhook timeouts from TradingView

- TradingView has a 3-second webhook timeout
- If your server responds slower, check:
  - Risk engine: should be <5ms (is DB query leaking into critical path?)
  - ZMQ: check if Rust engine is consuming signals (blocked?)
  - Network: VPS bandwidth saturated?
