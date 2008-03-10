<script type="text/javascript">
    function navBarLoaded() 
    {
        var metas = document.getElementsByTagName('meta');
        var i;
        for (i=0; i < metas.length; i++)
        {
            if (metas[i].getAttribute('name') == "guideURL")
            {
                miro_guide_frame.location = metas[i].getAttribute('content');
                break;
            }
        }
    }

    function guideLoaded() 
    {
        if (netscape)
        {
            netscape.security.PrivilegeManager.enablePrivilege('UniversalBrowserRead');
            netscape.security.PrivilegeManager.enablePrivilege('UniversalBrowserWrite');
        }
        
        miro_navigation_frame.document.getElementById('load-indicator').style.display = 'none';
    }

    function guideUnloaded() 
    {
        if (netscape)
        {
            netscape.security.PrivilegeManager.enablePrivilege('UniversalBrowserRead');
            netscape.security.PrivilegeManager.enablePrivilege('UniversalBrowserWrite');
        }
        
        miro_navigation_frame.document.getElementById('load-indicator').style.display = 'block';    
    }
</script>
