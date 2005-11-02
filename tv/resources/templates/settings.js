<script type="text/javascript">
    <!-- // Protect from our XML parser, which doesn't know to protect <script>
    function setAutoDownloadableFeed() {
        var url = 'action:setAutoDownloadableFeed';
        url += '?feed=' + document.forms['setAuto']['feed'].value;
        if (document.forms['setAuto'].automatic.checked)
            url += '&automatic=1';
        else
            url += '&automatic=0';
        eventURL(url);
    }
    function setAutoDownloadableFeed2() {
        var url = 'action:setAutoDownloadableFeed';
        url += '?feed=' + document.forms['setAuto2']['feed'].value;
        if (document.forms['setAuto2'].automatic.checked)
            url += '&automatic=1';
        else
            url += '&automatic=0';
        eventURL(url);
    }

    function settingsFormSubmit() {
         var url = 'action:changeFeedSettings?';

         url += 'feed=' + document.forms['settings']['feed'].value;         
         url += '&getEverything=' + document.forms['settings']['autoDownloadGets'].selectedIndex;

         if (document.forms['settings']['maxOutDownloads'].checked)
         {
             url += '&maxnew=' + document.forms['settings']['maxNew'].value;
         }
         else
         {
             url += '&maxnew=unlimited';
         }

         var selectedExpirationIndex = document.forms['settings']['expireAfter'].selectedIndex;
         url += "&expire=" + document.forms['settings']['expireAfter'].options[selectedExpirationIndex].value;
         
         eventURL(url);
    }
    -->
</script>