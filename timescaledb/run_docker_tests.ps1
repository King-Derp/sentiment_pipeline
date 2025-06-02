# PowerShell script to run TimescaleDB integration tests in Docker
# This script handles the full lifecycle of the test environment and runs the tests

# Load environment variables from .env.test
$envFilePath = Join-Path -Path $PSScriptRoot -ChildPath "..\.env.test"
if (Test-Path $envFilePath) {
    Write-Host "Loading environment variables from $envFilePath" -ForegroundColor Cyan
    Get-Content $envFilePath | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
            Write-Host "Loaded env var: $key" -ForegroundColor Gray
        }
    }
} else {
    Write-Error ".env.test file not found in parent directory. Please create it with the necessary environment variables."
    exit 1
}

# Verify that required environment variables are set
$requiredVars = @("TEST_PG_USER", "TEST_PG_PASSWORD", "TEST_PG_DB", "TEST_PG_PORT_HOST", "TEST_DATABASE_URL")
foreach ($var in $requiredVars) {
    if (-not [Environment]::GetEnvironmentVariable($var)) {
        Write-Error "Required environment variable $var is not set in .env.test"
        exit 1
    }
}

# Display the test environment configuration
Write-Host "TimescaleDB Docker Test Environment Configuration:" -ForegroundColor Cyan
Write-Host "  Database URL: $TEST_DATABASE_URL" -ForegroundColor Yellow

# Start test containers
Write-Host "Starting TimescaleDB test container..." -ForegroundColor Cyan
$composePath = Join-Path -Path $PSScriptRoot -ChildPath "..\docker-compose.test.yml"
docker-compose -f $composePath up -d --remove-orphans

# Wait for database to be ready
Write-Host "Waiting for TimescaleDB test container to be healthy..." -ForegroundColor Cyan
$attempts = 0
$max_attempts = 30
while ($attempts -lt $max_attempts) {
    $health = docker inspect --format='{{.State.Health.Status}}' timescaledb_test_service 2>$null
    if ($health -eq "healthy") {
        Write-Host "TimescaleDB test container is healthy!" -ForegroundColor Green
        break
    }
    Write-Host "Waiting for TimescaleDB test container to be ready... ($($attempts+1)/$max_attempts)"
    Start-Sleep -Seconds 2
    $attempts++
}

if ($attempts -eq $max_attempts) {
    Write-Error "TimescaleDB test container failed to become healthy"
    docker-compose -f $composePath down --remove-orphans
    exit 1
}

# Construct TEST_DATABASE_URL from loaded env vars (needed for Alembic and tests)
$env:TEST_DATABASE_URL = "postgresql://$($env:TEST_PG_USER):$($env:TEST_PG_PASSWORD)@localhost:$($env:TEST_PG_PORT_HOST)/$($env:TEST_PG_DB)"
Write-Host "Constructed TEST_DATABASE_URL for Alembic/Tests: $($env:TEST_DATABASE_URL)" -ForegroundColor Yellow

# Apply Alembic migrations
Write-Host "Applying Alembic migrations..." -ForegroundColor Cyan
Push-Location "..\"
$env:ALEMBIC_CONFIG = "alembic.ini" # Ensure Alembic uses the correct config
$env:ALEMBIC_DATABASE_URL = $env:TEST_DATABASE_URL # Set for Alembic
try {
    Write-Host "Running: alembic upgrade head" -ForegroundColor Yellow
    $tempLogFile = New-TemporaryFile
    alembic upgrade head *> $tempLogFile.FullName # Corrected redirection for all output
    $alembicExitCode = $LASTEXITCODE
    $alembicLogContent = Get-Content $tempLogFile.FullName -Raw

    if ($alembicExitCode -ne 0) {
        Write-Error "Alembic migrations failed! Exit code: $alembicExitCode"
        Write-Host "Alembic Output:" -ForegroundColor Red
        Write-Host "$alembicLogContent" -ForegroundColor Red
        docker-compose -f $composePath down --remove-orphans
        Remove-Item $tempLogFile.FullName -Force
        exit 1
    }
    Write-Host "Alembic migrations applied successfully." -ForegroundColor Green
    if ($alembicLogContent) {
        Write-Host "Alembic Output (Success):"
        Write-Host "$alembicLogContent"
    }
    Remove-Item $tempLogFile.FullName -Force
} catch {
    Write-Error "Error running Alembic migrations: $_"
    docker-compose -f $composePath down --remove-orphans
    exit 1
} finally {
    Pop-Location
}

# Environment variables for tests (TEST_DATABASE_URL already set)
Write-Host "Using TEST_DATABASE_URL for Pytest: $env:TEST_DATABASE_URL" -ForegroundColor Yellow

# Run the tests
Write-Host "Running integration tests..." -ForegroundColor Cyan
try {
    # Parse command line arguments
    $pytestTarget = if ($args.Count -gt 0) {
        $args[0] # e.g., user provides a specific test file
    } else {
        "." # Default to running all tests in the current directory
    }
    
    Write-Host "Running pytest with target: $pytestTarget" -ForegroundColor Yellow
    
    # Use the correct path to tests directory
    $testsDir = Join-Path -Path $PSScriptRoot -ChildPath "tests"
    if (-not (Test-Path $testsDir)) {
        Write-Error "Tests directory not found at: $testsDir"
        docker-compose -f $composePath down --remove-orphans
        exit 1
    }
    
    # Run pytest and show output directly in the console
    Push-Location (Join-Path -Path $PSScriptRoot -ChildPath "tests")
    python -m pytest $pytestTarget -v
    $testResult = $LASTEXITCODE
    Pop-Location
    
    if ($testResult -eq 0) {
        Write-Host "Integration tests completed successfully!" -ForegroundColor Green
    } else {
        Write-Host "Integration tests failed with exit code $testResult" -ForegroundColor Red
    }
} 
catch {
    Write-Error "Error running tests: $_"
    $testResult = 1
}
finally {
    # Cleanup
    Write-Host "Cleaning up test containers..." -ForegroundColor Cyan
    docker-compose -f $composePath down --remove-orphans
    
    # Return the test result
    exit $testResult
}
