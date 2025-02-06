@echo off
setlocal EnableDelayedExpansion

echo [LOG] Starting ESP32 reflash script...

REM Initialize device array
set "index=0"
for /f "tokens=* usebackq" %%a in (`powershell -command "Get-CimInstance -ClassName Win32_PnPEntity | Where-Object { $_.Caption -match 'COM\d+' } | ForEach-Object { $_.Caption }"`) do (
    set /a "index+=1"
    set "deviceName[!index!]=%%a"
    echo [DEBUG] Processing device: %%a
    
    REM Extract COM port using regex
    set "fullName=%%a"
    echo [DEBUG] Full device string: !fullName!
    
    for /f "tokens=1,2 delims=()" %%b in ("!fullName!") do (
        set "devicePort[!index!]=%%c"
        echo [DEBUG] Extracted port: %%c from parentheses
        echo [LOG] Found device !index!: %%a [Port: %%c]
    )
)

echo [DEBUG] Total devices found: %index%

if %index% GTR 1 (
    echo Multiple ESP32 devices found. Please select one:
    for /l %%i in (1,1,%index%) do (
        echo %%i^) !deviceName[%%i]!
    )
    set /p "selection=Enter number (1-%index%): "
) else (
    set "selection=1"
)

set "COMPORT=!devicePort[%selection%]!"
echo [DEBUG] Selected port: !COMPORT!
echo [LOG] User selected device %selection%: !deviceName[%selection%]! [Port: !COMPORT!]

echo Using port: !COMPORT!
echo Erasing flash...
esptool --chip esp32 --port "!COMPORT!" erase_flash

echo Writing firmware...
esptool --chip esp32 --port "!COMPORT!" --baud 460800 write_flash 0x1000 "C:\Users\insilicon\Downloads\ESP32_GENERIC-20241129-v1.24.1 (1).bin"

echo Flashing ESP folder...
ampy --port "!COMPORT!" --baud 115200 put ./esp /