#!/usr/bin/env pwsh
# Bi-Directional Data Reconciliation Execution Script

param(
    [switch]$DryRun = $false,
    [switch]$Verbose = $false,
    [string]$BackupDir = ""
)

# Set error action preference
$ErrorActionPreference = "Stop"

Write-Host "=== Bi-Directional Reddit Data Reconciliation Script ===" -ForegroundColor Green
Write-Host "Started at: $(Get-Date)" -ForegroundColor Yellow

# Function to load environment variables from .env file
function Load-EnvFile {
    param([string]$EnvFilePath = ".env")
    
    if (-not (Test-Path $EnvFilePath)) {
        throw "Environment file not found: $EnvFilePath"
    }
    
    Get-Content $EnvFilePath | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            $value = $value -replace '^["'']|["'']$', ''
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
            Write-Verbose "Loaded env var: $name"
        }
    }
}

# Load environment variables from .env file
try {
    Load-EnvFile
    Write-Verbose "Environment variables loaded from .env file"
} catch {
    Write-Host "ERROR: Failed to load .env file: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Navigate to project root (script is now in reddit_scraper/scripts)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $ProjectRoot

# Create comprehensive backup if not in dry-run mode
if (-not $DryRun) {
    if ([string]::IsNullOrEmpty($BackupDir)) {
        $BackupDir = "reddit_scraper\reconciliation\backups\bidirectional_reconciliation_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss')"
    }
    
    Write-Host "Creating comprehensive backup in: $BackupDir" -ForegroundColor Yellow
    New-Item -Path $BackupDir -ItemType Directory -Force | Out-Null
    
    # Backup database
    Write-Host "Backing up TimescaleDB raw_events table..." -ForegroundColor Yellow
    docker-compose exec -T timescaledb pg_dump -U $env:PG_USER -d $env:PG_DB -t raw_events > "$BackupDir\raw_events_backup.sql"
    
    # Backup CSV file with timestamp
    Write-Host "Backing up CSV file..." -ForegroundColor Yellow
    Copy-Item "data\reddit_finance.csv" "$BackupDir\reddit_finance_backup.csv"
    
    # Create backup metadata
    $BackupInfo = @{
        timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        operation = "bi-directional-reconciliation"
        csv_size_bytes = (Get-Item "data\reddit_finance.csv").Length
        db_record_count = (docker-compose exec -T timescaledb psql -U $env:PG_USER -d $env:PG_DB -t -c "SELECT COUNT(*) FROM raw_events WHERE source = 'reddit';" | Out-String).Trim()
    }
    
    $BackupInfo | ConvertTo-Json | Out-File "$BackupDir\backup_metadata.json"
    Write-Host "Backup completed successfully" -ForegroundColor Green
    Write-Host "  - Database records: $($BackupInfo.db_record_count)" -ForegroundColor Cyan
    Write-Host "  - CSV size: $([math]::Round($BackupInfo.csv_size_bytes / 1MB, 2)) MB" -ForegroundColor Cyan
}

# Set environment variables
$env:PYTHONPATH = $ProjectRoot

# Pre-execution validation
Write-Host "Running pre-execution validation..." -ForegroundColor Yellow

# Check Docker services
$DockerStatus = docker-compose ps --services --filter "status=running"
if ($DockerStatus -notcontains "timescaledb") {
    Write-Host "ERROR: TimescaleDB service is not running" -ForegroundColor Red
    Write-Host "Please start services with: docker-compose up -d timescaledb" -ForegroundColor Yellow
    exit 1
}

# Check database connectivity
try {
    $DbTest = docker-compose exec -T timescaledb psql -U test_user -d sentiment_pipeline_db -c "\dt" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Database connection failed"
    }
    Write-Host "✓ Database connectivity verified" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Cannot connect to database: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Check CSV file
if (-not (Test-Path "data\reddit_finance.csv")) {
    Write-Host "ERROR: reddit_finance.csv not found in data directory" -ForegroundColor Red
    exit 1
}

$CsvSize = (Get-Item "data\reddit_finance.csv").Length
Write-Host "✓ CSV file found (Size: $([math]::Round($CsvSize / 1MB, 2)) MB)" -ForegroundColor Green

# Check Python dependencies
try {
    $PythonDeps = python -c "import pandas, sqlalchemy, psycopg2; print('Dependencies OK')" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Missing dependencies"
    }
    Write-Host "✓ Python dependencies verified" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Missing Python dependencies. Please run: pip install pandas sqlalchemy psycopg2-binary" -ForegroundColor Red
    exit 1
}

