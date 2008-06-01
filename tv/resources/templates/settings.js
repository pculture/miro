<script type="text/javascript">
    <!-- // Protect from our XML parser, which doesn't know to protect <script>

    var settingsMode = 'closed';

    function showSettings()
    {
        if(settingsMode == 'open') return hideSettings();
        var feedSettings = document.getElementById("feed-settings");
        feedSettings.style.display = "block";
        settingsMode = 'open';
        return false;
    }

    function hideSettings()
    {
        var feedSettings = document.getElementById("feed-settings");
        feedSettings.style.display = "none";
        settingsMode = 'closed';
        return false;
    }

    function setExpiration()
    {
        var url = "action:setExpiration";
        var idx = document.forms['settings']['expireAfter'].selectedIndex;
        var value = document.forms['settings']['expireAfter'].options[idx].value;

        url += '?feed=' + document.forms['settings']['feed'].value;
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

        url += '?feed=' + document.forms['settings']['feed'].value;
        if (document.forms['settings']['maxOutDownloads'].checked)
        {
            var maxNew = document.forms['settings']['maxNew'];
            maxNew.disabled = false;
            if(maxNew.value == '') maxNew.value = '0';
            if(!(parseInt(maxNew.value) >= 0)) {
               eventURL('action:requiresPositiveInteger?value=' + escape(maxNew.value));
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

function setMaxOldItems() {
    var url = 'action:setMaxOldItems?feed=';
    url += document.forms['settings']['feed'].value;
    url += '&maxOldItems=';
    var idx = document.forms['settings']['maxOldItems'].selectedIndex;
    var value = document.forms['settings']['maxOldItems'].options[idx].value;
    url += value;
    eventURL(url);	
}

    -->
</script>
