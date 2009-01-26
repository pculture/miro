/*
 * Miro - an RSS based video player application
 * Copyright (C) 2005-2009 Participatory Culture Foundation
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
 *
 * In addition, as a special exception, the copyright holders give
 * permission to link the code of portions of this program with the OpenSSL
 * library.
 *
 * You must obey the GNU General Public License in all respects for all of
 * the code used other than OpenSSL. If you modify file(s) with this
 * exception, you may extend this exception to your version of the file(s),
 * but you are not obligated to do so. If you do not wish to do so, delete
 * this exception statement from your version. If you delete this exception
 * statement from all source files in the program, then also delete it here.
**/

/*
 * Init.cpp
 *
 * Initialize and Shutdown XPCom
 */

#include <stdlib.h>

#include "nsCOMPtr.h"
#include "nsEmbedString.h"
#include "nsILocalFile.h"
#include "nsXPCOMGlue.h" 
#include "pref/nsIPref.h"
#include "xulapp/nsXULAppAPI.h"
#include "xpcom/nsServiceManagerUtils.h"

#include "Init.h"

XRE_InitEmbeddingType XRE_InitEmbedding;
XRE_TermEmbeddingType XRE_TermEmbedding; 

nsresult init_xulrunner(const char* xul_dir, const char* app_dir)
{
    nsresult rv;

    char xpcom_dll[_MAX_PATH ];
    if(strlen(xul_dir) >= _MAX_PATH) {
        return NS_ERROR_FAILURE;
    }
    strcpy(xpcom_dll, xul_dir);
    strncat(xpcom_dll, "\\xpcom.dll", _MAX_PATH - strlen(xpcom_dll));

    rv = XPCOMGlueStartup(xpcom_dll);
    if (NS_FAILED(rv)) {
        printf("GLUE STARTUP FAILED\n");
        return rv;
    }

    const nsDynamicFunctionLoad dynamicSymbols[] = {
        { "XRE_InitEmbedding", (NSFuncPtr*) &XRE_InitEmbedding },
        { "XRE_TermEmbedding", (NSFuncPtr*) &XRE_TermEmbedding },
        { nsnull, nsnull }
    }; 
    XPCOMGlueLoadXULFunctions(dynamicSymbols);

    nsCOMPtr<nsILocalFile> xul_dir_file;
    rv = NS_NewNativeLocalFile(nsEmbedCString(xul_dir), PR_FALSE,
            getter_AddRefs(xul_dir_file));
    NS_ENSURE_SUCCESS(rv, rv);

    nsCOMPtr<nsILocalFile> app_dir_file;
    rv = NS_NewNativeLocalFile(nsEmbedCString(app_dir), PR_FALSE,
                getter_AddRefs(app_dir_file));
    NS_ENSURE_SUCCESS(rv, rv);

    rv = XRE_InitEmbedding(xul_dir_file, app_dir_file, 0, 0, 0);
    NS_ENSURE_SUCCESS(rv, rv);
    return NS_OK;
}


nsresult setup_user_agent(const char* vendor, const char* vendor_sub, 
        const char* comment)
{
    nsresult rv;
    nsCOMPtr<nsIPref> prefs(do_GetService(NS_PREF_CONTRACTID, &rv));
    NS_ENSURE_SUCCESS(rv, rv);
    rv = prefs->SetCharPref("general.useragent.vendor", vendor);
    NS_ENSURE_SUCCESS(rv, rv);
    rv = prefs->SetCharPref("general.useragent.vendorSub", vendor_sub);
    NS_ENSURE_SUCCESS(rv, rv);
    rv = prefs->SetCharPref("general.useragent.vendorComment", comment);
    NS_ENSURE_SUCCESS(rv, rv);
    return NS_OK;
}

void shutdown_xulrunner()
{
    XRE_TermEmbedding();
    XPCOMGlueShutdown();
}
