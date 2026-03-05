@echo off
REM NEXUS Agent Orchestrator Setup

echo ========================================
echo NEXUS Agent Orchestrator Setup
echo ========================================
echo.

REM Install dependencies
echo Installing dependencies...
pip install anthropic requests
echo.

REM Check for API key
echo Checking for ANTHROPIC_API_KEY...
if "%ANTHROPIC_API_KEY%"=="" (
    echo.
    echo WARNING: ANTHROPIC_API_KEY not set!
    echo.
    echo To set your API key:
    echo   1. Get your key from: https://console.anthropic.com/
    echo   2. Run: setx ANTHROPIC_API_KEY "your-api-key-here"
    echo   3. Restart this terminal
    echo.
) else (
    echo ✓ API key is set
)

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo To run an agent orchestrator:
echo   python E:\NEXUS_V2_RECREATED\tools\agent_orchestrator.py LOUIE
echo   python E:\NEXUS_V2_RECREATED\tools\agent_orchestrator.py CLOUSE
echo   python E:\NEXUS_V2_RECREATED\tools\agent_orchestrator.py MENDEL
echo   python E:\NEXUS_V2_RECREATED\tools\agent_orchestrator.py JAQUES
echo.
pause
