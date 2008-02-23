; These are passed in from setup.py:
;  CONFIG_VERSION        eg, "0.8.0"
;  CONFIG_PROJECT_URL    eg, "http://www.participatoryculture.org/"
;  CONFIG_SHORT_APP_NAME eg, "Democracy"
;  CONFIG_LONG_APP_NAME  eg, "Democracy Player"
;  CONFIG_PUBLISHER      eg, "Participatory Culture Foundation"
;  CONFIG_EXECUTABLE     eg, "Democracy.exe
;  CONFIG_MOVIE_DATA_EXECUTABLE     eg, "Democracy_MovieData.exe
;  CONFIG_ICON           eg, "Democracy.ico"
;  CONFIG_OUTPUT_FILE    eg, "Democracy-0.8.0.exe"
;  CONFIG_PROG_ID        eg, "Democracy.Player.1"

!define INST_KEY "Software\${CONFIG_PUBLISHER}\${CONFIG_LONG_APP_NAME}"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${CONFIG_LONG_APP_NAME}"

!define RUN_SHORTCUT "${CONFIG_LONG_APP_NAME}.lnk"
!define UNINSTALL_SHORTCUT "Uninstall ${CONFIG_SHORT_APP_NAME}.lnk"
!define MUI_ICON "miro-installer.ico"
!define MUI_UNICON "miro-installer.ico"

!define OLD_INST_KEY "Software\Participatory Culture Foundation\Democracy Player"
!define OLD_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Democracy Player"
!define OLD_RUN_SHORTCUT1 "Democracy Player.lnk"
!define OLD_RUN_SHORTCUT2 "Democracy.lnk"
!define OLD_UNINSTALL_SHORTCUT1 "Uninstall Democracy Player.lnk"
!define OLD_UNINSTALL_SHORTCUT2 "Uninstall Democracy.lnk"

Name "$APP_NAME"
OutFile "${CONFIG_OUTPUT_FILE}"
InstallDir "$PROGRAMFILES\${CONFIG_PUBLISHER}\${CONFIG_LONG_APP_NAME}"
InstallDirRegKey HKLM "${INST_KEY}" "Install_Dir"
SetCompressor lzma

SetOverwrite ifnewer
CRCCheck on

Icon "${CONFIG_ICON}"

Var STARTMENU_FOLDER
Var THEME_NAME
Var APP_NAME ; Used in text within the program
Var ONLY_INSTALL_THEME
Var THEME_TEMP_DIR
Var INITIAL_FEEDS
Var TACKED_ON_FILE
Var SIMPLE_INSTALL

; Runs in tv/platform/windows-xul/dist, so 4 ..s.
!addplugindir ..\..\..\..\dtv-binary-kit\NSIS-Plugins\

!addincludedir ..\..\..\..\dtv-binary-kit\NSIS-Plugins\

!define MUI_WELCOMEPAGE_TITLE "Welcome to Miro!"
!define MUI_WELCOMEPAGE_TEXT "To get started, choose an easy or a custom install process and then click 'Install'."

!include "MUI.nsh"
!include "Sections.nsh"
!include zipdll.nsh
!include nsProcess.nsh
!include "TextFunc.nsh"
!include "WordFunc.nsh"
!include "FileFunc.nsh"
!include "WinMessages.nsh"

!insertmacro TrimNewLines
!insertmacro WordFind
!insertmacro un.TrimNewLines
!insertmacro un.WordFind
!insertmacro un.GetParameters
!insertmacro un.GetOptions


ReserveFile "iHeartMiro-installer-page.ini"

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Pages                                                                     ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

; Welcome page
!define MUI_PAGE_CUSTOMFUNCTION_PRE   "add_radio_buttons"
!define MUI_PAGE_CUSTOMFUNCTION_SHOW  "fix_background_color"
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE "check_radio_buttons"

!define MUI_COMPONENTSPAGE_NODESC
!define MUI_WELCOMEFINISHPAGE_BITMAP "miro-install-image.bmp"
!insertmacro MUI_PAGE_WELCOME

