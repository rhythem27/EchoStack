# EchoStack Development Startup Script
# Verifies environment and boots all services

$ErrorActionPreference = "Stop"

# Helper function to print headers
function Write-Header ($text) {
    Write-Host "`n=== $text ===" -ForegroundColor Cyan
}

# Helper function to print errors and pause
function Handle-Error ($msg, $exception) {
    Write-Host "`n[ERROR] $msg" -ForegroundColor Red
    if ($exception) {
        Write-Host $exception -ForegroundColor DarkRed
    }
    Write-Host "`nPress any key to exit..." -ForegroundColor Yellow
    [void]$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

try {
    Write-Header "Checking Docker Daemon"
    Write-Host "Verifying that Docker is running..." -ForegroundColor Gray
    
    # Run docker info and capture output & error to prevent console spam
    $dockerCheck = & docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon is not running or docker command is not available. Please make sure Docker Desktop is running."
    }
    Write-Host "Docker daemon is running!" -ForegroundColor Green
} catch {
    Handle-Error "Docker check failed." $_
}

try {
    Write-Header "Starting Docker Infrastructure Containers"
    Write-Host "Running: docker compose up -d postgres redis kafka" -ForegroundColor Gray
    & docker compose up -d postgres redis kafka
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start Docker containers via docker compose."
    }
    Write-Host "Infrastructure containers started successfully." -ForegroundColor Green
} catch {
    Handle-Error "Docker Compose failed." $_
}

try {
    Write-Header "Checking Backend Python Dependencies"
    Write-Host "Running: poetry install" -ForegroundColor Gray
    & poetry install
    if ($LASTEXITCODE -ne 0) {
        throw "Poetry install failed. Make sure Poetry is installed and configured."
    }
    Write-Host "Python dependencies up to date." -ForegroundColor Green
} catch {
    Handle-Error "Python dependency setup failed." $_
}

try {
    Write-Header "Checking Frontend Node Dependencies"
    $frontendDir = Join-Path $PSScriptRoot "frontend"
    $nodeModulesDir = Join-Path $frontendDir "node_modules"

    if (-not (Test-Path $nodeModulesDir)) {
        Write-Host "node_modules not found in frontend directory. Running npm install..." -ForegroundColor Yellow
        
        # Save current directory, move to frontend, run npm install, then restore directory
        $currentDir = Get-Location
        Set-Location $frontendDir
        & npm install
        $npmExit = $LASTEXITCODE
        Set-Location $currentDir
        
        if ($npmExit -ne 0) {
            throw "npm install failed in frontend directory. Make sure Node.js and npm are installed."
        }
        Write-Host "Node dependencies installed successfully." -ForegroundColor Green
    } else {
        Write-Host "Node dependencies already installed." -ForegroundColor Green
    }
} catch {
    Handle-Error "Frontend dependency setup failed." $_
}

# Define local environment variable overrides
$envOverrides = @{
    DATABASE_URL = "postgresql://postgres_user:postgres_secure_password@localhost:5432/echostack_db"
    REDIS_URL = "redis://localhost:6379/0"
    KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
}

# Construct environment setting commands for powershell
$envPrefix = ""
foreach ($key in $envOverrides.Keys) {
    $val = $envOverrides[$key]
    $envPrefix += "`$env:$key='$val'; "
}

# Commands to run
$backendCmd = "${envPrefix}`$host.UI.RawUI.WindowTitle='EchoStack Backend API'; poetry run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
$workerCmd = "${envPrefix}`$host.UI.RawUI.WindowTitle='EchoStack Ingestion Worker'; poetry run python backend/worker.py"
$frontendCmd = "`$host.UI.RawUI.WindowTitle='EchoStack Frontend'; npm run dev"

Write-Header "Launching Applications"

# Detect if Windows Terminal is available
$hasWt = $null -ne (Get-Command wt -ErrorAction SilentlyContinue)

if ($hasWt) {
    Write-Host "Windows Terminal detected. Launching processes in tabs..." -ForegroundColor Green
    
    # Run wt.exe using Start-Process with array arguments to bypass semicolon parsing issues
    $wtArgs = @(
        "-d", "$PSScriptRoot",
        "powershell", "-NoExit", "-Command", $backendCmd,
        ";", "new-tab", "-d", "$PSScriptRoot",
        "powershell", "-NoExit", "-Command", $workerCmd,
        ";", "new-tab", "-d", "$PSScriptRoot\frontend",
        "powershell", "-NoExit", "-Command", $frontendCmd
    )
    
    Start-Process wt -ArgumentList $wtArgs
} else {
    Write-Host "Windows Terminal not found. Launching processes in separate PowerShell windows..." -ForegroundColor Yellow
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WorkingDirectory $PSScriptRoot
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $workerCmd -WorkingDirectory $PSScriptRoot
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WorkingDirectory "$PSScriptRoot\frontend"
}

Write-Header "EchoStack Startup Successful!"
Write-Host "You can access the project using the links below:" -ForegroundColor Gray
Write-Host ""
Write-Host "  > Frontend Client: " -NoNewline -ForegroundColor Gray
Write-Host "http://localhost:5173" -ForegroundColor Green
Write-Host "  > Backend API:     " -NoNewline -ForegroundColor Gray
Write-Host "http://localhost:8000" -ForegroundColor Green
Write-Host "  > FastAPI Docs:    " -NoNewline -ForegroundColor Gray
Write-Host "http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "All processes have been started in separate terminals/tabs." -ForegroundColor Cyan
Write-Host "Feel free to close this startup console now." -ForegroundColor DarkGray
Write-Host ""
