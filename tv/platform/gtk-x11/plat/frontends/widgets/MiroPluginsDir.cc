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

/*
 * MiroPluginsDir.cc
 *
 * Remove the list of plugins directories, so we don't load any plugins.
 */

#include "MiroPluginsDir.h"
#include "nsAppDirectoryServiceDefs.h"
#include "nsCOMPtr.h"
#include "nsIDirectoryService.h"
#include "nsISimpleEnumerator.h"
#include "nsServiceManagerUtils.h"

/*
 * EmptySimpleEnumerator is an enumerator that doesn't yield any values.  We
 * use this to return an empty plugin directory list.
 */
class EmptySimpleEnumerator : public nsISimpleEnumerator
{
public:
  NS_DECL_ISUPPORTS
  NS_DECL_NSISIMPLEENUMERATOR
};


NS_IMPL_ISUPPORTS1(EmptySimpleEnumerator, nsISimpleEnumerator)

NS_IMETHODIMP EmptySimpleEnumerator::HasMoreElements(PRBool *_retval)
{
    *_retval = PR_FALSE;
    return NS_OK;
}

NS_IMETHODIMP EmptySimpleEnumerator::GetNext(nsISupports **_retval)
{
    /* Shouldn't get here because we return False in HasMoreElements */
    return NS_ERROR_NOT_IMPLEMENTED;
}

class MiroDirectoryServiceProvider : public nsIDirectoryServiceProvider2
{
public:
  NS_DECL_ISUPPORTS
  NS_DECL_NSIDIRECTORYSERVICEPROVIDER
  NS_DECL_NSIDIRECTORYSERVICEPROVIDER2
};

NS_IMPL_ISUPPORTS2(MiroDirectoryServiceProvider, nsIDirectoryServiceProvider,
        nsIDirectoryServiceProvider2)

NS_IMETHODIMP MiroDirectoryServiceProvider::GetFile(const char *prop, PRBool *persistent, nsIFile **_retval)
{
    // We don't want to overide any of these values
    *_retval = nsnull;
    return NS_OK;
}

NS_IMETHODIMP MiroDirectoryServiceProvider::GetFiles(const char *prop, nsISimpleEnumerator **_retval)
{
    // Don't mess with most values, but overide NS_APP_PLUGINS_DIR_LIST
    *_retval = nsnull;
    if(!strcmp(prop, NS_APP_PLUGINS_DIR_LIST)) {
        *_retval = new EmptySimpleEnumerator();
        (*_retval)->AddRef();
    }

    return NS_OK;
}

nsresult setup_plugins_dir()
{
    nsresult rv;

    nsCOMPtr<nsIDirectoryService> dir_service(
                do_GetService(NS_DIRECTORY_SERVICE_CONTRACTID, &rv));
    NS_ENSURE_SUCCESS(rv, rv);

    MiroDirectoryServiceProvider *dir_provider = new MiroDirectoryServiceProvider();
    dir_provider->AddRef();

    rv = dir_service->RegisterProvider(dir_provider);
    NS_ENSURE_SUCCESS(rv, rv);

    return NS_OK;
}