Function add_radio_buttons

  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Settings" "NumFields" "5"
  
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 2" "Top" "20"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 2" "Bottom" "38"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 2" "Right" "325"

  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 3" "Top" "45"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 3" "Bottom" "65"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 3" "Right" "325"

  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 4" "Type"   "radiobutton"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 4" "Text"   "Easy Install"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 4" "Left"   "120"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 4" "Right"  "315"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 4" "Top"    "75"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 4" "Bottom" "85"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 4" "Flags"  "NOTIFY"

  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 5" "Type"   "radiobutton"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 5" "Text"   "Custom Install"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 5" "Left"   "120"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 5" "Right"  "315"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 5" "Top"    "90"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 5" "Bottom" "100"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 5" "Flags"  "NOTIFY"

  StrCmp $SIMPLE_INSTALL "1" simple custom

  custom:
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 4" "State"  "0"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 5" "State"  "1"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Settings" "NextButtonText" "Next >"
  goto end

  simple:
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 4" "State"  "1"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Field 5" "State"  "0"
  !insertmacro MUI_INSTALLOPTIONS_WRITE "ioSpecial.ini" "Settings" "NextButtonText" "Install"
  goto end

  end:
FunctionEnd

Function fix_background_color
  Push $0

  GetDlgItem $0 $MUI_HWND 1203
  SetCtlColors $0 "" 0xFFFFFF
  GetDlgItem $0 $MUI_HWND 1204
  SetCtlColors $0 "" 0xFFFFFF

  StrCmp $SIMPLE_INSTALL "1" simple custom

  simple:
  GetDlgItem $0 $HWNDPARENT 1
  SendMessage $0 ${WM_SETTEXT} 0 "STR:Install"
  goto end

  custom:
  GetDlgItem $0 $HWNDPARENT 1
  SendMessage $0 ${WM_SETTEXT} 0 "STR:Next >"
  goto end

  end:

  Pop $0
FunctionEnd

Var STATE
Function check_radio_buttons
  Push $0
  ReadINIStr $SIMPLE_INSTALL "$PLUGINSDIR\ioSpecial.ini" "Field 4" "State"
  ReadINIStr $STATE "$PLUGINSDIR\ioSpecial.ini" "Settings" "State"
  StrCmp $STATE "4" set
  StrCmp $STATE "5" set

  next_clicked:
  goto end

  set:
  StrCmp $SIMPLE_INSTALL "1" simple custom

  simple:
  GetDlgItem $0 $HWNDPARENT 1
  SendMessage $0 ${WM_SETTEXT} 0 "STR:Install"
  goto end_set

  custom:
  GetDlgItem $0 $HWNDPARENT 1
  SendMessage $0 ${WM_SETTEXT} 0 "STR:Next >"
  goto end_set

  end_set:
  Abort

  end:
  Pop $0
FunctionEnd

Function skip_if_simple
  StrCmp $SIMPLE_INSTALL "1" skip_for_simple
  goto end
  skip_for_simple:
  Abort
  end:
FunctionEnd


; License page
; !insertmacro MUI_PAGE_LICENSE "license.txt"

; Component selection page
!define MUI_COMPONENTSPAGE_TEXT_COMPLIST \
  "Please choose which optional components to install."
!define MUI_PAGE_CUSTOMFUNCTION_PRE   "skip_if_simple"
!insertmacro MUI_PAGE_COMPONENTS

; Page custom iHeartMiroInstall iHeartMiroInstallLeave

; Installation directory selection page
!define MUI_PAGE_CUSTOMFUNCTION_PRE   "skip_if_simple"
!insertmacro MUI_PAGE_DIRECTORY

; Start menu folder name selection page
!define MUI_PAGE_CUSTOMFUNCTION_PRE   "skip_if_simple"
!insertmacro MUI_PAGE_STARTMENU Application $STARTMENU_FOLDER

; Installation page
!insertmacro MUI_PAGE_INSTFILES

; Finish page
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Run $APP_NAME"
!define MUI_FINISHPAGE_RUN_FUNCTION "LaunchLink"
!define MUI_FINISHPAGE_LINK \
  "${CONFIG_PUBLISHER} homepage."
