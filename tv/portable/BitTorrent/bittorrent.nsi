# Written by Bram Cohen
# see LICENSE.txt for license information

!define VERSION "3.4.2"
Outfile BitTorrent-${VERSION}.exe
Name BitTorrent
SilentInstall silent
SetCompressor lzma
InstallDir "$PROGRAMFILES\BitTorrent\"
Section "Install"
  SetOutPath $INSTDIR
  WriteUninstaller "$INSTDIR\uninstall.exe"
  File dist\*.exe
  File dist\*.pyd
  File dist\*.dll
  File dist\library.zip
  File redirdonate.html
  File bittorrent.ico
  File LICENSE.txt
  WriteRegStr HKCR .torrent "" bittorrent
  DeleteRegKey HKCR ".torrent\Content Type"
  WriteRegStr HKCR "MIME\Database\Content Type\application/x-bittorrent" Extension .torrent
  WriteRegStr HKCR bittorrent "" "TORRENT File"
  WriteRegBin HKCR bittorrent EditFlags 00000100
  WriteRegStr HKCR "bittorrent\shell" "" open
  WriteRegStr HKCR "bittorrent\shell\open\command" "" `"$INSTDIR\btdownloadgui.exe" --responsefile "%1"`
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BitTorrent" "DisplayName" "BitTorrent ${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BitTorrent" "UninstallString" '"$INSTDIR\uninstall.exe"'
  ExecShell open "$INSTDIR\redirdonate.html"
  Sleep 2000
  MessageBox MB_OK "BitTorrent has been successfully installed!$\r$\n$\r$\nTo use BitTorrent, find a web site which uses it and click on the appropriate links."
  BringToFront
SectionEnd

Section "Uninstall"
  DeleteRegKey HKCR .torrent
  DeleteRegKey HKCR "MIME\Database\Content Type\application/x-bittorrent"
  DeleteRegKey HKCR bittorrent
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BitTorrent"
  RMDir /r "$INSTDIR"
SectionEnd
