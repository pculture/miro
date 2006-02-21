function performSearch()
{
    engine = document.forms['search']['engines'].value;
    query =  document.forms['search']['query'].value;
    url = 'action:'
    
    if (query == '')
    {
        url = url + 'resetSearch?'
    }
    else
    {
        url = url + 'performSearch?engine=' + URLencode(engine);
        url = url + '&query=' + URLencode(query);
    }
    
    return eventURL(url);
}

function updateLastSearchEngine()
{
    engine = document.forms['search']['engines'].value;
    updateUrl =  'action:updateLastSearchEngine?engine=' + engine;
    eventURL(updateUrl)
    return true;
}

function fillSearch()
{
    query =  document.forms['search']['query'].value;
    updateUrl =  'action:updateLastSearchQuery?query=' + query;
    eventURL(updateUrl)
    return true;
}

function validateSearch(e)
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
        engine = document.forms['search']['engines'].value;
        query =  document.forms['search']['query'].value;
        performSearch(engine, query)
    }

    return false;
}