!define MUI_FINISHPAGE_LINK_LOCATION "${CONFIG_PROJECT_URL}"
!define MUI_FINISHPAGE_NOREBOOTSUPPORT
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE "dont_leave_early"
Function dont_leave_early
  ReadINIStr $STATE "$PLUGINSDIR\ioSpecial.ini" "Settings" "State"
  StrCmp $STATE "4" dont_leave
  goto end
  dont_leave:
  Abort
  end:
FunctionEnd
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
;; Macros
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

!macro checkExtensionHandled ext sectionName
  Push $0
  ReadRegStr $0 HKCR "${ext}" ""
  StrCmp $0 "" +6
  StrCmp $0 "DemocracyPlayer" +5
  StrCmp $0 "${CONFIG_PROG_ID}" +4
    SectionGetFlags ${sectionName} $0
    IntOp $0 $0 & 0xFFFFFFFE
    SectionSetFlags ${sectionName} $0
  Pop $0
!macroend

!macro uninstall directory
  ; Remove the program
  Delete   "${directory}\${CONFIG_EXECUTABLE}"
  Delete   "${directory}\${CONFIG_ICON}"
  Delete   "${directory}\${CONFIG_MOVIE_DATA_EXECUTABLE}"
  Delete   "${directory}\*.dll"
  Delete   "${directory}\moviedata_util.py"
  Delete   "${directory}\application.ini"
  Delete   "${directory}\uninstall.exe"

  RMDir /r "${directory}\chrome"
  RMDir /r "${directory}\components"
  RMDir /r "${directory}\defaults"
  RMDir /r "${directory}\resources"
  RMDir /r "${directory}\vlc-plugins"
  RMDir /r "${directory}\plugins"
  RMDir /r "${directory}\xulrunner"
  RMDir /r "${directory}\imagemagick"

  RMDIR ${directory} 
!macroend

!macro GetConfigOptionsMacro trim find
ClearErrors
Push $R0
Push $R1
Push $R2
Push $R3

  FileOpen $R2 "$R1" r
config_loop:
  FileRead $R2 $R1
  IfErrors error_in_config
  ${trim} "$R1" $R1
  StrLen $R3 $R0
  StrCpy $R4 $R1 $R3
  StrCmp $R4 $R0 done_config_loop
  Goto config_loop
done_config_loop:
  FileClose $R2

  ${find} "$R1" "=" "+1}" $R0

trim_spaces_loop:
  StrCpy $R2 $R0 1
  StrCmp $R2 " " 0 done_config
  StrCpy $R0 "$R0" "" 1
  Goto trim_spaces_loop

error_in_config:
  StrCpy $R0 ""
  FileClose $R2
  ClearErrors

done_config:
Pop $R3
Pop $R2
Pop $R1
Exch $R0
!macroend

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

; Set $R0 to the config option and $R1 to the config file name
; puts the value of the config option on the stack
Function GetConfigOption
  !insertmacro GetConfigOptionsMacro "${TrimNewLines}" "${WordFind}"
FunctionEnd
Function un.GetConfigOption
  !insertmacro GetConfigOptionsMacro "${un.TrimNewLines}" "${un.WordFind}"
FunctionEnd

; Set $R0 to the theme directory
; Returns the theme version string
Function GetThemeVersion
  Push $R0
  Push $R1
  Push $R2

  FileOpen $R1 "$R0\version.txt" r
  IfErrors errors_in_version
  FileRead $R1 $R0
  FileClose $R1
  ${TrimNewLines} "$R0" $R0
  Goto done_version

errors_in_version:
  StrCpy $R0 ""
done_version:
  Push $R2
  Push $R1
  Exch $R0
FunctionEnd

