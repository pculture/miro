function submitThis(select) {
    var str = select.value;
    
    if (str != '') {
        var path = 'http://www.radioblogclub.com/search/0/';
        newLocation = path+str; 

        window.open(newLocation);
    }
    
    return false;
}