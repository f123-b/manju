@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch-preview.ps1"
if not "%ERRORLEVEL%"=="0" (
  echo.
  echo Short Drama OS preview failed to start. Error code: %ERRORLEVEL%
  pause
)
endlocal