; Sets $R0 to icon, $R1 to parameters, $R2 to the shortcut name, 
; $R3 uninstall shortcut name
Function GetShortcutInfo
  StrCpy $R0 "$INSTDIR\${CONFIG_ICON}"
  StrCpy $R1 ""
  StrCpy $R2 "${RUN_SHORTCUT}"
  StrCpy $R3 "${UNINSTALL_SHORTCUT}"

  StrCmp $THEME_NAME "" done
  ; theme specific icons
  StrCpy $R0 "longAppName"
  StrCpy $R1 "$THEME_TEMP_DIR\app.config"
  Call GetConfigOption
  Pop $R0
  StrCpy $R2 "$R0.lnk"
  StrCpy $R3 "Uninstall $R0.lnk"

  StrCpy $R1 "--theme $\"$THEME_NAME$\""

  Push $R1
  StrCpy $R0 "windowsIcon"
  StrCpy $R1 "$THEME_TEMP_DIR\app.config"
  Call GetConfigOption
  Pop $R0
  Pop $R1
  StrCmp $R0 "" done
  StrCpy $R0 "$APPDATA\Participatory Culture Foundation\Miro\Themes\$THEME_NAME\$R0"

done:

FunctionEnd

Function LaunchLink
  SetShellVarContext all
  Call GetShortcutInfo
  ExecShell "" "$SMPROGRAMS\$STARTMENU_FOLDER\$R2"
FunctionEnd

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
     "WARNING: $APP_NAME is not officially supported on this version of Windows$\r$\n$\r$\nVideo playback is known to be broken, and there may be other problems"
lbl_winnt:

  Pop $R0

  Call IsUserAdmin
  Pop $R0
  StrCmp $R0 "true" is_admin
  MessageBox MB_OK|MB_ICONEXCLAMATION "You must have administrator privileges to install $APP_NAME.  Please log in using an administrator account and try again."
  Quit
  
is_admin:
  SetShellVarContext all
  SetOutPath "$INSTDIR"

StrCmp $ONLY_INSTALL_THEME "1" install_theme

!if ${CONFIG_TWOSTAGE} = "Yes"

  InetLoad::load http://ftp.osuosl.org/pub/pculture.org/democracy/win/${CONFIG_SHORT_APP_NAME}-Contents-${CONFIG_VERSION}.zip "$INSTDIR\${CONFIG_SHORT_APP_NAME}-Contents.zip"
  Pop $0
  StrCmp $0 "OK" dlok
  MessageBox MB_OK|MB_ICONEXCLAMATION "Download Error, click OK to abort installation: $0" /SD IDOK
  Abort
dlok:
  !insertmacro ZIPDLL_EXTRACT "$INSTDIR\${CONFIG_SHORT_APP_NAME}-Contents.zip" $INSTDIR <ALL>
  Delete "$INSTDIR\${CONFIG_SHORT_APP_NAME}-Contents.zip"
  Pop $0
  StrCmp $0 "success" unzipok
  MessageBox MB_OK|MB_ICONEXCLAMATION "Unzip error, click OK to abort installation: $0" /SD IDOK
  Abort
unzipok:

!else

  File  "${CONFIG_EXECUTABLE}"
  File  "${CONFIG_ICON}"
  File  "${CONFIG_MOVIE_DATA_EXECUTABLE}"
  File  "moviedata_util.py"
  File  "*.dll"
  File  application.ini
  File  /r chrome
  File  /r components
  File  /r defaults
  File  /r resources
  File  /r vlc-plugins
  File  /r plugins
  File  /r xulrunner
  File  /r imagemagick

!endif

install_theme:
  StrCmp $THEME_NAME "" done_installing_theme
  SetShellVarContext all ; use the global $APPDATA

  StrCpy $R0 "$APPDATA\Participatory Culture Foundation\Miro\Themes\$THEME_NAME"
  RMDir /r "$R0"
  ClearErrors
  CreateDirectory "$R0"
  CopyFiles /SILENT "$THEME_TEMP_DIR\*.*" "$R0"
done_installing_theme:

  StrCmp $INITIAL_FEEDS "" done_installing_initial_feeds

  CreateDirectory "$INSTDIR\resources\"
  CopyFiles /SILENT "$INITIAL_FEEDS" "$INSTDIR\resources\initial-feeds.democracy"

done_installing_initial_feeds:

  IfErrors 0 files_ok
  
  MessageBox MB_OK|MB_ICONEXCLAMATION "Installation failed.  An error occured writing to the ${CONFIG_SHORT_APP_NAME} Folder."
  Quit
