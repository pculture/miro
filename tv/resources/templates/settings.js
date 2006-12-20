<script type="text/javascript">
    <!-- // Protect from our XML parser, which doesn't know to protect <script>

    var feedSettingsTimeout = null;
    var settingsMode = 'closed';

    function showSettings()
    {
	if(settingsMode == 'open') return hideSettings();
	if(settingsMode == 'animating') return;
        var feedSettings = document.getElementById("feed-settings");
        var closeButton = document.getElementById("feed-settings-close-button");
        feedSettings.style.display = "block";
        feedSettings.style.top = "-224px";
        closeButton.style.display = "none";
        var startTop = -147;
        var endTop = 77;
        var steps = 5;
        var stepSize = (endTop - startTop) / steps;
        var currentStep = 0;
        function iteration() {
           currentStep += 1;
           var top = Math.round(startTop + (currentStep * stepSize));
           feedSettings.style.top = top + "px";
           if(currentStep != steps) {
                feedSettingsTimeout = setTimeout(iteration, 50);
           } else {
                feedSettingsTimeout = null;
		closeButton.style.display = "block";
		settingsMode = 'open';
           }
        }
        feedSettingsTimeout = setTimeout(iteration, 50);
	settingsMode = 'animating';
        return false;
    }

    function hideSettings()
    {
        if(feedSettingsTimeout) {
            clearTimeout(feedSettingsTimeout);
	    feedSettingsTimeout = null;
        }
        var feedSettings = document.getElementById("feed-settings");
	feedSettings.style.display = "none";
	settingsMode = 'closed';
	return false;
    }

    function setAutoDownloadableFeed()
    {
        var url = 'action:setAutoDownloadableFeed';
        url += '?feed=' + document.forms['setAuto']['feed'].value;
        if (document.forms['setAuto'].automatic.checked)
            url += '&automatic=1';
        else
            url += '&automatic=0';
        eventURL(url);
    }

    function setAutoDownloadGets()
    {
        var url = "action:setGetEverything";
        var idx = document.forms['settings']['autoDownloadGets'].selectedIndex;
        
        url += '?feed=' + document.forms['setAuto']['feed'].value;
        url += "&everything=" + document.forms['settings']['autoDownloadGets'].options[idx].value;

        eventURL(url);
    }

    function setExpiration()
    {
        var url = "action:setExpiration";
        var idx = document.forms['settings']['expireAfter'].selectedIndex;
        var value = document.forms['settings']['expireAfter'].options[idx].value;

        url += '?feed=' + document.forms['setAuto']['feed'].value;
        if (value == 'system' || value == 'never')
        {
            url += "&type=" + value + "&time=0";
        }
        else
        {
            url += "&type=feed&time=" + value;
        }

        eventURL(url);
    }

    function setMaxNew()
    {
        var url = "action:setMaxNew";

        url += '?feed=' + document.forms['setAuto']['feed'].value;
        if (document.forms['settings']['maxOutDownloads'].checked)
        {
            var maxNew = document.forms['settings']['maxNew'];
            maxNew.disabled = false;
            if(maxNew.value == '') maxNew.value = '0';
            if(!(parseInt(maxNew.value) >= 0)) {
               eventURL('action:invalidMaxNew?value=' + escape(maxNew.value));
               maxNew.value = '0';
            }
            url += '&maxNew=' + maxNew.value;
        }
        else
        {
            document.forms['settings']['maxNew'].disabled = true;
            url += '&maxNew=-1';
        }

        eventURL(url);
    }

    -->
</script>
