!define PRODUCT_NAME "DTV"
!define PRODUCT_VERSION '${VERSION}'
!define PRODUCT_GROUP "PCF"
!define PRODUCT_PUBLISHER "PCF Devel Team"
!define PRODUCT_WEB_SITE "http://www.participatoryculture.org"
!define PRODUCT_DIR_REGKEY "Software\PCF\DTV"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"
!define MUI_STARTMENUPAGE_DEFAULTFOLDER "Participatory Culture Foundation"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile ..\dtv-${VERSION}.exe
InstallDir "$PROGRAMFILES\Participatory Culture Foundation\DTV"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" "Install_Dir"
SetCompressor lzma

SetOverwrite ifnewer
CRCCheck on

Icon dtv.ico

Var STARTMENU_FOLDER

!include "MUI.nsh"

    !define MUI_WELCOMEPAGE_TITLE_3LINES
    !insertmacro MUI_PAGE_WELCOME
  ; License page
    !insertmacro MUI_PAGE_LICENSE "license.txt"
    !define MUI_COMPONENTSPAGE_TEXT_COMPLIST "Please, choose which optional components to install"
    !insertmacro MUI_PAGE_COMPONENTS
    !insertmacro MUI_PAGE_DIRECTORY

    !insertmacro MUI_PAGE_STARTMENU Application $STARTMENU_FOLDER
    !insertmacro MUI_PAGE_INSTFILES
  ; Finish page
    !define MUI_FINISHPAGE_RUN "$INSTDIR\dtv.exe"
    !define MUI_FINISHPAGE_LINK "Visit the PCF DTV Website"
    !define MUI_FINISHPAGE_LINK_LOCATION "http://www.participatoryculture.org/"
    !define MUI_FINISHPAGE_NOREBOOTSUPPORT
    !insertmacro MUI_PAGE_FINISH

; Uninstaller pages
    !insertmacro MUI_UNPAGE_CONFIRM
    !insertmacro MUI_UNPAGE_INSTFILES
    !insertmacro MUI_UNPAGE_FINISH

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

!insertmacro MUI_RESERVEFILE_LANGDLL

  !insertmacro MUI_RESERVEFILE_INSTALLOPTIONS

Section "-DTV"
  SetShellVarContext all
  SetOutPath "$INSTDIR"

  File  dtv.exe
  File  dtv.ico
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

    !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    CreateDirectory "$SMPROGRAMS\$STARTMENU_FOLDER"
    CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\DTV.lnk" "$INSTDIR\dtv.exe" "" "$INSTDIR\dtv.ico"
    CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\Uninstall DTV.lnk" "$INSTDIR\uninstall.exe"
    !insertmacro MUI_STARTMENU_WRITE_END

SectionEnd

Section /o "Desktop icon" SecDesktop
  CreateShortcut "$DESKTOP\DTV.lnk" "$INSTDIR\dtv.exe" "" "$INSTDIR\dtv.ico"
SectionEnd

Function .onInit
  ReadRegStr $R0  ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
  "UninstallString"
  StrCmp $R0 "" done
 
  MessageBox MB_YESNO|MB_ICONEXCLAMATION \
  "DTV has already been installed. $\nDo you want to remove \
  the previous version before installing $(^Name) ?" \
  IDNO done
  
  ;Run the uninstaller
  ;uninst:
    ClearErrors
    ExecWait '$R0 _?=$INSTDIR' ;Do not copy the uninstaller to a temp file
  done:
  !insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "InstallDir" $INSTDIR
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "Version" "${VERSION}"
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\dtv.exe"

  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
    "DisplayName" "$(^Name)"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
    "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
    "DisplayIcon" "$INSTDIR\dtv.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
    "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
    "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
    "Publisher" "${PRODUCT_PUBLISHER}"
SectionEnd

Section "Uninstall" SEC91
  SetShellVarContext all

  RMDir "$SMPROGRAMS\Participatory Culture Foundation"
  RMDir /r "$SMPROGRAMS\Participatory Culture Foundation"
  RMDir /r $INSTDIR
  DeleteRegKey HKLM Software\PCF

  DeleteRegKey HKLM \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

!insertmacro MUI_STARTMENU_GETFOLDER Application $R0
  Delete "$SMPROGRAMS\$R0\DTV.lnk"
  Delete "$SMPROGRAMS\$R0\Uninstall DTV.lnk"
  Delete "$DESKTOP\DTV.lnk"
  RMDir "$R0"

  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
  SetAutoClose true
SectionEnd
