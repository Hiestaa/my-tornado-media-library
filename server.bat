@echo off
call "_internal\setenv.bat"

%PYTHON_EXECUTABLE% %SRC_DIR%\server_main.py -vv

pause