files_ok:


  ; Old versions used HKEY_LOCAL_MACHINE for the RunAtStartup value, we use
  ; HKEY_CURRENT_USER now
  ReadRegStr $R0 HKLM  "Software\Microsoft\Windows\CurrentVersion\Run" "${CONFIG_LONG_APP_NAME}"
  StrCmp $R0 "" +3
    DeleteRegValue HKLM  "Software\Microsoft\Windows\CurrentVersion\Run" "${CONFIG_LONG_APP_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${CONFIG_LONG_APP_NAME}" $R0

  StrCpy $R3 '$INSTDIR\${CONFIG_EXECUTABLE} "%1"'
  StrCmp $THEME_NAME "" install_reg_keys
  StrCpy $R3 '$INSTDIR\${CONFIG_EXECUTABLE} --theme "$THEME_NAME" "%1"'

install_reg_keys:
  ; Create a ProgID for Democracy
  WriteRegStr HKCR "${CONFIG_PROG_ID}" "" "${CONFIG_LONG_APP_NAME}"
  WriteRegDword HKCR "${CONFIG_PROG_ID}" "EditFlags" 0x00010000
  ; FTA_OpenIsSafe flag
  WriteRegStr HKCR "${CONFIG_PROG_ID}\shell" "" "open"
  WriteRegStr HKCR "${CONFIG_PROG_ID}\DefaultIcon" "" "$INSTDIR\${CONFIG_EXECUTABLE},0"
  WriteRegStr HKCR "${CONFIG_PROG_ID}\shell\open\command" "" "$R3"
  WriteRegStr HKCR "${CONFIG_PROG_ID}\shell\edit" "" "Edit Options File"
  WriteRegStr HKCR "${CONFIG_PROG_ID}\shell\edit\command" "" "$R3"

  ; Delete our old, poorly formatted ProgID
  DeleteRegKey HKCR "DemocracyPlayer"

  ; Democracy complains if this isn't present and it can't create it
  CreateDirectory "$INSTDIR\xulrunner\extensions"

  Call GetShortcutInfo

  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
  CreateDirectory "$SMPROGRAMS\$STARTMENU_FOLDER"
  CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\$R2" \
    "$INSTDIR\${CONFIG_EXECUTABLE}" "$R1" "$R0"
  CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\$R3" \
    "$INSTDIR\uninstall.exe" "$R1"
  !insertmacro MUI_STARTMENU_WRITE_END

SectionEnd

Section "Desktop icon" SecDesktop
  Call GetShortcutInfo
  CreateShortcut "$DESKTOP\$R2" "$INSTDIR\${CONFIG_EXECUTABLE}" \
    "$R1" "$R0"
SectionEnd

Section /o "Quick launch icon" SecQuickLaunch
  Call GetShortcutInfo
  CreateShortcut "$QUICKLAUNCH\$R2" "$INSTDIR\${CONFIG_EXECUTABLE}" \
    "$R1" "$R0"
SectionEnd

Section "Handle Miro files" SecRegisterMiro
  WriteRegStr HKCR ".miro" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle Democracy files" SecRegisterDemocracy
  WriteRegStr HKCR ".democracy" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle Torrent files" SecRegisterTorrent
  WriteRegStr HKCR ".torrent" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle AVI files" SecRegisterAvi
  WriteRegStr HKCR ".avi" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle MPEG files" SecRegisterMpg
  WriteRegStr HKCR ".m4v" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".mpg" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".mpeg" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".mp2" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".mp4" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".mpe" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".mpv" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".mpv2" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle MP3 files" SecRegisterMp3
  WriteRegStr HKCR ".mp3" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".mpa" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle Quicktime files" SecRegisterMov
  WriteRegStr HKCR ".mov" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".qt" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle ASF files" SecRegisterAsf
  WriteRegStr HKCR ".asf" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle Windows Media files" SecRegisterWmv
  WriteRegStr HKCR ".wmv" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "DTS files" SecRegisterDts
  WriteRegStr HKCR ".dts" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle Ogg Media files" SecRegisterOgg
  WriteRegStr HKCR ".ogg" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".ogm" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle Matroska Media files" SecRegisterMkv
  WriteRegStr HKCR ".mkv" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".mka" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".mks" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle 3gp Media files" SecRegister3gp
  WriteRegStr HKCR ".3gp" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle 3g2 Media files" SecRegister3g2
  WriteRegStr HKCR ".3g2" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle Flash Video files" SecRegisterFlv
  WriteRegStr HKCR ".flv" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle Nullsoft Video files" SecRegisterNsv
  WriteRegStr HKCR ".nsv" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle pva Video files" SecRegisterPva
  WriteRegStr HKCR ".pva" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle Annodex Video files" SecRegisterAnx
  WriteRegStr HKCR ".anx" "" "${CONFIG_PROG_ID}"
