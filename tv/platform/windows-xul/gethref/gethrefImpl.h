#ifndef gethrefImpl_h__
#define gethrefImpl_h__

#include "pcfIDTVGetHREF.h"

// {75616E9E-2948-49a8-A58B-4DF1EE43D94A}
#define GETHREF_CID { 0x75616e9e, 0x2948, 0x49a8, { 0xa5, 0x8b, 0x4d, 0xf1, 0xee, 0x43, 0xd9, 0x4a } }

#define GETHREF_CONTRACTID \
  "@participatoryculture.org/dtv/gethref;1"

class GetHREF : public pcfIDTVGetHREF
{
public:
  NS_DECL_ISUPPORTS
  NS_DECL_PCFIDTVGETHREF

  GetHREF();

private:
  ~GetHREF();
  
};

#endif // gethrefImpl_h__
