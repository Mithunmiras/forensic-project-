@echo off
rem One command to run RetailIQ. Prepares anything missing, starts the server and opens the browser.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
