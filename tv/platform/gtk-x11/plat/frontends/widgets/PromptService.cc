/*
# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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
 * PromptService.cc
 *
 * Dummy prompt service implementation that does nothing.  (This is better
 * than the default, which hangs).
 */

#include <nsIPromptService.h>
#include <nsIGenericFactory.h>
#include <nsIComponentRegistrar.h>

#ifdef PCF_USING_XULRUNNER19
#include <nsComponentManagerUtils.h>
#endif

#include <nsCOMPtr.h>
#include <nsEmbedString.h>
#include <nsStringAPI.h>
#include <nsXPCOM.h>
#include "PromptService.h"

extern "C" void log_warning(const char *msg);

void log_dialog(const PRUnichar* title, const PRUnichar* text) {
    nsEmbedString titleString(title), textString(text);
    nsEmbedCString titleConverted, textConverted;

    NS_UTF16ToCString(titleString, NS_CSTRING_ENCODING_UTF8, titleConverted);
    NS_UTF16ToCString(textString, NS_CSTRING_ENCODING_UTF8, textConverted);

    nsEmbedCString msg("Ignoring Dialog -- title: ");
    msg.Append(titleConverted);
    msg.Append(" text: ");
    msg.Append(textConverted);
    log_warning(msg.get());
}

// {A2112D6A-0E28-421f-B46A-25C0B308CBD0}
#define NS_PROMPTSERVICE_CID \
    {0xa2112d6a, 0x0e28, 0x421f, {0xb4, 0x6a, 0x25, 0xc0, 0xb3, 0x8, \
                                     0xcb, 0xd0}}

class MiroPromptService : public nsIPromptService
{
public:
  NS_DECL_ISUPPORTS
  NS_DECL_NSIPROMPTSERVICE

  MiroPromptService();

private:
  ~MiroPromptService();

protected:
  /* additional members */
};

/* Implementation file */
NS_IMPL_ISUPPORTS1(MiroPromptService, nsIPromptService)

MiroPromptService::MiroPromptService()
{
}

MiroPromptService::~MiroPromptService()
{
}

/* void alert (in nsIDOMWindow aParent, in wstring aDialogTitle, in wstring aText); */
NS_IMETHODIMP MiroPromptService::Alert(nsIDOMWindow *aParent, const PRUnichar *aDialogTitle, const PRUnichar *aText)
{
    log_dialog(aDialogTitle, aText);
    return NS_OK;
}

/* void alertCheck (in nsIDOMWindow aParent, in wstring aDialogTitle, in wstring aText, in wstring aCheckMsg, inout boolean aCheckState); */
NS_IMETHODIMP MiroPromptService::AlertCheck(nsIDOMWindow *aParent, const PRUnichar *aDialogTitle, const PRUnichar *aText, const PRUnichar *aCheckMsg, PRBool *aCheckState)
{
    log_dialog(aDialogTitle, aText);
    return NS_OK;
}

/* boolean confirm (in nsIDOMWindow aParent, in wstring aDialogTitle, in wstring aText); */
NS_IMETHODIMP MiroPromptService::Confirm(nsIDOMWindow *aParent, const PRUnichar *aDialogTitle, const PRUnichar *aText, PRBool *_retval)
{
    log_dialog(aDialogTitle, aText);
    return NS_OK;
}

/* boolean confirmCheck (in nsIDOMWindow aParent, in wstring aDialogTitle, in wstring aText, in wstring aCheckMsg, inout boolean aCheckState); */
NS_IMETHODIMP MiroPromptService::ConfirmCheck(nsIDOMWindow *aParent, const PRUnichar *aDialogTitle, const PRUnichar *aText, const PRUnichar *aCheckMsg, PRBool *aCheckState, PRBool *_retval)
{
    log_dialog(aDialogTitle, aText);
    return NS_OK;
}

