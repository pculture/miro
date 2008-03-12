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
        try
        {
            netscape.security.PrivilegeManager.enablePrivilege('UniversalBrowserRead');
            netscape.security.PrivilegeManager.enablePrivilege('UniversalBrowserWrite');
        }
        catch (e) {}
        
        var loadIndicator = miro_navigation_frame.document.getElementById('load-indicator');
        if (loadIndicator !== null)
        {
            loadIndicator.style.display = 'none';
        }
    }

    function guideUnloaded() 
    {
        try
        {
            netscape.security.PrivilegeManager.enablePrivilege('UniversalBrowserRead');
            netscape.security.PrivilegeManager.enablePrivilege('UniversalBrowserWrite');
        }
        catch (e) {}
        
        miro_navigation_frame.document.getElementById('load-indicator').style.display = 'block';
    }
</script>

