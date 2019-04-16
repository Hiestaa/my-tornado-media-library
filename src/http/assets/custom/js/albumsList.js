$(function () {
    function AlbumsList() {
        var self = this;
        self.albumTemplate = '\
<div class="uk-width-1-3 album-item" data-album-id="{{_id}}">\
    <div class="uk-panel uk-panel-box">\
        <div class="uk-panel-teaser">\
            <img src="{{cover}}" alt="{{title}}\'s cover" width="100%">\
        </div>\
        <p class="album-title"><a href="/slideshow/albumId={{_id}}">{{title}} ({{starNb}} <i class="uk-icon-star" /> / {{picNb}} <i class="uk-icon-image" />)</a></p>\
    </div>\
</div>\
<div class="uk-width-1-3" id="loading-info">\
    <i class="fa fa-spinner fa-spin"></i>\
</div>';

        self.onRcvAlbums = function (albums) {
            if (albums.length == 0)
                return spinLoading('stop');
            var i = 0;
            var onPicLoaded = function () {
                var album = albums[i];
                $('#albums-list #loading-info').remove();
                $('#albums-list').append(render(self.albumTemplate, {
                    cover: album['picturesDetails'][album['cover']]['url'],
                    title: album['name'],
                    _id: album['_id'],
                    picNb: album['picturesDetails'].length,
                    starNb: album['picturesDetails'].filter(p => !!p.starred).length
                }));
                i += 1;
                if (i < albums.length)
                    preloadPictures([album['picturesDetails'][album['cover']]['url']], onPicLoaded);
                else
                    $('#albums-list #loading-info').remove();
                $('#albums-list .album-item').off().click(function (e) {
                    if ($(e.target).parent().prop('tagName') != 'A' && $(e.target).prop('tagName') != 'A')
                        window.open('/slideshow/albumId=' + $(this).attr('data-album-id'), '_self', false);
                });
            };
            preloadPictures([albums[i]['picturesDetails'][albums[i]['cover']]['url']], function () {
                spinLoading('stop');
                onPicLoaded();
            });
        }

        self.load = function () {
            spinLoading();
            $.ajax({
                url: '/api/album/display',
                type: 'get',
                dataType: 'json',
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while loading albums, see logs for details.", {status:'danger'});
                },
                success: self.onRcvAlbums
            });
        }
        self.load();
    }
    new AlbumsList()
})