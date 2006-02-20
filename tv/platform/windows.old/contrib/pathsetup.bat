REM START of pathsetup.bat - NON-user-specific hard-coded paths for building with free MS tools

REM add Python-2.4 to path
set Path=C:\Python24;%Path%
set PYTHON_ROOT=C:\Python24
set PYTHON_VERSION=2.4

REM add the compiler path
set Path=%ProgramFiles%\Microsoft Visual C++ Toolkit 2003\bin;%Path%

REM setup include paths
set Include=%ProgramFiles%\Microsoft Platform SDK for Windows XP
SP2\Include;%Include%
set Include=%ProgramFiles%\Microsoft Visual C++ Toolkit
2003\include;%Include%

REM setup Lib paths
set Lib=%ProgramFiles%\Microsoft Platform SDK for Windows XP SP2\Lib;%Lib%
set Lib=%ProgramFiles%\Microsoft Visual C++ Toolkit 2003\lib;%Lib%
set Lib=%ProgramFiles%\Microsoft Visual Studio .NET 2003\Vc7\lib;%Lib%

rem this bit required by boost - where is unixutils?, eg, sed/etc:
set Path=C:\utils;%Path%

@echo -------------------------------------------------------------------------------
@echo You may want to copy this file (pathsetup.bat) to:
@echo  %ProgramFiles%\Microsoft Visual Studio .NET 2003\Vc7\bin\vcvars32.bat
@echo and
@echo  %ProgramFiles%\Microsoft Visual C++ Toolkit 2003\vcvars32.bat
@echo as oither applications may expect to find it there.
@echo -------------------------------------------------------------------------------

REM END of pathsetup.bat