@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Cai Dat Moi Truong - He Thong Do Goc Co CROM
color 0B

echo.
echo  ==============================================================
echo     CÀI ĐẶT MÔI TRƯỜNG & THƯ VIỆN CHO HỆ THỐNG ĐO GÓC CỔ
echo  ==============================================================
echo.

:: Tim kiem trinh thong dich Python
set "PY_CMD="
python --version >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD (
    py --version >nul 2>&1 && set "PY_CMD=py"
)
if not defined PY_CMD (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%D\python.exe" set "PY_CMD=%%D\python.exe"
    )
)

if not defined PY_CMD (
    echo  [LỖI] Không tìm thấy Python trên máy tính của bạn!
    echo.
    echo  BƯỚC CẦN LÀM:
    echo  1. Truy cập https://www.python.org/downloads/
    echo  2. Tải và cài đặt Python (phiên bản 3.10 trở lên, khuyến nghị 3.11 hoặc 3.12).
    echo  3. QUAN TRỌNG: Khi chạy cài đặt, nhớ TÍCH CHỌN vào ô:
    echo     "[X] Add python.exe to PATH"
    echo  4. Sau khi cài Python xong, chạy lại file này!
    echo.
    pause
    exit /b 1
)

echo  [OK] Đã tìm thấy Python:
%PY_CMD% --version
echo.
echo  Đang tiến hành cài đặt các gói thư viện (Flask, SocketIO, Bleak, NumPy, Pandas)...
echo  Vui lòng giữ kết nối Internet...
echo.

%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install -r "%~dp0requirements.txt"

if errorlevel 1 (
    echo.
    echo  [LỖI] Cài đặt thư viện thất bại! Vui lòng kiểm tra lại mạng Internet.
    echo.
    pause
    exit /b 1
)

echo.
echo  ==============================================================
echo   CHÚC MỪNG: ĐÃ CÀI ĐẶT THÀNH CÔNG TẤT CẢ THƯ VIỆN CẦN THIẾT!
echo   Bây giờ bạn chỉ cần nhấp đúp vào "Mo_Phan_Mem.bat" để sử dụng.
echo  ==============================================================
echo.
pause