# Execute bi-directional reconciliation
Write-Host "Starting bi-directional reconciliation process..." -ForegroundColor Yellow

if ($DryRun) {
    Write-Host "DRY RUN MODE - Analysis only, no changes will be made" -ForegroundColor Magenta
    $env:RECONCILIATION_DRY_RUN = "true"
} else {
    Write-Host "LIVE MODE - Changes will be made to database and CSV" -ForegroundColor Green
    $env:RECONCILIATION_DRY_RUN = "false"
}

# Create output directory for logs and reports
$OutputDir = "reddit_scraper\reconciliation\outputs\reconciliation_output_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss')"
New-Item -Path $OutputDir -ItemType Directory -Force | Out-Null

try {
    $StartTime = Get-Date
    
    if ($Verbose) {
        $env:PYTHONUNBUFFERED = "1"
        python -m reddit_scraper.reconciliation.main | Tee-Object -FilePath "$OutputDir\reconciliation_verbose.log"
    } else {
        python -m reddit_scraper.reconciliation.main 2>&1 | Tee-Object -FilePath "$OutputDir\reconciliation.log"
    }
    
    $EndTime = Get-Date
    $Duration = $EndTime - $StartTime
    
    Write-Host "Bi-directional reconciliation completed successfully!" -ForegroundColor Green
    Write-Host "Processing time: $($Duration.TotalMinutes.ToString('F2')) minutes" -ForegroundColor Cyan
    
    # Post-execution validation
    Write-Host "Running post-execution validation..." -ForegroundColor Yellow
    
    # Check for reconciliation report in reddit_scraper/reconciliation/outputs
    $ReportFiles = @()
    $ReportFiles += Get-ChildItem "bidirectional_reconciliation_report_*.json" -ErrorAction SilentlyContinue
    $ReportFiles += Get-ChildItem "reconciliation\bidirectional_reconciliation_report_*.json" -ErrorAction SilentlyContinue
    $ReportFiles += Get-ChildItem "reddit_scraper\reconciliation\outputs\bidirectional_reconciliation_report_*.json" -ErrorAction SilentlyContinue
    $ReportFiles = $ReportFiles | Sort-Object LastWriteTime -Descending
    
    if ($ReportFiles.Count -gt 0) {
        $LatestReport = $ReportFiles[0]
        if ($LatestReport.DirectoryName -ne (Resolve-Path $OutputDir).Path) {
            Move-Item $LatestReport.FullName "$OutputDir\"
        }
        
        $ReportContent = Get-Content "$OutputDir\$($LatestReport.Name)" | ConvertFrom-Json
        
        Write-Host "✓ Reconciliation report generated" -ForegroundColor Green
        Write-Host "Summary of operations performed:" -ForegroundColor Cyan
        Write-Host "  - Records inserted to DB: $($ReportContent.statistics.records_inserted_to_db)" -ForegroundColor White
        Write-Host "  - Records exported to CSV: $($ReportContent.statistics.records_exported_to_csv)" -ForegroundColor White
        Write-Host "  - Conflicts resolved: $($ReportContent.statistics.conflicts_resolved)" -ForegroundColor White
        Write-Host "  - Processing time: $($ReportContent.statistics.processing_time_seconds) seconds" -ForegroundColor White
        Write-Host "  - Synchronization coverage: $($ReportContent.data_quality.synchronization_coverage)%" -ForegroundColor White
    }
    
    # Verify data consistency
    Write-Host "Verifying bi-directional synchronization..." -ForegroundColor Yellow
    
    $PostDbCount = (docker-compose exec -T timescaledb psql -U test_user -d sentiment_pipeline_db -t -c "SELECT COUNT(*) FROM raw_events WHERE source = 'reddit';" | Out-String).Trim()
    $PostCsvCount = (python -c "import pandas as pd; df = pd.read_csv('data/reddit_finance.csv'); print(len(df))" 2>&1)
    
    Write-Host "Post-reconciliation counts:" -ForegroundColor Cyan
    Write-Host "  - Database records: $PostDbCount" -ForegroundColor White
    Write-Host "  - CSV records: $PostCsvCount" -ForegroundColor White
    
    # Move logs to output directory
    Get-ChildItem "bidirectional_reconciliation_*.log" -ErrorAction SilentlyContinue | Move-Item -Destination $OutputDir -ErrorAction SilentlyContinue
    Get-ChildItem "reconciliation\bidirectional_reconciliation_*.log" -ErrorAction SilentlyContinue | Move-Item -Destination $OutputDir -ErrorAction SilentlyContinue
    Get-ChildItem "reddit_scraper\reconciliation\outputs\bidirectional_reconciliation_*.log" -ErrorAction SilentlyContinue | Move-Item -Destination $OutputDir -ErrorAction SilentlyContinue
    
    Write-Host "All outputs saved to: $OutputDir" -ForegroundColor Green
    
} catch {
    Write-Host "Bi-directional reconciliation failed: $($_.Exception.Message)" -ForegroundColor Red
    
    if (-not $DryRun -and (Test-Path $BackupDir)) {
        Write-Host "Backup available for restoration at: $BackupDir" -ForegroundColor Yellow
        Write-Host "To restore database, run:" -ForegroundColor Yellow
        Write-Host "  docker-compose exec -T timescaledb psql -U $env:PG_USER -d $env:PG_DB < $BackupDir\raw_events_backup.sql" -ForegroundColor Cyan
        Write-Host "To restore CSV, run:" -ForegroundColor Yellow
        Write-Host "  Copy-Item '$BackupDir\reddit_finance_backup.csv' 'data\reddit_finance.csv'" -ForegroundColor Cyan
    }
    
    # Save error logs
    if (Test-Path $OutputDir) {
        Get-ChildItem "bidirectional_reconciliation_*.log" -ErrorAction SilentlyContinue | Move-Item -Destination $OutputDir -ErrorAction SilentlyContinue
        Get-ChildItem "reconciliation\bidirectional_reconciliation_*.log" -ErrorAction SilentlyContinue | Move-Item -Destination $OutputDir -ErrorAction SilentlyContinue
        Get-ChildItem "reddit_scraper\reconciliation\outputs\bidirectional_reconciliation_*.log" -ErrorAction SilentlyContinue | Move-Item -Destination $OutputDir -ErrorAction SilentlyContinue
        Write-Host "Error logs saved to: $OutputDir" -ForegroundColor Yellow
    }
    
    exit 1
}

Write-Host "=== Bi-Directional Reconciliation Complete ===" -ForegroundColor Green
Write-Host "Finished at: $(Get-Date)" -ForegroundColor Yellow

# Cleanup old backup directories (keep last 5)
Write-Host "Cleaning up old backups..." -ForegroundColor Yellow
$OldBackups = Get-ChildItem "reddit_scraper\reconciliation\backups\bidirectional_reconciliation_*" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -Skip 5
if ($OldBackups.Count -gt 0) {
    $OldBackups | Remove-Item -Recurse -Force
    Write-Host "Removed $($OldBackups.Count) old backup directories" -ForegroundColor Cyan
}

Write-Host "Bi-directional reconciliation process completed successfully!" -ForegroundColor Green