SectionEnd

Section "Handle Xvid Video files" SecRegisterXvid
  WriteRegStr HKCR ".xvid" "" "${CONFIG_PROG_ID}"
  WriteRegStr HKCR ".3ivx" "" "${CONFIG_PROG_ID}"
SectionEnd

Section -NotifyShellExentionChange
  System::Call 'Shell32::SHChangeNotify(i 0x8000000, i 0, i 0, i 0)'
SectionEnd

Function un.onInit
  StrCpy $APP_NAME "${CONFIG_LONG_APP_NAME}"
FunctionEnd

Function .onInit
  ; Process the tacked on file
  StrCpy $THEME_NAME ""
  StrCpy $INITIAL_FEEDS ""
  StrCpy $ONLY_INSTALL_THEME ""
  StrCpy $THEME_TEMP_DIR ""
  StrCpy $APP_NAME "${CONFIG_LONG_APP_NAME}"
  StrCpy $SIMPLE_INSTALL "1"

  !insertmacro MUI_INSTALLOPTIONS_EXTRACT "iHeartMiro-installer-page.ini"

  GetTempFileName $TACKED_ON_FILE
  Delete "$TACKED_ON_FILE"  ; The above macro creates the file
  TackOn::writeToFile "$TACKED_ON_FILE"
  FileOpen $0 "$TACKED_ON_FILE" r
  IfErrors no_tackon

  ; If file starts with 0x50 0x4b 0x03 0x04, it's a zip file
  FileReadByte $0 $1
  IntCmpU $1 0x50 0 non_zip_tackon non_zip_tackon
  FileReadByte $0 $1
  IntCmpU $1 0x4b 0 non_zip_tackon non_zip_tackon
  FileReadByte $0 $1
  IntCmpU $1 0x03 0 non_zip_tackon non_zip_tackon
  FileReadByte $0 $1
  IntCmpU $1 0x04 0 non_zip_tackon non_zip_tackon

  ; We have a zip tacked on file

  FileClose $0

  GetTempFileName $THEME_TEMP_DIR
  Delete "$THEME_TEMP_DIR"  ; The above macro creates the file
  !insertmacro ZIPDLL_EXTRACT "$TACKED_ON_FILE" "$THEME_TEMP_DIR" <ALL>

  StrCpy $R0 "$THEME_TEMP_DIR"
  Call GetThemeVersion
  Pop $0
  StrCmp $0 "0" 0 error_in_theme

  StrCpy $R0 "themeName"
  StrCpy $R1 "$THEME_TEMP_DIR\app.config"
  Call GetConfigOption
  Pop $THEME_NAME
  StrCmp "$THEME_NAME" "" error_in_theme
  StrCpy $R0 "longAppName"
  StrCpy $R1 "$THEME_TEMP_DIR\app.config"
  Call GetConfigOption
  Pop $APP_NAME
  Goto no_tackon

error_in_theme:
  MessageBox MB_OK|MB_ICONEXCLAMATION "Error in theme"
  Goto no_tackon

non_zip_tackon:  ; non-zip tacked on file

  FileClose $0
  StrCpy $INITIAL_FEEDS "$TACKED_ON_FILE"

no_tackon:
  ClearErrors

  ; Is the app running?  Stop it if so.
TestRunning:
  ${nsProcess::FindProcess} "miro.exe" $R0
  StrCmp $R0 0 0 NotRunning
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
  "It looks like you're already running $APP_NAME.$\n\
Please shut it down before continuing." \
       IDOK TestRunning
  Quit
