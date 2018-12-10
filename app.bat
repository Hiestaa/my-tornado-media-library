@echo off
call "_internal\setenv.bat"

%PYTHON_EXECUTABLE% %SRC_DIR%\main.py -vv

pause