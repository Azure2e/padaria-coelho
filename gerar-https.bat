@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist api\tls mkdir api\tls
where openssl >nul 2>&1
if %errorlevel%==0 goto GERAR
echo OpenSSL nao encontrado.
echo Instale Git for Windows ou use o site em HTTP:
echo   py -3 api\servidor.py
pause
goto :eof
:GERAR
openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes -keyout api\tls\key.pem -out api\tls\cert.pem -subj "/CN=localhost/O=Padaria Coelho/C=BR"
echo Certificado criado. Depois rode:
echo   set COELHO_HTTPS=1
echo   py -3 api\servidor.py
pause
