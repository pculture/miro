; These are passed in from setup.py:
;  CONFIG_VERSION        eg, "0.8.0"
;  CONFIG_PROJECT_URL    eg, "http://www.participatoryculture.org/"
;  CONFIG_SHORT_APP_NAME eg, "Democracy"
;  CONFIG_LONG_APP_NAME  eg, "Democracy Player"
;  CONFIG_PUBLISHER      eg, "Participatory Culture Foundation"
;  CONFIG_EXECUTABLE     eg, "Democracy.exe"
;  CONFIG_ICON           eg, "Democracy.ico"
;  CONFIG_OUTPUT_FILE    eg, "Democracy-0.8.0.exe"

!define INST_KEY "Software\${CONFIG_PUBLISHER}\${CONFIG_LONG_APP_NAME}"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${CONFIG_LONG_APP_NAME}"

!define RUN_SHORTCUT "${CONFIG_LONG_APP_NAME}.lnk"
!define UNINSTALL_SHORTCUT "Uninstall ${CONFIG_SHORT_APP_NAME}.lnk"

Name "${CONFIG_LONG_APP_NAME} ${CONFIG_VERSION}"
OutFile ${CONFIG_OUTPUT_FILE}
InstallDir "$PROGRAMFILES\${CONFIG_PUBLISHER}\${CONFIG_LONG_APP_NAME}"
InstallDirRegKey HKLM "${INST_KEY}" "Install_Dir"
SetCompressor lzma

SetOverwrite ifnewer
CRCCheck on

Icon ${CONFIG_ICON}

Var STARTMENU_FOLDER

; Runs in tv/platform/windows-xul/dist, so 4 ..s.
!addplugindir ..\..\..\..\dtv-binary-kit\NSIS-Plugins\

!addincludedir ..\..\..\..\dtv-binary-kit\NSIS-Plugins\

!include "MUI.nsh"
!include "Sections.nsh"
!include zipdll.nsh
!include nsProcess.nsh

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Pages                                                                     ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

; Welcome page
!define MUI_WELCOMEPAGE_TITLE_3LINES
!insertmacro MUI_PAGE_WELCOME

; License page
!insertmacro MUI_PAGE_LICENSE "license.txt"

; Component selection page
!define MUI_COMPONENTSPAGE_TEXT_COMPLIST \
  "Please choose which optional components to install."
!insertmacro MUI_PAGE_COMPONENTS

; Installation directory selection page
!insertmacro MUI_PAGE_DIRECTORY

; Start menu folder name selection page
!define MUI_STARTMENUPAGE_DEFAULTFOLDER "${CONFIG_LONG_APP_NAME}"
!insertmacro MUI_PAGE_STARTMENU Application $STARTMENU_FOLDER

; Installation page
!insertmacro MUI_PAGE_INSTFILES

; Finish page
!define MUI_FINISHPAGE_RUN "$INSTDIR\${CONFIG_EXECUTABLE}"
!define MUI_FINISHPAGE_LINK \
  "Click here to visit the ${CONFIG_PUBLISHER} homepage."
!define MUI_FINISHPAGE_LINK_LOCATION "${CONFIG_PROJECT_URL}"
!define MUI_FINISHPAGE_NOREBOOTSUPPORT
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Languages                                                                 ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

!insertmacro MUI_LANGUAGE "English" # first language is the default language
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "German"
!insertmacro MUI_LANGUAGE "Spanish"
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "TradChinese"
!insertmacro MUI_LANGUAGE "Japanese"
!insertmacro MUI_LANGUAGE "Korean"
!insertmacro MUI_LANGUAGE "Italian"
!insertmacro MUI_LANGUAGE "Dutch"
!insertmacro MUI_LANGUAGE "Danish"
!insertmacro MUI_LANGUAGE "Swedish"
!insertmacro MUI_LANGUAGE "Norwegian"
!insertmacro MUI_LANGUAGE "Finnish"
!insertmacro MUI_LANGUAGE "Greek"
!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "Portuguese"
!insertmacro MUI_LANGUAGE "Arabic"

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Reserve files (interacts with solid compression to speed up installation) ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

