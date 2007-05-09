function performSearch()
{
    fillSearch()
    engine = document.forms['search']['engines'].value;
    query =  document.forms['search']['query'].value;
    url = 'action:'
    
    if (query == '')
    {
        url = url + 'resetSearch?'
    }
    else
    {
        url = url + 'performSearch?engine=' + engine;
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
    updateUrl =  'action:updateLastSearchQuery?query=' + URLencode(query);
    eventURL(updateUrl)
    return true;
}

function validateSearch(e)
{
    if (getKeyFromEvent(e) == 13)
    {
        return performSearch();
    }

    return true;
}