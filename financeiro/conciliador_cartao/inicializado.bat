@echo off
chcp 65001 > nul
title Servidor - Conciliador de Cartão de Crédito

:: Entra na pasta onde este arquivo .bat está salvo
cd /d "%~dp0"

echo ========================================================
echo   INICIANDO CONCILIADOR DE FATURA NA REDE LOCAL
echo ========================================================
echo.
echo Para acessar de outros computadores na mesma rede:
echo Use o link "Network URL" exibido abaixo no navegador.
echo.

:: Inicia o Streamlit liberando o acesso externo na rede (0.0.0.0)
streamlit run Conciliador_Fatura.py --server.address 0.0.0.0 --server.port 8501

pause