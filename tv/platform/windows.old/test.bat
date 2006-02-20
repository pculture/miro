@REM ##########################################################################
@REM ## Edit for your machine                                                 #
@REM ##########################################################################

@set PATH=C:\Python24;%PATH%

@REM ##########################################################################

@REM I don't remember off the top of my head how to check the
@REM 'errorlevel' returned by a command. So, in order to avoid running DTV
@REM when the build failed, delete the main executable to ensure it can't
@REM start.
@del .\dist\DTV.exe

REM Build the application. The build script mostly knows how to build over
REM an existing 'dist' directory, wiping the resource directory as
REM necessary. For releases you will still want to remove 'dist' and do
REM a clean build to ensure that no unnecessary files are shipped.
@python setup.py py2exe

REM If the build succeeded, run the application.
@.\dist\DTV.exe
