#include <windows.h>
#include <stdio.h>
#include <io.h>
#include "nsWindowsRestart.cpp"

#define XULRUNNER_BIN "Democracy.exe"
#define GRE_SUBDIRECTORY "xulrunner"

static int main(int, char**);

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR args, int) {
  return main(__argc, __argv);
}

int main(int argc, char **argv) {
  /* Find the binary running right now .. */
  char processPath[MAX_PATH];
  if (!::GetModuleFileName(NULL, processPath, sizeof(processPath))) {
    return 1;
  }

  /* .. and get the top-level installation directory from it. */
  char *lastSlash = strrchr(processPath, '\\');
  if (!lastSlash)
    return 1;
  *(lastSlash+1) = '\0';

  /* Set the current directory to the top-level installation
     directory. This is necessary for us to find our DLLs. */
  if (!::SetCurrentDirectory(processPath))
    return 1;

  /* Compute the path to the application config file. */
  char applicationIniPath[MAX_PATH];
  _snprintf(applicationIniPath, sizeof(applicationIniPath),
            "%sapplication.ini", processPath);
  
  /* Compute the path to the Xulrunner launcher binary. */
  char xulrunnerPath[MAX_PATH];
  _snprintf(xulrunnerPath, sizeof(xulrunnerPath),
            "%s%s", processPath, GRE_SUBDIRECTORY "\\" XULRUNNER_BIN);

  /* Create child argument array. */
  int childArgc = argc + 1;
  char **childArgv = (char **)malloc(sizeof(char *) * (childArgc + 1));
  childArgv[0] = xulrunnerPath;
  childArgv[1] = applicationIniPath;
  for(int i = 1; i < argc; i++)
    childArgv[i+1] = argv[i];
  childArgv[argc + 1] = NULL;

  /* Launch the application */
  BOOL ok = WinLaunchChild(xulrunnerPath, childArgc, childArgv);
  free(childArgv);
  return !ok;
}
