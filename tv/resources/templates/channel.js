function showAllVideos() {
    var showMoreLabel = document.getElementById("show-more-videos-label");
    if(showMoreLabel.style.display != 'none') {
        toggleLayer('main-newlyavailable-seen');
        toggleLayer('show-more-videos-label');
        toggleLayer('main-channelbar-available');
    }
}