/* PRInt32 confirmEx (in nsIDOMWindow aParent, in wstring aDialogTitle, in wstring aText, in unsigned long aButtonFlags, in wstring aButton0Title, in wstring aButton1Title, in wstring aButton2Title, in wstring aCheckMsg, inout boolean aCheckState); */
NS_IMETHODIMP MiroPromptService::ConfirmEx(nsIDOMWindow *aParent, const PRUnichar *aDialogTitle, const PRUnichar *aText, PRUint32 aButtonFlags, const PRUnichar *aButton0Title, const PRUnichar *aButton1Title, const PRUnichar *aButton2Title, const PRUnichar *aCheckMsg, PRBool *aCheckState, PRInt32 *_retval)
{
    log_dialog(aDialogTitle, aText);
    return NS_OK;
}

/* boolean prompt (in nsIDOMWindow aParent, in wstring aDialogTitle, in wstring aText, inout wstring aValue, in wstring aCheckMsg, inout boolean aCheckState); */
NS_IMETHODIMP MiroPromptService::Prompt(nsIDOMWindow *aParent, const PRUnichar *aDialogTitle, const PRUnichar *aText, PRUnichar **aValue, const PRUnichar *aCheckMsg, PRBool *aCheckState, PRBool *_retval)
{
    log_dialog(aDialogTitle, aText);
    return NS_OK;
}

/* boolean promptUsernameAndPassword (in nsIDOMWindow aParent, in wstring aDialogTitle, in wstring aText, inout wstring aUsername, inout wstring aPassword, in wstring aCheckMsg, inout boolean aCheckState); */
NS_IMETHODIMP MiroPromptService::PromptUsernameAndPassword(nsIDOMWindow *aParent, const PRUnichar *aDialogTitle, const PRUnichar *aText, PRUnichar **aUsername, PRUnichar **aPassword, const PRUnichar *aCheckMsg, PRBool *aCheckState, PRBool *_retval)
{
    log_dialog(aDialogTitle, aText);
    return NS_OK;
}

/* boolean promptPassword (in nsIDOMWindow aParent, in wstring aDialogTitle, in wstring aText, inout wstring aPassword, in wstring aCheckMsg, inout boolean aCheckState); */
NS_IMETHODIMP MiroPromptService::PromptPassword(nsIDOMWindow *aParent, const PRUnichar *aDialogTitle, const PRUnichar *aText, PRUnichar **aPassword, const PRUnichar *aCheckMsg, PRBool *aCheckState, PRBool *_retval)
{
    log_dialog(aDialogTitle, aText);
    return NS_OK;
}

/* boolean select (in nsIDOMWindow aParent, in wstring aDialogTitle, in wstring aText, in PRUint32 aCount, [array, size_is (aCount)] in wstring aSelectList, out long aOutSelection); */
NS_IMETHODIMP MiroPromptService::Select(nsIDOMWindow *aParent, const PRUnichar *aDialogTitle, const PRUnichar *aText, PRUint32 aCount, const PRUnichar **aSelectList, PRInt32 *aOutSelection, PRBool *_retval)
{
    log_dialog(aDialogTitle, aText);
    return NS_OK;
}

NS_GENERIC_FACTORY_CONSTRUCTOR(MiroPromptService);

static const nsModuleComponentInfo componentInfo = { 
    "Miro Prompt Service",
    NS_PROMPTSERVICE_CID,
    "@mozilla.org/embedcomp/prompt-service;1",
    MiroPromptServiceConstructor
};

nsresult installPromptService()
{
    nsresult rv;

    nsCOMPtr<nsIComponentRegistrar> cr;
    rv = NS_GetComponentRegistrar(getter_AddRefs(cr));
    NS_ENSURE_SUCCESS(rv, rv);

    nsCOMPtr<nsIGenericFactory> componentFactory;
#ifndef PCF_USING_XULRUNNER19
    rv = NS_NewGenericFactory(getter_AddRefs(componentFactory),
           &componentInfo);
#else
    componentFactory = do_CreateInstance ("@mozilla.org/generic-factory;1", &rv);
#endif
    NS_ASSERTION(NS_SUCCEEDED(rv), "Unable to construct factory for component");
#ifdef PCF_USING_XULRUNNER19
    componentFactory->SetComponentInfo(&componentInfo);
#endif
    
    rv = cr->RegisterFactory(componentInfo.mCID, componentInfo.mDescription,
            componentInfo.mContractID, componentFactory);
    NS_ASSERTION(NS_SUCCEEDED(rv), "Unable to register factory for component");

    return rv;
}
