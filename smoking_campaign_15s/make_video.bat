@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title 15초 금연 홍보 영상 만들기

echo ==================================================
echo    15초 금연 홍보 영상 자동 제작
echo ==================================================
echo.

rem ---- 1. Python 찾기 -----------------------------------------
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if defined PY goto :have_python
python --version >nul 2>nul && set "PY=python"
if defined PY goto :have_python
echo [오류] Python을 찾지 못했습니다.
echo.
echo   1. https://www.python.org/downloads/ 에서 Python을 내려받아 설치하세요.
echo   2. 설치 첫 화면 아래쪽의 "Add python.exe to PATH" 를 반드시 체크하세요.
echo   3. 설치가 끝나면 이 파일을 다시 더블클릭하세요.
echo.
echo   자세한 안내는 README.md 를 보세요.
goto :end

:have_python
for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo Python 확인: %%v

rem ---- 2. Pillow 확인 - 설치는 사용자가 동의할 때만 ----------------
%PY% -c "import PIL" >nul 2>nul
if not errorlevel 1 goto :have_pillow
echo.
echo 그림을 만드는 Python 라이브러리 Pillow 가 설치되어 있지 않습니다.
echo 설치 명령: %PY% -m pip install --user Pillow
echo 현재 사용자 계정에만 설치되며, 시스템 설정은 바꾸지 않습니다.
echo.
choice /c YN /m "지금 설치할까요"
if errorlevel 2 goto :no_pillow
%PY% -m pip install --user Pillow
if errorlevel 1 goto :pillow_failed
goto :have_pillow

:no_pillow
echo.
echo 설치하지 않았습니다. Pillow 없이는 영상을 만들 수 없습니다.
echo 준비가 되면 이 파일을 다시 실행하세요.
goto :end

:pillow_failed
echo.
echo [오류] Pillow 설치에 실패했습니다. 인터넷 연결을 확인한 뒤 다시 실행하세요.
goto :end

:have_pillow
echo Pillow 확인: 설치됨
echo.

rem ---- 3. 영상 제작 - FFmpeg와 폰트 점검은 make_video.py 가 합니다 ----
%PY% make_video.py
if errorlevel 2 goto :partial
if errorlevel 1 goto :partial
echo.
echo 영상은 만들어졌지만 일부 검증 항목이 기준과 다릅니다. 위 목록의 X 표시를 확인하세요.
start "" "%~dp0output"
goto :end

:failed
echo.
echo 결과 폴더를 엽니다.
start "" "%~dp0output"
goto :end

:failed
echo.
echo 영상 제작이 끝나지 않았습니다. 위의 [오류] 와 [해결 방법] 을 확인하세요.

:end
echo.
pause
endlocal
