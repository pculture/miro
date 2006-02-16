pref("toolkit.defaultChromeURI", "chrome://dtv/content/main.xul");
pref("toolkit.singletonWindowType", "main");
pref("extensions.pyxpcom.embedded", true);

pref("security.warn_entering_secure", false);
pref("security.warn_entering_weak", false);
pref("security.warn_leaving_secure", false);
pref("security.warn_submit_insecure", false);
pref("security.warn_viewing_mixed", false);

/* NEEDS: it'd be nice to have an automated way to get the DTV version
   number into this */
pref("general.useragent.vendor", "DTV");
pref("general.useragent.vendorSub", "0.8.0");
pref("general.useragent.vendorComment", "http://participatoryculture.org");

/* debugging prefs */
pref("browser.dom.window.dump.enabled", true);
pref("javascript.options.showInConsole", true);
pref("javascript.options.strict", true);
