;
; OCSetupHlp.nsh
; --------------
;
; OpenCandy Helper Include File
;
; This file defines a few macros that need to be called
; from your main installer script in order to initialize and
; setup OpenCandy.
;
; Copyright (c) 2008 - OpenCandy, Inc.
;

; Local Variables

Var OCUseOfferPage
Var OCPageTitle
Var OCPageDesc
Var OCDetached
Var OCDialog
Var OCProductKey

; Registry key for OpenCandy's Download Manager

; TODO: do we need this ?
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\DLMgr.exe"

;
; Install Functions
; -----------------
;

;
; InitOpenCandy
;
; Performs initialization of the OpenCandy DLL
; and checks for available offers to present.
;
; Parameters are:
;
; PublisherName : Your publisher name (will be provided by OpenCandy)
; Key           : Your product key (will be provided by OpenCandy)
; Secret        : Your product code (will be provided by OpenCandy)
;

!macro OpenCandyInit PublisherName Key Secret

  ; We need to be loaded throughout the setup
  ; as we will uload ourselves when necessary
  
  SetPluginUnload alwaysoff

  Push $0
  Push $1
  Push $2
  Push $3
  Push $4

  IntOp $OCDetached 0 + 1

  SetOutPath $TEMP\OpenCandy ; create temp directory
  File OCSetupHlp.dll	     ; copy dll there

  StrCpy $0 ${PublisherName}	     ; Publisher

  StrCpy $1 ${Key}	; Product "Key"
  StrCpy $2 ${Secret}	; Secret

  StrCpy $OCProductKey ${Key}

  ; TODO: CHANGE THAT
  StrCpy $3 "en" ; hardcoded english test for now

  System::Call 'OCSetupHlp::OCInitA(t, t, t, t)i(r0, r1, r2 ,r3).r4? c'

  ${If} $4 == 0
	IntOp $OCUseOfferPage 1 + 0

	System::Call 'OCSetupHlp::OCGetBannerInfo(t, t)i(.r0, .r1).r2? c'

	${If} $2 == 3
		StrCpy $OCPageTitle $0
		StrCpy $OCPageDesc $1
	${ElseIf} $2 == 1
		StrCpy $OCPageDesc " "
	${ElseIf} $2 == 2
		StrCpy $OCPageTitle " "
	${Else}
		StrCpy $OCPageTitle " "
		StrCpy $OCPageDesc " "
	${EndIf}
  ${Else}
	IntOp $OCUseOfferPage 0 + 0
	SetPluginUnload manual
	; Do nothing (but let the installer unload the System dll)
	System::Free 0
  ${EndIf}

  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0

!macroend

;
; OpenCandyPageStartFn
; --------------------
;
; Decides if there is an offer to show and
; if so, sets up the offer page for NSIS
;
; You do not need to call this function, it just
; needs to be a parameter to the custom page
; declared in your setup along with your other pages
;

Function OpenCandyPageStartFn
  Push $0
  ${If} $OCUseOfferPage == 1

    ${If} $OCDetached == 0
		System::Call 'OCSetupHlp::OCDetach()i.r0? c'
		IntOp $OCDetached 0 + 1
    ${EndIf}

	nsDialogs::Create /NOUNLOAD 1018
	Pop $OCDialog

	${If} $OCDialog == error
		Abort
	${Else}

  	  !insertmacro MUI_HEADER_TEXT $OCPageTitle $OCPageDesc

 	  IntOp $OCDetached 0 + 0

	  System::Call 'OCSetupHlp::OCNSISAdjust(i, i, i, i, i)i($OCDialog, 14,70, 470, 228).r0? c'

	  System::Call 'OCSetupHlp::OCRunDialog(i, i, i, i)i($OCDialog, 240, 240 ,240).r0? c'

	  nsDialogs::Show
	  
	${EndIf}

  ${EndIf}
  Pop $0
FunctionEnd

;
; OpenCandyPageLeaveFn
; --------------------
;
; Decides there if it is ok to leave the
; page and continues with setup
;
; You do not need to call this function, it just
; needs to be a parameter to the custom page
; declared in your setup along with your other pages
;

Function OpenCandyPageLeaveFn
	Push $0
	Push $1
	Push $2
	System::Call 'OCSetupHlp::OCGetOfferState()i.r0? c'
	${If} $0 < 0
		StrCpy $1 "PleaseChoose"
		StrCpy $2 "                                                                                                                   "
		System::Call 'OCSetupHlp::OCGetMsg(t,t)i(r1,.r2).r0? c'
		MessageBox MB_ICONINFORMATION $2
		Abort
	${Else}
		System::Call 'OCSetupHlp::OCDetach()i.r0? c'
		IntOp $OCDetached 0 + 1
	${EndIf}
	Pop $2
	Pop $1
	Pop $0
