/* tackon.c -- NSIS plugin to read data tacked on to the end of a file
   Copyright (c) 2004 Nicholas Nassar
   Licensed under NSIS License see license.txt for details

   Based on ExDLL example plugin included in NSIS

   This plugin allows you to read data tack on the end of a NSIS .EXE
   file into a file. It's useful for situations where you need to
   include context specific data in an installer, but you don't want
   to regenerate the entire EXE or reverse engineer the structure.

   We use it as part of Blog Torrent to include torrents in EXE files

   The format of the file should be:
     Original .EXE
     DATA
     CRC32 (little-endian unsigned 32 bit integer)
     Size of Data in bytes (little-endian unsigned 32 bit integer)
     Unique ID (little-endian unsigned 32 bit integer)

   See tackon.php for an example of PHP code to tack on data

   To use this plugin:
   * Copy tackon.dll to your NSIS Plugins directory
   * Add a line containing "tackon::writeToFile filename" to your .NSI 
     script file
   * Recompile your installer using the new script
   * Optionally add data to the end of the file using a script such as
     the one provided

   If there is data tacked on to your installer, the plugin with
   output it to "filename"

   To compile using make/mingw:
     Move the tackon/ directory to the root of your NSIS source tree
     Set CC and STRIP variables in the Makefile appropriately
     run "make"

 */
#include <windows.h>
#include "tackon.h"
#include "Platform.h"

HINSTANCE g_hInstance;

HWND g_hwndParent;

extern unsigned long NSISCALL CRC32(unsigned long crc, const unsigned char *buf, unsigned int len);

void __declspec(dllexport) writeToFile(HWND hwndParent, int string_size, 
                                      char *variables, stack_t **stacktop)
{
  g_hwndParent=hwndParent;

  TACKON_INIT();

  {
    char filename[1024];
    char exename[1024];
    char buffer[32768];
    int attr;
    int exesize;
    HANDLE outfile;
    unsigned int datasize, crc, id,left,thischunk;
    unsigned long fcrc;
    DWORD rd;
    HANDLE exefile;

    //get command line parameter
    if (popstring(filename))
      MessageBox(g_hwndParent,"Please supply a filename for tackon::writeToFile",0,MB_OK);

    //get name of main exe file
    GetModuleFileName(NULL, exename, 1023);
    exename[1023]=0;

    //open the exe file as read only
    attr = GetFileAttributes(exename);
    exefile = CreateFile(exename,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,attr == INVALID_FILE_ATTRIBUTES ? 0 : attr,NULL);
    exesize = GetFileSize(exefile,NULL);

    //Read in CRC, size of data, and ID
    SetFilePointer(exefile,exesize-12,NULL,FILE_BEGIN);
    ReadFile(exefile,&crc,4,&rd,NULL);
    ReadFile(exefile,&datasize,4,&rd,NULL);
    ReadFile(exefile,&id,4,&rd,NULL);

    //If the ID is okay, extract the data
    if (id==560097380) {
      //Initialize CRC
      fcrc=0;

      //Open the output file
      outfile = CreateFile(filename, GENERIC_WRITE, 0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);

      //Set the pointer to the start of the data
      SetFilePointer(exefile,exesize-12-datasize,NULL,FILE_BEGIN);

      left = datasize;
      rd = 0;
      thischunk=0;

      //Write data out to file
      while ((left>0) && (thischunk==rd)) {
	//Read up to 32768 bytes
	if (left<32768)
	  thischunk=left;
	else
	  thischunk=32768;

	//Read data
	ReadFile(exefile,buffer,thischunk,&rd,NULL);
	//update the CRC
	fcrc=CRC32(fcrc,buffer,rd);
	left -=rd;
	//Write data
	WriteFile(outfile,buffer, rd, &rd,NULL);
      }
      //Complain if there were errors
      if ((crc!=fcrc)||(left>0)) {
	MessageBox(g_hwndParent,"Warning: error writing tacked on file!",0,MB_OK);
      }
    }

    CloseHandle(exefile);
    CloseHandle(outfile);
  }
}



BOOL WINAPI DllMain(HANDLE hInst, ULONG ul_reason_for_call, LPVOID lpReserved)
{
  g_hInstance=hInst;
	return TRUE;
}
