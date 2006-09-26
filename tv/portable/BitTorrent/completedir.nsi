# Written by Bram Cohen
# see LICENSE.txt for license information

Outfile completedir.exe
Name completedir
SilentInstall silent
SetCompressor lzma
InstallDir "$PROGRAMFILES\completedir\"
Section "Install"
  SetOutPath $INSTDIR
  WriteUninstaller "$INSTDIR\uninstall.exe"
  File dist\btcompletedirgui.exe
  File dist\*.exe
  File dist\*.pyd
  File dist\*.dll
  File dist\library.zip
  File bittorrent.ico
  File LICENSE.txt
  CreateShortCut "$STARTMENU\Programs\completedir.lnk" "$INSTDIR\btcompletedirgui.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CompleteDir" "DisplayName" "BitTorrent complete dir 1.1"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CompleteDir" "UninstallString" '"$INSTDIR\uninstall.exe"'
  MessageBox MB_OK "Complete dir has been successfully installed! Run it under the Programs in the Start Menu."
SectionEnd

Section "Uninstall"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CompleteDir"
  Delete "$STARTMENU\Programs\completedir.lnk"
  RMDir /r "$INSTDIR"
SectionEnd
