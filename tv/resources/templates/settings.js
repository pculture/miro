<script type="text/javascript">
<!-- // Protect from our XML parser, which doesn't know to protect <script>
function settingsFormSubmit() {
     url = 'action:changeFeedSettings?';
     url += 'feed='+document.forms['settings']['feed'].value;
     url += '&automatic='+document.forms['settings']['automatic'].value;
     url += '&getEverything='+document.forms['settings']['getEverything'].value;
     url += '&maxnew='+document.forms['settings']['maxnew'].value;
     url += '&fallbehind='+document.forms['settings']['fallbehind'].value;
     url += '&expire='+document.forms['settings']['expire'].value;
     url += '&expireDays='+document.forms['settings']['expireDays'].value;
     url += '&expireHours='+document.forms['settings']['expireHours'].value;
     eventURL(url);
}
-->
</script>