# ═══════════════════════════════════════════════════════════════════════════════
#  Rey Capital - Gemma Trader Setup Script
#  Complete initialization: Ollama, Python, dependencies, configuration
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [switch]$SkipOllama,
    [switch]$SkipMT5,
    [string]$OllamaModel = "gemma4",
    [switch]$Verbose
)

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvDir = Join-Path $AppDir "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ReqFile = Join-Path $AppDir "requirements.txt"
$LogsDir = Join-Path $AppDir "logs"

$OllamaUrl = "http://localhost:11434"
$OllamaDownloadUrl = "https://ollama.ai/download"
$MT5DownloadUrl = "https://www.metatrader5.com/en/download"

# ─────────────────────────────────────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

function Write-Banner {
    Write-Host "`n" -NoNewline
    Write-Host "  ╔═══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║     REY CAPITAL - GEMMA TRADER SETUP WIZARD           ║" -ForegroundColor Cyan
    Write-Host "  ║     Complete Environment Installation                ║" -ForegroundColor Cyan
    Write-Host "  ╚═══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host "`n"
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host "  $Title" -ForegroundColor White
    Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [✓] " -ForegroundColor Green -NoNewline
    Write-Host $Message -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "  [!] " -ForegroundColor Yellow -NoNewline
    Write-Host $Message -ForegroundColor Yellow
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "  [✗] " -ForegroundColor Red -NoNewline
    Write-Host $Message -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "  [i] " -ForegroundColor Cyan -NoNewline
    Write-Host $Message -ForegroundColor Cyan
}

function Test-CommandExists {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

function Test-Port {
    param([int]$Port)
    try {
        $listener = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
        return $listener.Port -contains $Port
    } catch {
        return $false
    }
}

# ─────────────────────────────────────────────────────────────────────────────
#  1. SYSTEM CHECKS
# ─────────────────────────────────────────────────────────────────────────────

Write-Banner

Write-Section "Step 1: System Requirements Check"

# Check Python
Write-Info "Checking Python installation..."
if (Test-CommandExists "python") {
    $pyVer = & python --version 2>&1 | Select-Object -First 1
    Write-Success "Python found: $pyVer"
    if ($pyVer -match "Python (\d+\.\d+)") {
        $ver = [version]$Matches[1]
        if ($ver -lt [version]"3.8") {
            Write-Warning "Python 3.8 or higher is recommended"
        }
    }
} else {
    Write-Error-Custom "Python not found. Install from https://python.org (add to PATH)"
    exit 1
}

# Check Git
Write-Info "Checking Git installation..."
if (Test-CommandExists "git") {
    $gitVer = & git --version
    Write-Success "Git found: $gitVer"
} else {
    Write-Warning "Git not found (optional). Install from https://git-scm.com if needed"
}

Write-Success "System checks passed"

# ─────────────────────────────────────────────────────────────────────────────
#  2. OLLAMA SETUP
# ─────────────────────────────────────────────────────────────────────────────

Write-Section "Step 2: Ollama & Gemma Model Setup"

if ($SkipOllama) {
    Write-Info "Skipping Ollama setup"
} else {
    # Check if Ollama is running
    Write-Info "Checking Ollama service..."
    $ollamaRunning = $false

    try {
        $response = Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -TimeoutSec 3 -ErrorAction Stop
        $ollamaRunning = $true

        # Check for gemma model
        $hasGemma = $response.models | Where-Object { $_.name -like "*gemma*" }

        if ($hasGemma) {
            Write-Success "Ollama is running with Gemma models available"
        } else {
            Write-Warning "Ollama is running but Gemma model not found. Will pull it now..."
        }
    } catch {
        Write-Warning "Ollama is not running"
    }

    # Try to start Ollama if not running
    if (-not $ollamaRunning) {
        Write-Info "Attempting to start Ollama..."

        if (Test-CommandExists "ollama") {
            Write-Info "Starting 'ollama serve' in background..."
            Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
            Start-Sleep -Seconds 5

            # Verify it started
            try {
                $null = Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -TimeoutSec 3
                Write-Success "Ollama service started successfully"
                $ollamaRunning = $true
            } catch {
                Write-Error-Custom "Failed to start Ollama service"
                Write-Info "Please download Ollama from: $OllamaDownloadUrl"
                Write-Info "Then run: ollama serve"
                exit 1
            }
        } else {
            Write-Error-Custom "Ollama not installed"
            Write-Info "Download from: $OllamaDownloadUrl"
            exit 1
        }
    }

    # Pull Gemma model
    if ($ollamaRunning) {
        Write-Info "Pulling $OllamaModel model (this may take a few minutes)..."
        & ollama pull $OllamaModel

        if ($LASTEXITCODE -eq 0) {
            Write-Success "Gemma model pulled successfully"
        } else {
            Write-Error-Custom "Failed to pull Gemma model"
            exit 1
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
#  3. PYTHON VIRTUAL ENVIRONMENT
# ─────────────────────────────────────────────────────────────────────────────

Write-Section "Step 3: Python Virtual Environment Setup"

if ((Test-Path $VenvDir) -and -not (Test-Path $VenvPython)) {
    Write-Warning "Found venv folder but $VenvPython is missing (likely created by a non-Windows Python). Rebuilding..."
    Remove-Item -Path $VenvDir -Recurse -Force -ErrorAction Stop
}

if (Test-Path $VenvPython) {
    Write-Info "Virtual environment already exists at: $VenvDir"
    Write-Info "To recreate, delete the venv folder and run this script again"
} else {
    Write-Info "Creating virtual environment..."
    & python -m venv $VenvDir

    if ($LASTEXITCODE -eq 0 -and (Test-Path $VenvPython)) {
        Write-Success "Virtual environment created at: $VenvDir"
    } else {
        Write-Error-Custom "Failed to create virtual environment"
        exit 1
    }
}

# ─────────────────────────────────────────────────────────────────────────────
#  4. PYTHON DEPENDENCIES
# ─────────────────────────────────────────────────────────────────────────────

Write-Section "Step 4: Installing Python Dependencies"

Write-Info "Activating virtual environment..."
& $VenvDir\Scripts\Activate.ps1

Write-Info "Upgrading pip..."
& $VenvPython -m pip install --upgrade pip -q

Write-Info "Installing core dependencies from requirements.txt..."
if (Test-Path $ReqFile) {
    # pandas_ta pulls in numba transitively, which has no wheel and no source support
    # for Python 3.14 yet (requires <3.14). Install pandas_ta separately with --no-deps
    # on 3.14+ so the rest of requirements.txt can install cleanly.
    $pyVersionRaw = & python -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))"
    $skipPandasTa = $false
    try {
        if ([version]$pyVersionRaw -ge [version]"3.14") { $skipPandasTa = $true }
    } catch {}

    if ($skipPandasTa) {
        Write-Info "Python $pyVersionRaw detected - installing pandas_ta separately with --no-deps (avoids numba build failure)"
        $filteredReq = Join-Path $AppDir ".requirements.nopd_ta.txt"
        (Get-Content $ReqFile) | Where-Object { $_ -notmatch '^\s*pandas_ta\b' } | Set-Content -Encoding UTF8 $filteredReq
        & $VenvPython -m pip install -r $filteredReq -q
        $mainExit = $LASTEXITCODE
        Remove-Item $filteredReq -Force -ErrorAction SilentlyContinue

        if ($mainExit -eq 0) {
            Write-Info "Installing pandas_ta with --no-deps..."
            & $VenvPython -m pip install "pandas_ta>=0.3" --no-deps -q
            if ($LASTEXITCODE -ne 0) {
                Write-Error-Custom "pandas_ta install failed"
                exit 1
            }

            Write-Info "Installing pandas_ta runtime deps (tqdm, scipy, stockstats)..."
            & $VenvPython -m pip install tqdm scipy stockstats -q
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Some pandas_ta runtime deps failed to install (may cause ImportError)"
            }

            # numba has no Python 3.14 wheel. Install a stub so pandas_ta's
            # `from numba import njit` resolves (decorated funcs run as plain Python).
            $hasNumba = $false
            $null = & $VenvPython -c "import numba" 2>&1
            if ($LASTEXITCODE -eq 0) { $hasNumba = $true }
            $LASTEXITCODE = 0

            if (-not $hasNumba) {
                Write-Info "Installing numba stub (real numba unavailable on Python $pyVersionRaw)..."
                $sitePackages = & $VenvPython -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
                $numbaDir = Join-Path $sitePackages "numba"
                if (-not (Test-Path $numbaDir)) {
                    New-Item -Path $numbaDir -ItemType Directory -Force | Out-Null
                }
                $stub = @'
# Minimal numba stub for pandas_ta on Python 3.14+ (no real numba wheel).
def njit(*args, **kwargs):
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]
    def decorator(func):
        return func
    return decorator

def jit(*args, **kwargs):
    return njit(*args, **kwargs)

prange = range
__version__ = "0.0.0-stub"
'@
                Set-Content -Path (Join-Path $numbaDir "__init__.py") -Value $stub -Encoding UTF8
                Write-Success "numba stub installed at $numbaDir"
            }

            Write-Success "Core dependencies installed successfully (pandas_ta via --no-deps + numba stub)"
        } else {
            Write-Error-Custom "Some dependencies failed to install"
            exit 1
        }
    } else {
        & $VenvPython -m pip install -r $ReqFile -q
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Core dependencies installed successfully"
        } else {
            Write-Error-Custom "Some dependencies failed to install"
            exit 1
        }
    }
} else {
    Write-Error-Custom "requirements.txt not found at: $ReqFile"
    exit 1
}

# Install MetaTrader5 (Windows-only)
Write-Info "Installing MetaTrader5 Python library..."
& $VenvPython -m pip install MetaTrader5 -q
if ($LASTEXITCODE -eq 0) {
    Write-Success "MetaTrader5 library installed"
} else {
    Write-Warning "MetaTrader5 library installation failed (optional)"
}

# ─────────────────────────────────────────────────────────────────────────────
#  5. METATRADER 5 (Optional)
# ─────────────────────────────────────────────────────────────────────────────

Write-Section "Step 5: MetaTrader 5 Configuration (Optional)"

if ($SkipMT5) {
    Write-Info "Skipping MT5 check"
} else {
    Write-Info "Checking MetaTrader 5 installation..."

    $mt5Proc = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue

    if ($mt5Proc) {
        Write-Success "MetaTrader 5 is running (PID: $($mt5Proc.Id))"
    } else {
        $mt5Paths = @(
            "C:\Program Files\MetaTrader 5\terminal64.exe",
            "C:\Program Files (x86)\MetaTrader 5\terminal64.exe"
        )

        $mt5Found = $false
        foreach ($path in $mt5Paths) {
            if (Test-Path $path) {
                $mt5Found = $true
                Write-Info "MetaTrader 5 found but not running"
                Write-Info "Please open MetaTrader 5 and log in before running the trader"
                break
            }
        }

        if (-not $mt5Found) {
            Write-Warning "MetaTrader 5 not found"
            Write-Info "For live trading with MT5, download from: $MT5DownloadUrl"
            Write-Info "For paper trading, you can skip this step"
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
#  6. CREATE LOGS DIRECTORY
# ─────────────────────────────────────────────────────────────────────────────

Write-Section "Step 6: Directory Structure"

if (-not (Test-Path $LogsDir)) {
    New-Item -Path $LogsDir -ItemType Directory -Force | Out-Null
    Write-Success "Created logs directory: $LogsDir"
} else {
    Write-Info "Logs directory exists: $LogsDir"
}

# ─────────────────────────────────────────────────────────────────────────────
#  7. VERIFY CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

Write-Section "Step 7: Verification & Summary"

Write-Info "Verifying installation..."

$checksPass = $true

# Verify Python venv
if (Test-Path $VenvPython) {
    Write-Success "Virtual environment: OK"
} else {
    Write-Error-Custom "Virtual environment: FAILED"
    $checksPass = $false
}

# Verify Ollama
try {
    $null = Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -TimeoutSec 2
    Write-Success "Ollama service: OK"
} catch {
    Write-Warning "Ollama service: Not running (will be needed to run the trader)"
}

# Verify requirements
$requiredModules = @("flask", "flask_socketio", "pyyaml", "requests", "pandas", "numpy")
if (-not (Test-Path $VenvPython)) {
    Write-Error-Custom "Venv Python missing at $VenvPython - skipping module verification"
    $checksPass = $false
} else {
    foreach ($module in $requiredModules) {
        $LASTEXITCODE = 0
        $null = & $VenvPython -c "import $module" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "${module}: OK"
        } else {
            Write-Error-Custom "${module}: NOT INSTALLED"
            $checksPass = $false
        }
    }
}

if ($checksPass) {
    Write-Success "All verifications passed!"
} else {
    Write-Warning "Some checks failed. Review the output above."
}

# ─────────────────────────────────────────────────────────────────────────────
#  FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "`n"
Write-Host "  ╔═══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║              SETUP COMPLETE                           ║" -ForegroundColor Green
Write-Host "  ╚═══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Green
Write-Host "  1. Run the trader:" -ForegroundColor White
Write-Host "     .\Run-GemmaTrader.ps1" -ForegroundColor Cyan
Write-Host "  "
Write-Host "  2. (Optional) For paper trading mode:" -ForegroundColor White
Write-Host "     .\Run-GemmaTrader.ps1 -Mode paper" -ForegroundColor Cyan
Write-Host "  "
Write-Host "  3. Open dashboard in browser:" -ForegroundColor White
Write-Host "     http://localhost:8050" -ForegroundColor Cyan
Write-Host "  "
Write-Host "  To stop the trader, run:" -ForegroundColor White
Write-Host "     .\Stop-GemmaTrader.ps1" -ForegroundColor Cyan
Write-Host ""
