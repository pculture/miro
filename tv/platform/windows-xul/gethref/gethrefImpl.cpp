/*
 * Miro - an RSS based video player application
 * Copyright (C) 2005-2007 Participatory Culture Foundation
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
*/

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
