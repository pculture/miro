function performSearch(query)
{
    url = 'action:'
    
    if (query == '')
    {
        url = url + 'resetSearch?'
    }
    else
    {
        url = url + 'performSearch?query=' + URLencode(query);
    }
    
    return eventURL(url);
}

function fillSearch(query)
{
    updateUrl =  'action:updateLastSearchQuery?query=' + query;
    eventURL(updateUrl)
    return true;
}

function validateSearch(e, query)
{
   	if (window.event) 
   	{
   		key = e.keyCode;
   	}
   	else if (e.which) 
   	{
   		key = e.which;
   	}

    if (key == 13)
    {
        performSearch(query)
    }

    return true;
}