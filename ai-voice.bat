@echo off
echo ===============================
echo Starting Flask App
echo ===============================

echo.
echo.


echo ===============================
echo Activating virtual environment...
call .venv\Scripts\activate
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to activate virtual environment
    exit /b 1
)


echo Virtual environment activated
echo ===============================

echo.
echo.


echo ===============================
echo Running Flask app...

echo Starting the application...
start http://127.0.0.1:5000


python app.py


IF %ERRORLEVEL% NEQ 0 (
    echo Failed to start app.py
    exit /b 1
)

echo Flask app stopped
echo ===============================


echo.
echo.

echo --------------------------------
echo Press any key to exit
pause
echo --------------------------------