esptool --port COM3 erase_flash
esptool --port COM3 --baud 460800 write_flash 0x1000 "C:\Users\insilicon\Downloads\ESP32_GENERIC-20241129-v1.24.1 (1).bin"
./flash.bat