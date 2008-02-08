/*
# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.
*/

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