FunctionEnd

;
; OpenCandyOnInstSuccess
; ----------------------
;
; This macro needs to be called from the
; NSIS function .onInstSuccess to signal
; a successful installation of the product
; and launch installation of the recommended
; software if any was selected by the user
;

!macro OpenCandyOnInstSuccess

	System::Call 'OCSetupHlp::OCSignalProductInstalled()i.r0? c'

        ; Check if we are in normal
        ; or embedded mode and run accordingy

        Push $0
        Push $1

	StrCpy $1 "                                                                                                                   "
	
	System::Call 'OCSetupHlp::OCGetOfferType(t)i(.r1).r0? c'

        ${If} $0 == 1 ; OC_OFFER_TYPE_NORMAL
 	      StrCpy $0 "$INSTDIR\OpenCandy\DLMgr.exe"
	      System::Call 'OCSetupHlp::OCExecuteOffer(t)i(r0).r0? c'
	      Exec '"$INSTDIR\OpenCandy\DLMgr.exe"'
        ${EndIf}
        
	Pop $1
	Pop $0

!macroend

;
; OpenCandyOnGuiEnd
; -----------------
;
; This needs to be called from the NSIS
; function .onGUIEnd to properly unload
; the OpenCandy DLL. We need to have the DLL
; loaded until then as to be able to start
; the recommended software setup at the
; very end of the NSIS install process
;

!macro OpenCandyOnGuiEnd

  ${If} $OCUseOfferPage != 0
    ${If} $OCDetached == 0
		System::Call 'OCSetupHlp::OCDetach()i.r0? c'
		IntOp $OCDetached 0 + 1
    ${EndIf}
	IntOp $OCUseOfferPage 0 + 0
	SetPluginUnload manual
	; do nothing (but let the installer unload the System dll)
	System::Free 0
  ${EndIf}
  
!macroend

;
; OpenCandyInstallDownloadManager
; -------------------------------
;
; This macro performs the installation of OpenCandy's
; download manager in order to provide the recommended
; software package later on. You need to call this
; macro from a section during the install to make sure
; it is installed with your product
;
;

!macro OpenCandyInstallDownloadManager

  CreateDirectory "$INSTDIR\OpenCandy"
  SetOutPath "$INSTDIR\OpenCandy"
  SetOverwrite ifnewer

  File OCSetupHlp.dll
  File DLMgr.exe
  
  ; Check if we are in normal
  ; or embedded mode and run accordingy

  Push $0
  Push $1

  StrCpy $1 "                                                                                                                   "

  System::Call 'OCSetupHlp::OCGetOfferType(t)i(.r1).r0? c'

  ${If} $0 == 2 ; OC_OFFER_TYPE_EMBEDDED
      StrCpy $0 "$INSTDIR\OpenCandy\DLMgr.exe"
      System::Call 'OCSetupHlp::OCExecuteOffer(t)i(r0).r0? c'
      Exec '"$INSTDIR\OpenCandy\DLMgr.exe" /S$OCProductKey'
  ${EndIf}

  Pop $1
  Pop $0

  SetOutPath "$INSTDIR"

!macroend

;
; Uninstall Functions
; -------------------
;

;
; OpenCandyUninstallDownloadManager
; ---------------------------------
;
; Effectively uninstalls the OpenCandy Download manager
; You need to call this macro from your uninstall section.
;
;

!macro OpenCandyUninstallDownloadManager
  Delete "$INSTDIR\OpenCandy\OCSetupHlp.dll"
  Delete "$INSTDIR\OpenCandy\DLMgr.exe"
!macroend

;
; OpenCandyProductUninstallComplete
; ---------------------------------
;
; Signals to OpenCandy that your product was uninstalled
; You need to call this macro from your uninstall section.
;
;

!macro OpenCandyProductUninstallComplete
    Push $0
	Push $OutDir
	SetOutPath "$INSTDIR\OpenCandy"
	StrCpy $0 '159b52283eb914d3b721da65cf5ad4c0'
	System::Call 'OCSetupHlp::OCSignalProductUnInstalled(t)i(r0).r0? c'

	Pop $0
	SetOutPath $0
	Pop $0
!macroend

; END of OpenCandy Helper Include file
