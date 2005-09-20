#include "MozillaBrowser.h"

// GRE SDK lacks do_CreateInstance. This function is given as an
// alternative here:
// http://www.mail-archive.org/mozilla-embedding@mozilla.org/msg04692.html
nsresult CreateInstance(const char *aContractID, const nsIID &aIID,
			void **aInstancePtr) {
  nsresult rv;

  nsCOMPtr<nsIComponentManager> compMgr;
  rv = NS_GetComponentManager(getter_AddRefs(compMgr));
  if (NS_FAILED(rv))
    return rv;

  return compMgr->CreateInstanceByContractID(aContractID, NULL, aIID,
					     aInstancePtr);
}


// NEEDS: would be nice to have finalization too, but I don't know how to
// make Python do that right now.
nsresult startMozilla(void) {
  nsresult rv;

  // Should not be necessary to protect this with a mutex since Python
  // is secretly single-threaded (NEEDS: check)
  static int initialized = 0;
  if (initialized)
    return NS_OK;
  initialized = 1;

#ifdef HARDCODED_GRE_PATH
  // We were built with a fixed path to our GRE. Tell Mozilla to skip its
  // detection logic and use that GRE.
  {
    char buf[2048];
    snprintf(buf, sizeof(buf), "GRE_HOME=%s", HARDCODED_GRE_PATH);
    fflush(stdout);
    PR_SetEnv(buf);
  }
#endif

  return GRE_Startup();
}

wchar_t *stripBOM(wchar_t *str) {
  // If the string starts with a byte-order mark, and it indicates the
  // native byte order you'd assume anyway on this platform, strip
  // it. This simple logic is enough to handle the usual case created
  // by Python.
  if (!str)
    return NULL;

  wchar_t *source = *str == 0xfeff ? str+1 : str;
  int len = wcslen(source) + 1;
  wchar_t *ret = (wchar_t *)malloc(sizeof(wchar_t) * len);
  wmemcpy(ret, source, len);

  printf("stripBOM returning string of length %d == %S\n", wcslen(ret), ret);
  return ret;
}