!insertmacro MUI_RESERVEFILE_LANGDLL
!insertmacro MUI_RESERVEFILE_INSTALLOPTIONS

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Functions
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

; Author: Lilla (lilla@earthlink.net) 2003-06-13
; function IsUserAdmin uses plugin \NSIS\PlusgIns\UserInfo.dll
; This function is based upon code in \NSIS\Contrib\UserInfo\UserInfo.nsi
; This function was tested under NSIS 2 beta 4 (latest CVS as of this writing).
;
; Removed a bunch of comments --Ben
;
; Usage:
;   Call IsUserAdmin
;   Pop $R0   ; at this point $R0 is "true" or "false"
;
Function IsUserAdmin
Push $R0
Push $R1
Push $R2
 
ClearErrors
UserInfo::GetName
IfErrors Win9x
Pop $R1
UserInfo::GetAccountType
Pop $R2
 
StrCmp $R2 "Admin" 0 Continue
; Observation: I get here when running Win98SE. (Lilla)
; The functions UserInfo.dll looks for are there on Win98 too, 
; but just don't work. So UserInfo.dll, knowing that admin isn't required
; on Win98, returns admin anyway. (per kichik)
StrCpy $R0 "true"
Goto Done
 
Continue:
; You should still check for an empty string because the functions
; UserInfo.dll looks for may not be present on Windows 95. (per kichik)
StrCmp $R2 "" Win9x
StrCpy $R0 "false"
Goto Done
 
Win9x:
StrCpy $R0 "true"
 
Done:
Pop $R2
Pop $R1
Exch $R0
FunctionEnd

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Macros
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

!macro checkExtensionHandled ext sectionName
  Push $0
  ReadRegStr $0 HKCR "${ext}" ""
  StrCmp $0 "" +6
  StrCmp $0 "DemocracyPlayer" +5
  StrCmp $0 "Democracy.Player.1" +4
    SectionGetFlags ${sectionName} $0
    IntOp $0 $0 & 0xFFFFFFFE
    SectionSetFlags ${sectionName} $0
  Pop $0
!macroend

!macro uninstall directory
  ; Remove the program
  Delete   "${directory}\${CONFIG_EXECUTABLE}"
  Delete   "${directory}\${CONFIG_ICON}"
  Delete   "${directory}\Democracy_Downloader.exe"
  Delete   "${directory}\application.ini"
  Delete   "${directory}\msvcp71.dll"
  Delete   "${directory}\msvcr71.dll"
  Delete   "${directory}\python24.dll"
  Delete   "${directory}\boost_python-vc71-mt-1_33.dll"
  Delete   "${directory}\uninstall.exe"

  RMDir /r "${directory}\chrome"
  RMDir /r "${directory}\components"
  RMDir /r "${directory}\defaults"
  RMDir /r "${directory}\resources"
  RMDir /r "${directory}\vlc-plugins"
  RMDir /r "${directory}\xulrunner"

  RMDIR ${directory} 
!macroend


;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Sections                                                                  ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

Section "-${CONFIG_LONG_APP_NAME}"

; Warn users of Windows 9x/ME that they're not supported
  Push $R0
  ClearErrors
  ReadRegStr $R0 HKLM \
    "SOFTWARE\Microsoft\Windows NT\CurrentVersion" CurrentVersion
  IfErrors 0 lbl_winnt
  MessageBox MB_ICONEXCLAMATION \
     "WARNING: Democracy Player is not officially supported on this version of Windows$\r$\n$\r$\nVideo playback is known to be broken, and there may be other problems"
lbl_winnt:

  Pop $R0

  Call IsUserAdmin
  Pop $R0
  StrCmp $R0 "true" is_admin
  MessageBox MB_OK|MB_ICONEXCLAMATION "You must have administrator privileges to install Democracy.  Please log in using an administrator account and try again."
  Quit
  
is_admin:
  SetShellVarContext all

  SetOutPath "$INSTDIR"

