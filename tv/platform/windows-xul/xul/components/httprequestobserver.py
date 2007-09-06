import logging
from xpcom import components
import locale

nsIObserver = components.interfaces.nsIObserver
nsIHttpChannel = components.interfaces.nsIHttpChannel

class HTTPRequestObserver:
    _com_interfaces_ = [ nsIObserver ]
    _reg_clsid_ = "{59a204b1-7304-45bc-807f-4d108249770f}"
    _reg_contractid_ = "@participatoryculture.org/dtv/httprequestobserver;1"
    _reg_desc_ = "Democracy HTTP Request Observer"

    def observe(self, subject, topic, data):
        if topic == "http-on-modify-request":
              channel = subject.queryInterface(nsIHttpChannel)
              currentLanguages = channel.getRequestHeader('Accept-Language')
              language = locale.getdefaultlocale()[0].replace('_', '-')
              channel.setRequestHeader("Accept-Language", language, False)
              channel.setRequestHeader("Accept-Lanugage", currentLanguages, True)
              channel.setRequestHeader("X-Miro", "1", False);
