function performSearch(query)
{
    url = 'action:'
    
    if (query == '')
    {
        url = url + 'resetSearch'
    }
    else
    {
        url = url + 'performSearch?query=' + URLencode(query);
    }
    
    return eventURL(url);
}