!if ${CONFIG_TWOSTAGE} = "Yes"

  InetLoad::load http://ftp.osuosl.org/pub/pculture.org/democracy/win/Democracy-Contents-${CONFIG_VERSION}.zip $INSTDIR\Democracy-Contents.zip
  Pop $0
  StrCmp $0 "OK" dlok
  MessageBox MB_OK|MB_ICONEXCLAMATION "Download Error, click OK to abort installation: $0" /SD IDOK
  Abort
dlok:
  !insertmacro ZIPDLL_EXTRACT $INSTDIR\Democracy-Contents.zip $INSTDIR <ALL>
  Delete $INSTDIR\Democracy-Contents.zip
  Pop $0
  StrCmp $0 "success" unzipok
  MessageBox MB_OK|MB_ICONEXCLAMATION "Unzip error, click OK to abort installation: $0" /SD IDOK
  Abort
unzipok:

!else

  File  ${CONFIG_EXECUTABLE}
  File  ${CONFIG_ICON}
  File  Democracy_Downloader.exe
  File  application.ini
  File  msvcp71.dll  
  File  msvcr71.dll  
  File  python24.dll
  File  boost_python-vc71-mt-1_33.dll

  File  /r chrome
  File  /r components
  File  /r defaults
  File  /r resources
  File  /r vlc-plugins
  File  /r xulrunner

!endif

  SetOutPath "$INSTDIR\resources"
  TackOn::writeToFile initial-feeds.democracy
  IfErrors 0 files_ok
  
  MessageBox MB_OK|MB_ICONEXCLAMATION "Installation failed.  An error occured writing to the Democracy Folder."
  Quit

files_ok:

  ; Old versions used HKEY_LOCAL_MACHINE for the RunAtStartup value, we use
  ; HKEY_CURRENT_USER now
  ReadRegStr $R0 HKLM  "Software\Microsoft\Windows\CurrentVersion\Run" "Democracy Player"
  StrCmp $R0 "" +3
    DeleteRegValue HKLM  "Software\Microsoft\Windows\CurrentVersion\Run" "Democracy Player"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Democracy Player" $R0

  ; Create a ProgID for Democracy
  WriteRegStr HKCR "Democracy.Player.1" "" "Democracy Player"
  WriteRegDword HKCR "Democracy.Player.1" "EditFlags" 0x00010000
  ; FTA_OpenIsSafe flag
  WriteRegStr HKCR "Democracy.Player.1\shell" "" "open"
  WriteRegStr HKCR "Democracy.Player.1\DefaultIcon" "" "$INSTDIR\Democracy.exe,0"
  WriteRegStr HKCR "Democracy.Player.1\shell\open\command" "" \
    '$INSTDIR\Democracy.exe "%1"'
  WriteRegStr HKCR "Democracy.Player.1\shell\edit" "" "Edit Options File"
  WriteRegStr HKCR "Democracy.Player.1\shell\edit\command" "" \
    '$INSTDIR\Democracy.exe "%1"'

  ; Delete our old, poorly formatted ProgID
  DeleteRegKey HKCR "DemocracyPlayer"

  ; Democracy complains if this isn't present and it can't create it
  CreateDirectory "$INSTDIR\xulrunner\extensions"

  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
  CreateDirectory "$SMPROGRAMS\$STARTMENU_FOLDER"
  CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\${RUN_SHORTCUT}" \
    "$INSTDIR\${CONFIG_EXECUTABLE}" "" "$INSTDIR\${CONFIG_ICON}"
  CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\${UNINSTALL_SHORTCUT}" \
    "$INSTDIR\uninstall.exe"
  !insertmacro MUI_STARTMENU_WRITE_END
SectionEnd

Section "Desktop icon" SecDesktop
  CreateShortcut "$DESKTOP\${RUN_SHORTCUT}" "$INSTDIR\${CONFIG_EXECUTABLE}" \
    "" "$INSTDIR\${CONFIG_ICON}"
SectionEnd

