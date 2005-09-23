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

    function settingsFormSubmit() {
         var expire = 'system';
         var i = 0;
         var url = 'action:changeFeedSettings?';
         url += 'feed='+document.forms['settings']['feed'].value;
         if (document.forms['settings'].automatic.checked)
             url += '&automatic=1';
         else
             url += '&automatic=0';
         for (i=0;i<document.forms['settings'].expire.length;i++)
             {
                 if (document.forms['settings'].expire[i].checked)
                     {
                         expire = document.forms['settings'].expire[i].value;
                     }
             }
         url += '&expire='+expire;
         if (document.forms['settings'].getEverything.checked)
             url += '&getEverything=1';
         else
             url += '&getEverything=0';
         url += '&maxnew='+document.forms['settings']['maxnew'].value;
         url += '&fallbehind='+document.forms['settings']['fallbehind'].value;
         url += '&expireDays='+document.forms['settings']['expireDays'].value;
         url += '&expireHours='+document.forms['settings']['expireHours'].value;
         eventURL(url);
    }
    -->
</script>