NotRunning:

TestOldRunning:
  ${nsProcess::FindProcess} "democracy.exe" $R0
  StrCmp $R0 0 0 NotOldRunning
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
  "It looks like you're running Democracy Player.$\n\
Please shut it down before continuing." \
       IDOK TestOldRunning
  Quit
NotOldRunning:

  ; Is the downloader running?  Stop it if so.
  ${nsProcess::FindProcess} "miro-downloader.exe" $R0
  StrCmp $R0 0 0 NotDownloaderRunning
  ${nsProcess::KillProcess} "miro-downloader.exe" $R0
NotDownloaderRunning:
  ; Is the downloader running?  Stop it if so.
  ${nsProcess::FindProcess} "democracy-downloader.exe" $R0
  StrCmp $R0 0 0 NotOldDownloaderRunning
  ${nsProcess::KillProcess} "democracy-downloader.exe" $R0
NotOldDownloaderRunning:

  ; Is the app already installed? Bail if so.
  ReadRegStr $R0 HKLM "${INST_KEY}" "InstallDir"
  StrCmp $R0 "" NotCurrentInstalled
 
prompt_for_uninstall:
  ; Should we uninstall the old one?
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
  "It looks like you already have a copy of $APP_NAME $\n\
installed.  Do you want to continue and overwrite it?" \
       IDOK UninstallCurrent
  Quit
UninstallCurrent:
  !insertmacro uninstall $R0
NotCurrentInstalled:

  ; Is the app already installed? Bail if so.
  ReadRegStr $R0 HKLM "${OLD_INST_KEY}" "InstallDir"
  StrCmp $R0 "" NotOldInstalled
 
  ; Should we uninstall the old one?
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
  "It looks like you already have a copy of Democracy Player $\n\
installed.  Do you want to continue and overwrite it?" \
       IDOK UninstallOld
  Quit
UninstallOld:
  !insertmacro uninstall $R0

  SetShellVarContext current
  ; Remove Start Menu shortcuts
  Delete "$SMPROGRAMS\Democracy Player\${OLD_RUN_SHORTCUT1}"
  Delete "$SMPROGRAMS\Democracy Player\${OLD_RUN_SHORTCUT2}"
  Delete "$SMPROGRAMS\Democracy Player\${OLD_UNINSTALL_SHORTCUT1}"
  Delete "$SMPROGRAMS\Democracy Player\${OLD_UNINSTALL_SHORTCUT2}"
  RMDir "$SMPROGRAMS\Democracy Player"

  ; Remove desktop and quick launch shortcuts
  Delete "$DESKTOP\${OLD_RUN_SHORTCUT1}"
  Delete "$DESKTOP\${OLD_RUN_SHORTCUT2}"
  Delete "$QUICKLAUNCH\${OLD_RUN_SHORTCUT1}"
  Delete "$QUICKLAUNCH\${OLD_RUN_SHORTCUT2}"

  SetShellVarContext all
  ; Remove Start Menu shortcuts
  Delete "$SMPROGRAMS\Democracy Player\${OLD_RUN_SHORTCUT1}"
  Delete "$SMPROGRAMS\Democracy Player\${OLD_RUN_SHORTCUT2}"
  Delete "$SMPROGRAMS\Democracy Player\${OLD_UNINSTALL_SHORTCUT1}"
  Delete "$SMPROGRAMS\Democracy Player\${OLD_UNINSTALL_SHORTCUT2}"
  RMDir "$SMPROGRAMS\Democracy Player"

  ; Remove desktop and quick launch shortcuts
  Delete "$DESKTOP\${OLD_RUN_SHORTCUT1}"
  Delete "$DESKTOP\${OLD_RUN_SHORTCUT2}"
  Delete "$QUICKLAUNCH\${OLD_RUN_SHORTCUT1}"
  Delete "$QUICKLAUNCH\${OLD_RUN_SHORTCUT2}"

  SetShellVarContext current

  ; Remove registry keys
  DeleteRegKey HKLM "${OLD_INST_KEY}"
  DeleteRegKey HKLM "${OLD_UNINST_KEY}"
  DeleteRegValue HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "Democracy Player"
  DeleteRegKey HKCR "Democracy.Player.1"

