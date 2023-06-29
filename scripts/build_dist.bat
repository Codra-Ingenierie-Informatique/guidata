@echo off
REM This script was copied from PythonQwt project
REM ======================================================
REM Package build script
REM ======================================================
REM Licensed under the terms of the MIT License
REM Copyright (c) 2020 Pierre Raybaut
REM (see PythonQwt LICENSE file for more details)
REM ======================================================
call %~dp0utils GetScriptPath SCRIPTPATH
call %FUNC% GetLibName LIBNAME
call %FUNC% GetModName MODNAME
call %FUNC% SetPythonPath
call %FUNC% UsePython
if exist MANIFEST ( del /q MANIFEST )
python setup.py sdist bdist_wheel
del %MODNAME%\*.chm
python setup.py build sdist
rmdir /s /q %LIBNAME%.egg-info
call %FUNC% EndOfScript