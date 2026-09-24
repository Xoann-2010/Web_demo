@echo off
chcp 65001 >nul
cd /d "%~dp0"
title He Thong Do Goc Co Lam Sang - Danh Cho Bac Si
color 1F

echo.
echo  ==============================================================
echo.
echo     HỆ THỐNG ĐO GÓC CÚI/NGHIÊNG ĐẦU LÂM SÀNG [CROM]
echo     Phần mềm dành cho Bác sĩ và Kỹ thuật viên Phục hồi Chức năng
echo.
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
    echo  [LỖI] Không tìm thấy Python trên máy tính!
    echo  Vui lòng cài đặt Python [phiên bản 3.10 trở lên] để sử dụng phần mềm.
    echo  Lưu ý nhớ tích chọn 'Add Python to PATH' khi cài đặt.
    echo.
    pause
    exit /b 1
)

:: Giai phong cong 5000 neu co tien trinh cu bi treo
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo  [1/2] Đang khởi động máy chủ Web y tế...
echo  [Trình duyệt Chrome / Edge sẽ tự động mở sau vài giây]
echo.

:: Mo trinh duyet sau 2 giay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: Chay ung dung Python
%PY_CMD% app.py

echo.
echo  ==============================================================
echo   Hệ thống đã dừng. Nhấn phím bất kỳ để đóng cửa sổ.
echo  ==============================================================
pause >nul
