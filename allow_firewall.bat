@echo off
echo Adding Firewall Rules for DawarElOmda System...
echo Requesting Admin Privileges...

net session >nul 2>&1
if %errorLevel% == 0 (
    echo Admin privileges confirmed.
) else (
    echo Please right-click and run as Administrator.
    pause
    exit
)

echo Adding rule for Port 3000 (Main Server)...
netsh advfirewall firewall add rule name="DawarElOmda Main" dir=in action=allow protocol=TCP localport=3000

echo Adding rule for Port 3001 (Tablet Server)...
netsh advfirewall firewall add rule name="DawarElOmda Tablet" dir=in action=allow protocol=TCP localport=3001

echo.
echo Rules added successfully!
echo You can now access the system from other devices.
echo Main: http://[YOUR_IP]:3000
echo Tablet: http://[YOUR_IP]:3001/tablet
echo.
pause
