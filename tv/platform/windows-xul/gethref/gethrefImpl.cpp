#include <windows.h>
#include "gethrefImpl.h"
#include "pcfIDTVGetHREF.h"

#include "nsIBaseWindow.h"
#include <prtypes.h>

NS_IMPL_ISUPPORTS1(GetHREF,pcfIDTVGetHREF)

GetHREF::GetHREF()
{
}

GetHREF::~GetHREF()
{
}

NS_IMETHODIMP 
GetHREF::Getit(nsIBaseWindow *window, PRInt32 *href) {
  nsresult rv;
  nativeWindow nativeSon;
  rv = window->GetParentNativeWindow( &nativeSon );
  NS_ENSURE_SUCCESS(rv, rv);
  *href = NS_REINTERPRET_CAST(PRInt32, nativeSon);
  return NS_OK;
}
