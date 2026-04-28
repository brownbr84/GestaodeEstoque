@echo off
setlocal

:: ============================================================
:: TraceBox WMS — Execução da Suíte de Testes
:: Uso: run_tests.bat [opcao]
::
::   (sem argumento)   Roda todos os testes, resumido
::   all               Roda todos os testes, verbose
::   fast              Apenas testes sem I/O externo (exclui DANFE/e-mail)
::   cov               Testes + relatório de cobertura HTML
::   file <modulo>     Roda um arquivo específico
::                     Ex: run_tests.bat file test_security
:: ============================================================

set PYTHON=py
set TESTS_DIR=tests
set COV_DIR=htmlcov

if "%1"=="" goto :all_quiet
if /i "%1"=="all"  goto :all_verbose
if /i "%1"=="fast" goto :fast
if /i "%1"=="cov"  goto :coverage
if /i "%1"=="file" goto :single_file
goto :usage

:all_quiet
echo [TraceBox] Rodando todos os testes...
%PYTHON% -m pytest %TESTS_DIR% -q --tb=short
goto :end

:all_verbose
echo [TraceBox] Rodando todos os testes (verbose)...
%PYTHON% -m pytest %TESTS_DIR% -v --tb=short
goto :end

:fast
echo [TraceBox] Rodando testes rapidos (sem DANFE/email)...
%PYTHON% -m pytest %TESTS_DIR% -q --tb=short ^
  --ignore=%TESTS_DIR%\test_danfe_helpers.py ^
  --ignore=%TESTS_DIR%\test_email_service.py
goto :end

:coverage
echo [TraceBox] Rodando testes com cobertura...
%PYTHON% -m pip install pytest-cov -q
%PYTHON% -m pytest %TESTS_DIR% --cov=. --cov-report=html:%COV_DIR% --cov-report=term-missing -q
echo.
echo Relatorio HTML gerado em: %COV_DIR%\index.html
start "" "%COV_DIR%\index.html"
goto :end

:single_file
if "%2"=="" (
    echo Informe o modulo. Ex: run_tests.bat file test_security
    goto :end
)
echo [TraceBox] Rodando: %TESTS_DIR%\%2.py
%PYTHON% -m pytest %TESTS_DIR%\%2.py -v --tb=short
goto :end

:usage
echo Uso: run_tests.bat [all ^| fast ^| cov ^| file ^<modulo^>]
goto :end

:end
endlocal
