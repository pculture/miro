pref("toolkit.defaultChromeURI", "chrome://dtv/content/main.xul");
pref("toolkit.singletonWindowType", "main");

/* Allow files on local disk (such as those we autogenerate) to
   acquire the UniversalBrowserRead privilege, which is what's
   necessary to do XMLHttpRequests to arbitrary URLs (such as  our
   dispatch: handler.)

   NEEDS: careful security audit. Is there a way we can restrict this
   grant to just the HTML our template code generates?
*/
pref("capability.principal.codebase.dtv.granted", "UniversalBrowserRead");
pref("capability.principal.codebase.dtv.id", "file://");
pref("capability.principal.codebase.dtv.subjectName", "");

/* debugging prefs */
pref("browser.dom.window.dump.enabled", true);
pref("javascript.options.showInConsole", true);
pref("javascript.options.strict", true);