Section /o "Quick launch icon" SecQuickLaunch
  CreateShortcut "$QUICKLAUNCH\${RUN_SHORTCUT}" "$INSTDIR\${CONFIG_EXECUTABLE}" \
    "" "$INSTDIR\${CONFIG_ICON}"
SectionEnd

Section "Handle Democracy files" SecRegisterDemocracy
  WriteRegStr HKCR ".democracy" "" "Democracy.Player.1"
SectionEnd

Section "Handle Torrent files" SecRegisterTorrent
  WriteRegStr HKCR ".torrent" "" "Democracy.Player.1"
SectionEnd

Section "Handle AVI files" SecRegisterAvi
  WriteRegStr HKCR ".avi" "" "Democracy.Player.1"
SectionEnd

Section "Handle MPEG files" SecRegisterMpg
  WriteRegStr HKCR ".m4v" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mpg" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mpeg" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mp2" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mp3" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mp4" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mpa" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mpe" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mpv" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mpv2" "" "Democracy.Player.1"
SectionEnd

Section "Handle Quicktime files" SecRegisterMov
  WriteRegStr HKCR ".mov" "" "Democracy.Player.1"
  WriteRegStr HKCR ".qt" "" "Democracy.Player.1"
SectionEnd

Section "Handle ASF files" SecRegisterAsf
  WriteRegStr HKCR ".asf" "" "Democracy.Player.1"
SectionEnd

Section "Handle Windows Media files" SecRegisterWmv
  WriteRegStr HKCR ".wmv" "" "Democracy.Player.1"
SectionEnd

Section "DTS files" SecRegisterDts
  WriteRegStr HKCR ".dts" "" "Democracy.Player.1"
SectionEnd

Section "Handle Ogg Media files" SecRegisterOgg
  WriteRegStr HKCR ".ogg" "" "Democracy.Player.1"
  WriteRegStr HKCR ".ogm" "" "Democracy.Player.1"
SectionEnd

Section "Handle Matroska Media files" SecRegisterMkv
  WriteRegStr HKCR ".mkv" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mka" "" "Democracy.Player.1"
  WriteRegStr HKCR ".mks" "" "Democracy.Player.1"
SectionEnd

Section "Handle 3gp Media files" SecRegister3gp
  WriteRegStr HKCR ".3gp" "" "Democracy.Player.1"
SectionEnd

Section "Handle 3g2 Media files" SecRegister3g2
  WriteRegStr HKCR ".3g2" "" "Democracy.Player.1"
SectionEnd

Section "Handle Flash Video files" SecRegisterFlv
  WriteRegStr HKCR ".flv" "" "Democracy.Player.1"
SectionEnd

Section "Handle Nullsoft Video files" SecRegisterNsv
  WriteRegStr HKCR ".nsv" "" "Democracy.Player.1"
SectionEnd

Section "Handle pva Video files" SecRegisterPva
  WriteRegStr HKCR ".pva" "" "Democracy.Player.1"
SectionEnd

Section "Handle Annodex Video files" SecRegisterAnx
  WriteRegStr HKCR ".anx" "" "Democracy.Player.1"
SectionEnd

Section "Handle Xvid Video files" SecRegisterXvid
  WriteRegStr HKCR ".xvid" "" "Democracy.Player.1"
  WriteRegStr HKCR ".3ivx" "" "Democracy.Player.1"
SectionEnd

Section -NotifyShellExentionChange
  System::Call 'Shell32::SHChangeNotify(i 0x8000000, i 0, i 0, i 0)'
SectionEnd

Function .onInit
  ; Is the app running?  Stop it if so.
TestRunning:
  ${nsProcess::FindProcess} "democracy.exe" $R0
  StrCmp $R0 0 0 NotRunning
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
  "It looks like you're already running ${CONFIG_LONG_APP_NAME}.$\n\
Please shut it down before continuing." \
       IDOK TestRunning
  Quit
NotRunning:

  ; Is the downloader running?  Stop it if so.
  ${nsProcess::FindProcess} "democracy-downloader.exe" $R0
  StrCmp $R0 0 0 NotDownloaderRunning
  ${nsProcess::KillProcess} "democracy-downloader.exe" $R0
