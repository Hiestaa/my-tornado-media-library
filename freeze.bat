@echo off
call "_internal\setenv.bat"

%PYTHON_EXECUTABLE% -m pip freeze > requirements.txt

pause