NotOldInstalled:
  !insertmacro MUI_LANGDLL_DISPLAY

  ; Make check boxes for unhandled file extensions.


  !insertmacro checkExtensionHandled ".torrent" ${SecRegisterTorrent}

  StrCpy $R0 "alwaysRegisterTorrents"
  StrCpy $R1 "$THEME_TEMP_DIR\app.config"
  Call GetConfigOption
  Pop $R0
  StrCmp $R0 "" DoneTorrentRegistration
  SectionGetFlags ${SecRegisterTorrent} $0
  IntOp $0 $0 | 17  ; Set register .torrents to selected and read only
  SectionSetFlags ${SecRegisterTorrent} $0

DoneTorrentRegistration:

  !insertmacro checkExtensionHandled ".miro" ${SecRegisterMiro}
  !insertmacro checkExtensionHandled ".democracy" ${SecRegisterDemocracy}
  !insertmacro checkExtensionHandled ".avi" ${SecRegisterAvi}
  !insertmacro checkExtensionHandled ".m4v" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpg" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpeg" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mp2" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mp4" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpe" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpv" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mpv2" ${SecRegisterMpg}
  !insertmacro checkExtensionHandled ".mp3" ${SecRegisterMp3}
  !insertmacro checkExtensionHandled ".mpa" ${SecRegisterMp3}
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

Function iHeartMiroInstall
  !insertmacro MUI_HEADER_TEXT "Install I Heart Miro?" "Go to ihearmiro.org to install the iHeartMiro firefox extension."
  !insertmacro MUI_INSTALLOPTIONS_DISPLAY "iHeartMiro-installer-page.ini"
FunctionEnd

Function iHeartMiroInstallLeave
;  !insertmacro MUI_INSTALLOPTIONS_READ $R0 "iHeartMiro-installer-page.ini" "Settings" "State"
;  IntCmp $R0 1 InstallHeart
;    SectionGetFlags ${SecIHeartMiro} $0
;    IntOp $0 $0 & ~${SF_SELECTED}
;    SectionSetFlags ${SecIHeartMiro} $0
;    Return
;  InstallHeart:
;    SectionGetFlags ${SecIHeartMiro} $0
;    IntOp $0 $0 | ${SF_SELECTED}
;    SectionSetFlags ${SecIHeartMiro} $0
;    Return
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

  ; We're Vista compatible now, so drop the compatability crap
  DeleteRegValue HKLM "Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers" "$INSTDIR\${CONFIG_EXECUTABLE}"
SectionEnd

Section "Uninstall" SEC91
  SetShellVarContext all

  ${un.GetParameters} $R0
  ${un.GetOptions} "$R0" "--theme" $THEME_NAME
  IfErrors continue

  StrCmp "$THEME_NAME" "" continue

  StrCpy $R0 "longAppName"
  StrCpy $R1 "$APPDATA\Participatory Culture Foundation\Miro\Themes\$THEME_NAME\app.config"
  Call un.GetConfigOption
  Pop $R0
  Delete "$APPDATA\Participatory Culture Foundation\Miro\Themes\$THEME_NAME\*.*"
  RMDir "$APPDATA\Participatory Culture Foundation\Miro\Themes\$THEME_NAME"

  !insertmacro MUI_STARTMENU_GETFOLDER Application $R1
  Delete "$SMPROGRAMS\$R1\$R0.lnk"
  Delete "$SMPROGRAMS\$R1\Uninstall $R0.lnk"

  Delete "$DESKTOP\$R0.lnk"
  Delete "$QUICKLAUNCH\$R0.lnk"

  RMDir "$SMPROGRAMS\$R1"

continue:
  ClearErrors
  !insertmacro uninstall $INSTDIR
  RMDIR "$PROGRAMFILES\${CONFIG_PUBLISHER}"

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
  DeleteRegValue HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "${CONFIG_LONG_APP_NAME}"
  DeleteRegKey HKCR "${CONFIG_PROG_ID}"

done:
  SetAutoClose true
SectionEnd
