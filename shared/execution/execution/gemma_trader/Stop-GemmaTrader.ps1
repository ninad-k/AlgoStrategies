# ═══════════════════════════════════════════════════════════════════════════════
#  Rey Capital - Gemma Trader Stop Script
#  Gracefully shut down the trading bot and cleanup
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [switch]$Force,
    [switch]$KillOllama,
    [int]$WaitSeconds = 10
)

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProcessFile = Join-Path $AppDir ".trader_pid.txt"
$LogsDir = Join-Path $AppDir "logs"

# ─────────────────────────────────────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

function Write-Banner {
    Write-Host ""
    Write-Host "  ╔═══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║        REY CAPITAL - GEMMA TRADER SHUTDOWN            ║" -ForegroundColor Cyan
    Write-Host "  ║        Graceful Termination                           ║" -ForegroundColor Cyan
    Write-Host "  ╚═══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Status {
    param([string]$Label, [string]$Status, [string]$Detail)
    $color = switch ($Status) {
        "OK"      { "Green"  }
        "WARN"    { "Yellow" }
        "FAIL"    { "Red"    }
        "INFO"    { "Cyan"   }
        default   { "White"  }
    }
    $icon = switch ($Status) {
        "OK"   { "[✓]" }
        "WARN" { "[!]" }
        "FAIL" { "[✗]" }
        "INFO" { "[i]" }
        default{ "   " }
    }
    Write-Host "  $icon " -ForegroundColor $color -NoNewline
    Write-Host "$Label " -NoNewline
    if ($Detail) { Write-Host "- $Detail" -ForegroundColor DarkGray } else { Write-Host "" }
}

# ─────────────────────────────────────────────────────────────────────────────
#  1. FIND PYTHON PROCESSES
# ─────────────────────────────────────────────────────────────────────────────

Write-Banner

Write-Host "  STOPPING GEMMA TRADER" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

Write-Status "Scan" "INFO" "Looking for Gemma Trader processes..."

# Look for Python processes running run.py from the app directory
$processes = @()

try {
    $allPythonProcs = Get-Process -Name "python*" -ErrorAction SilentlyContinue

    if ($allPythonProcs) {
        foreach ($proc in $allPythonProcs) {
            try {
                $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
                if ($cmdLine -and $cmdLine -like "*run.py*" -and $cmdLine -like "*$AppDir*") {
                    $processes += $proc
                }
            } catch {
                # Skip if we can't get command line
            }
        }
    }
} catch {
    Write-Status "Scan" "WARN" "Could not enumerate processes"
}

# Also check by reading PID file
if (Test-Path $ProcessFile) {
    try {
        $pidContent = Get-Content $ProcessFile -Raw -ErrorAction SilentlyContinue
        $storedPid = [int]$pidContent.Trim()

        $storedProc = Get-Process -Id $storedPid -ErrorAction SilentlyContinue
        if ($storedProc) {
            if ($processes -notcontains $storedProc) {
                $processes += $storedProc
            }
        }
    } catch {
        # PID file may be stale
    }
}

if ($processes.Count -eq 0) {
    Write-Status "Scan" "WARN" "No running Gemma Trader process found"
    Write-Host ""
    Write-Host "  The application may not be running, or it was started differently." -ForegroundColor Yellow
    Write-Host "  You can also press Ctrl+C in the terminal where it's running." -ForegroundColor Yellow
    Write-Host ""
    exit 0
} else {
    Write-Status "Found" "OK" "$($processes.Count) process(es) to stop"
}

Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
#  2. ATTEMPT GRACEFUL SHUTDOWN
# ─────────────────────────────────────────────────────────────────────────────

if (-not $Force) {
    Write-Host "  GRACEFUL SHUTDOWN (waiting $WaitSeconds seconds)" -ForegroundColor White
    Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    foreach ($proc in $processes) {
        Write-Status "Process" "INFO" "Stopping PID $($proc.Id)..."

        try {
            # Try to terminate gracefully
            $proc.CloseMainWindow() | Out-Null
            $waited = 0

            # Wait for process to exit
            while (-not $proc.HasExited -and $waited -lt $WaitSeconds) {
                Start-Sleep -Seconds 1
                $waited++
                Write-Host "    Waiting... $waited/$WaitSeconds`r" -NoNewline
            }

            if ($proc.HasExited) {
                Write-Status "Process" "OK" "Gracefully stopped (PID $($proc.Id))"
            } else {
                Write-Status "Process" "WARN" "Did not exit gracefully, will force kill"
                $Force = $true
            }
        } catch {
            Write-Status "Process" "WARN" "Error during graceful shutdown: $_"
            $Force = $true
        }
    }

    Write-Host ""
}

# ─────────────────────────────────────────────────────────────────────────────
#  3. FORCE KILL IF NEEDED
# ─────────────────────────────────────────────────────────────────────────────

if ($Force) {
    Write-Host "  FORCE TERMINATION" -ForegroundColor White
    Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    foreach ($proc in $processes) {
        if (-not $proc.HasExited) {
            try {
                Stop-Process -Id $proc.Id -Force -ErrorAction Stop
                Write-Status "Process" "OK" "Force killed (PID $($proc.Id))"
            } catch {
                Write-Status "Process" "FAIL" "Could not kill PID $($proc.Id): $_"
            }
        }
    }

    Write-Host ""
}

# ─────────────────────────────────────────────────────────────────────────────
#  4. OPTIONAL: STOP OLLAMA
# ─────────────────────────────────────────────────────────────────────────────

if ($KillOllama) {
    Write-Host "  OPTIONAL: STOPPING OLLAMA" -ForegroundColor White
    Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    $ollamaProcs = Get-Process -Name "ollama" -ErrorAction SilentlyContinue

    if ($ollamaProcs) {
        foreach ($proc in $ollamaProcs) {
            Write-Status "Ollama" "INFO" "Stopping (PID $($proc.Id))..."
            $proc.CloseMainWindow() | Out-Null
            Start-Sleep -Seconds 2

            if (-not $proc.HasExited) {
                try {
                    Stop-Process -Id $proc.Id -Force -ErrorAction Stop
                    Write-Status "Ollama" "OK" "Stopped"
                } catch {
                    Write-Status "Ollama" "WARN" "Could not stop"
                }
            } else {
                Write-Status "Ollama" "OK" "Gracefully stopped"
            }
        }
    } else {
        Write-Status "Ollama" "INFO" "Not running"
    }

    Write-Host ""
}

# ─────────────────────────────────────────────────────────────────────────────
#  5. CLEANUP
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "  CLEANUP" -ForegroundColor White
Write-Host "  ────────────────────────────────────────────────────────" -ForegroundColor DarkGray

if (Test-Path $ProcessFile) {
    try {
        Remove-Item $ProcessFile -Force
        Write-Status "Cleanup" "OK" "PID file removed"
    } catch {
        Write-Status "Cleanup" "WARN" "Could not remove PID file"
    }
}

Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
#  6. SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "  ╔═══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║              SHUTDOWN COMPLETE                        ║" -ForegroundColor Green
Write-Host "  ╚═══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  • Review logs at: $LogsDir" -ForegroundColor Cyan
Write-Host "  • Start again with: .\Run-GemmaTrader.ps1" -ForegroundColor Cyan
Write-Host ""