NotDownloaderRunning:

  ; Is the app already installed? Bail if so.
  ReadRegStr $R0 HKLM "${INST_KEY}" "InstallDir"
  StrCmp $R0 "" done
 
  ; Should we uninstall the old one?
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
  "It looks like you already have a copy of ${CONFIG_LONG_APP_NAME} $\n\
installed.  Do you want to continue and overwrite it?" \
       IDOK continue
  Quit
continue:
  !insertmacro uninstall $R0

  done:
  !insertmacro MUI_LANGDLL_DISPLAY

  ; Make check boxes for unhandled file extensions.
  !insertmacro checkExtensionHandled ".torrent" ${SecRegisterTorrent}
  !insertmacro checkExtensionHandled ".democracy" ${SecRegisterDemocracy}
  !insertmacro checkExtensionHandled ".avi" ${SecRegisterAvi}
  !insertmacro checkExtensionHandled ".m4v" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpg" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpeg" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mp2" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mp3" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mp4" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpa" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpe" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpv" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpv2" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mov" ${SecRegisterMov}
  !insertmacro checkExtensionHandled ".qa" ${SecRegisterMov}
  !insertmacro checkExtensionHandled ".asf" ${SecRegisterAsf}
  !insertmacro checkExtensionHandled ".wmv" ${SecRegisterWmv}
  !insertmacro checkExtensionHandled ".dts" ${SecRegisterDts}
  !insertmacro checkExtensionHandled ".ogg" ${SecRegisterOgg}
  !insertmacro checkExtensionHandled ".ogm" ${SecRegisterOgg}
  !insertmacro checkExtensionHandled ".mkv" ${SecRegisterMkv}
  !insertmacro checkExtensionHandled ".mka" ${SecRegisterMkv}
  !insertmacro checkExtensionHandled ".mks" ${SecRegisterMkv}
  !insertmacro checkExtensionHandled ".3gp" ${SecRegister3gp}
  !insertmacro checkExtensionHandled ".3g2" ${SecRegister3g2}
  !insertmacro checkExtensionHandled ".flv" ${SecRegisterFlv}
  !insertmacro checkExtensionHandled ".nsv" ${SecRegisterNsv}
  !insertmacro checkExtensionHandled ".pva" ${SecRegisterPva}
  !insertmacro checkExtensionHandled ".anx" ${SecRegisterAnx}
  !insertmacro checkExtensionHandled ".xvid" ${SecRegisterXvid}
  !insertmacro checkExtensionHandled ".3ivx" ${SecRegisterXvid}
FunctionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${INST_KEY}" "InstallDir" $INSTDIR
  WriteRegStr HKLM "${INST_KEY}" "Version" "${CONFIG_VERSION}"
  WriteRegStr HKLM "${INST_KEY}" "" "$INSTDIR\${CONFIG_EXECUTABLE}"

  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${CONFIG_EXECUTABLE}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${CONFIG_VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "URLInfoAbout" "${CONFIG_PROJECT_URL}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${CONFIG_PUBLISHER}"
SectionEnd

Section "Uninstall" SEC91
  SetShellVarContext all

  !insertmacro uninstall $INSTDIR

  ; Remove Start Menu shortcuts
  !insertmacro MUI_STARTMENU_GETFOLDER Application $R0
  Delete "$SMPROGRAMS\$R0\${RUN_SHORTCUT}"
  Delete "$SMPROGRAMS\$R0\${UNINSTALL_SHORTCUT}"
  RMDir "$SMPROGRAMS\$R0"

  ; Remove desktop and quick launch shortcuts
  Delete "$DESKTOP\${RUN_SHORTCUT}"
  Delete "$QUICKLAUNCH\${RUN_SHORTCUT}"

  ; Remove registry keys
  DeleteRegKey HKLM "${INST_KEY}"
  DeleteRegKey HKLM "${UNINST_KEY}"
  DeleteRegValue HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "Democracy Player"
  DeleteRegKey HKCR "Democracy.Player.1"

  SetAutoClose true
SectionEnd
