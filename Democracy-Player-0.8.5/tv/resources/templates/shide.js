function toggleLayer(layer)
{
	var style = document.getElementById(layer).style;
	style.display = (style.display == "none") ? "block":"none";
}

function toggleLayerWithTriangle(layerID, triangleID) 
{
    var layerElt = document.getElementById(layerID);
    var triangleElt = document.getElementById(triangleID);
    if(layerElt.style.display == 'none') {
        layerElt.style.display = 'block';
        triangleElt.className = 'triangledown';
    } else {
        layerElt.style.display = 'none';
        triangleElt.className = 'triangle';
    }
}
