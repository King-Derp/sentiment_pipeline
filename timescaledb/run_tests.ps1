# PowerShell script to run TimescaleDB tests with environment variables set
# This script is for running tests against an already running TimescaleDB container
# If container is not running, it will start one using run_docker_tests.ps1

# Parse command line arguments
param(
    [string]$TestTarget = "tests"  # Default to running all tests
)

# Display header
Write-Host "Running TimescaleDB Integration Tests" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan

# First, check if the Docker container is running
$containerRunning = docker ps --filter "name=timescaledb_test_service" --format "{{.Names}}"

if ($containerRunning -ne "timescaledb_test_service") {
    Write-Host "TimescaleDB test container is not running. Starting it using run_docker_tests.ps1..." -ForegroundColor Yellow
    
    # Call the run_docker_tests.ps1 script with our specific test target
    & "$PSScriptRoot\run_docker_tests.ps1" $TestTarget
    exit $LASTEXITCODE
} else {
    Write-Host "TimescaleDB test container is already running." -ForegroundColor Green
    
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
        # Fallback to hardcoded values if .env.test doesn't exist
        Write-Host "No .env.test found, using default test environment variables" -ForegroundColor Yellow
        $env:TEST_PG_USER = "test_user"
        $env:TEST_PG_PASSWORD = "test_password"
        $env:TEST_PG_DB = "sentiment_pipeline_test_db"
        $env:TEST_PG_PORT_HOST = "5434"
        $env:TEST_PG_HOST = "localhost"
    }

    # Construct TEST_DATABASE_URL from loaded env vars
    $env:TEST_DATABASE_URL = "postgresql://$($env:TEST_PG_USER):$($env:TEST_PG_PASSWORD)@$($env:TEST_PG_HOST):$($env:TEST_PG_PORT_HOST)/$($env:TEST_PG_DB)"

    # Display the test environment configuration
    Write-Host "TimescaleDB Test Environment Configuration:" -ForegroundColor Cyan
    Write-Host "  Database URL: $($env:TEST_DATABASE_URL)" -ForegroundColor Yellow

    # Run the tests with pytest
    Write-Host "Running tests with target: $TestTarget..." -ForegroundColor Cyan
    Push-Location (Join-Path -Path $PSScriptRoot -ChildPath "tests")
    python -m pytest $TestTarget -v
    $testResult = $LASTEXITCODE
    Pop-Location
    
    if ($testResult -eq 0) {
        Write-Host "Tests completed successfully!" -ForegroundColor Green
    } else {
        Write-Host "Tests failed with exit code $testResult" -ForegroundColor Red
    }
    
    # Return the exit code from pytest
    exit $testResult
}
