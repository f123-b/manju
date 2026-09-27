@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0package-preview.ps1"
if not "%ERRORLEVEL%"=="0" (
  echo.
  echo Short Drama OS preview package failed. Error code: %ERRORLEVEL%
  pause
)
endlocal
