#include <stdio.h>
#define MOZILLA_STRICT_API

#include "gethrefImpl.h"
#include "nsIGenericFactory.h" 

NS_GENERIC_FACTORY_CONSTRUCTOR(GetHREF)

static nsModuleComponentInfo components[] =
{
  {
    "Turn a nsIBaseWindow into a Windows HREF",
    GETHREF_CID,
    GETHREF_CONTRACTID,
    GetHREFConstructor
  },
};

NS_IMPL_NSGETMODULE(minimizeToTrayModule, components)
