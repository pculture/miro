;--------------------------------
; Example:
;--------------------------------
; Push "|" ;divider char
; Push "string1|string2|string3|string4|string5" ;input string
; Call SplitFirstStrPart
; Pop $R0 ;1st part ["string1"]
; Pop $R1 ;rest ["string2|string3|string4|string5"]
;--------------------------------

Function SplitFirstStrPart
  Exch $R0
  Exch
  Exch $R1
  Push $R2
  Push $R3
  StrCpy $R3 $R1
  StrLen $R1 $R0
  IntOp $R1 $R1 + 1
  loop:
    IntOp $R1 $R1 - 1
    StrCpy $R2 $R0 1 -$R1
    StrCmp $R1 0 exit0
    StrCmp $R2 $R3 exit1 loop
  exit0:
  StrCpy $R1 ""
  Goto exit2
  exit1:
    IntOp $R1 $R1 - 1
    StrCmp $R1 0 0 +3
     StrCpy $R2 ""
     Goto +2
    StrCpy $R2 $R0 "" -$R1
    IntOp $R1 $R1 + 1
    StrCpy $R0 $R0 -$R1
    StrCpy $R1 $R2
  exit2:
  Pop $R3
  Pop $R2
  Exch $R1 ;rest
  Exch
  Exch $R0 ;first
FunctionEnd


Function FindParamInList
	Exch $R1
	Exch
	Exch $R0
	Push $R2

_loop:
	Push ","
	Push $R1
	Call SplitFirstStrPart
	Pop $R2
	Pop $R1
	StrCmp $R2 "" +2
	StrCmp $R2 $R0 0 _loop
	StrCpy $R1 $R2

	Pop $R2
	Pop $R0
	Exch $R1
FunctionEnd


;---------------------------------------------------------------------------
; Macro to associate a logical name and actual section index to turn on/off.
;----------------------------------------------------------------------------

!macro OI_SELSEC_BY_CMDPARAM ONPARLIST OFFPARLIST PARNAME SECIDX

	Push $R0

	Push ${PARNAME}
	Push ${ONPARLIST}
	Call FindParamInList
	Pop $R0
	StrCmp $R0 "" +6
    SectionGetFlags ${SECIDX} $R0
	IfErrors +13 0
	    IntOp $R0 $R0 | ${SF_SELECTED}
	    SectionSetFlags ${SECIDX} $R0
		GoTo +10

	Push ${PARNAME}
	Push ${OFFPARLIST}
	Call FindParamInList
	Pop $R0
	StrCmp $R0 "" +5
    SectionGetFlags ${SECIDX} $R0
	IfErrors +3 0
	    IntOp $R0 $R0 & ${SECTION_OFF}
	    SectionSetFlags ${SECIDX} $R0

	Pop $R0

!macroend
