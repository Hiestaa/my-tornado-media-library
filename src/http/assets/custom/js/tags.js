$(function () {
    function Tags () {
        console.log ("Initializing Tags Manager");
        var self = this;
        self.rowTemplate = '\
<tr class="tag-row" id="{{tagId}}">\
    <td class="tag-name">{{tagName}}</td>\
    <td class="tag-value" data-tag-name="{{tagName}}">{{tagValue}}</td>\
    <td class="tag-autotag uk-form">{{autoTag}}</td>\
    <td class="tag-usage">{{tagUsage}}</td>\
    <td class="tag-home-uses">{{homeUses}}</td>\
    <td class="tag-relation">{{tagRelation}}</td>\
    <td class="tag-delete"><i class="uk-icon-remove" title="Delete this tag" data-uk-tooltip="{pos: \'top-left\'}"></i></td>\
</tr>'
        self.tags = null;
        self.tagNames = [];
        self.tagValues = {};
        self.onNumericCellClick = function ($cell, min, max) {
            var current = $cell.html();
            var field;
            $cell.html('<input type="number" value="' + current + '" min="' + (min || 0) + '" max="' + (max || 10) + '" style="width: 100%">');
            $cell.find('input').focus();
            // save the name of the field
            if ($cell.hasClass('tag-home-uses'))
                field = 'home';
            $cell.off().keydown(function (e) {
                if (e.keyCode == 13) {  // enter
                    self.edit(
                        $cell.parent().attr('id'),
                        field, $cell.find('input').val());
                }
                if (e.keyCode == 27) { // escape
                    $cell.html(current).click(self.onCellClick)
                }
            });
        }
        self.onAutotagClick = function ($cell) {
            var current = $cell.html();
            $cell.html('<input type="text" value="' + current + '" style="width: 100%">');
            $cell.find('input').focus();
            $cell.off().keydown(function (e) {
                if (e.keyCode == 13) { // enter
                    self.edit(
                        $cell.parent().attr('id'),
                        'autotag', $cell.find('input').val());
                }
                if (e.keyCode == 27) { // escape
                    $cell.html(current).click(self.onCellClick);
                }
            });
        }
        self.onTextCellClick = function ($cell) {
            var field, options;
            // save the name of the field, and the list of options
            // that will be available for the selectize dropdown
            if ($cell.hasClass('tag-name')) {
                field = 'name';
                options = self.tagNames;
            }
            if ($cell.hasClass('tag-value')) {
                field = 'value';
                options = self.tagValues[$cell.attr('data-tag-name')];
            }
            // save current value, in case of cancel
            var current = $cell.html();
            // create html <select> in this cell
            $cell.html('<select>' +
                options.map(function (val) {
                    return '<option value="' + val + '" ' + (val == current ? 'selected': '') + '>' + val + '<options>'
                }).join('') + '</select>')
            // create the selectize dropdown
            var $select = $cell.find('select').selectize({
                create: true, openOnFocus: true,
                onItemAdd: function (value, $item) {
                    if (value == current)
                        return;
                    self.edit(
                        $cell.parent().attr('id'),
                        field, value
                    );
                },
                onDropdownClose: function () {
                    $cell.html(current);
                    $cell.click(self.onCellClick);
                }
            });
            // remove any event on this cell
            $cell.off();
            // open dropdown
            $select[0].selectize.focus();
        }
        self.onCellClick = function () {
            var $cell = $(this)
            if ($cell.hasClass('tag-name') || $cell.hasClass('tag-value')) {
                self.onTextCellClick($cell);
            }
            else if ($cell.hasClass('tag-home-uses'))
                self.edit(
                    $cell.parent().attr('id'),
                    'home',
                    !$cell.find('i').hasClass('uk-icon-check'))
            else if ($cell.hasClass('tag-autotag'))
                self.onAutotagClick($cell)
            else if ($cell.hasClass('tag-relation')) {
                self.edit(
                    $cell.parent().attr('id'),
                    'relation',
                    !$cell.find('i').hasClass('uk-icon-check'))
            }
            else if ($cell.hasClass('tag-delete')) {
                // todo: add a confirmation modal?
                $.ajax({
                    url: '/api/tag/delete',
                    type: 'post',
                    dataType: 'json',
                    data: {'tagId': $cell.parent().attr('id')},
                    error: function (e) {
                        console.error(e);
                        $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                    },
                    success: function () {
                        $cell.parent().remove();
                    }
                });
            }
        };

        self.create = function () {
            $.ajax({
                url: '/api/tag/create',
                type: 'post',
                dataType: 'json',
                data: {
                    name: $('#select-new-name').val(),
                    value: $('#select-new-value').val(),
                    relation: $('#new-relation').hasClass('uk-icon-check'),
                    autotag: $('#input-new-autotag').val(),
                    home: $('#new-home-uses').hasClass('uk-icon-check')
                },
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                },
                success: function (tag) {
                    if (self.tagNames.indexOf(tag.name) === -1) {
                        self.tagNames.push(tag.name);
                        self.tagValues[tag.name] = [];
                    }
                    if (self.tagValues[tag.name].indexOf(tag.value) === -1)
                        self.tagValues[tag.name].push(tag.value);
                    var relation = '<i class="uk-icon-check"></i>';
                    if (!tag.relation)
                        relation = '<i class="uk-icon-close"></i>';
                    var home = '<i class="uk-icon-check"></i>';
                    if (!tag.home)
                        home = '<i class="uk-icon-close"></i>';
                    $('#tags-table #content').prepend(render(self.rowTemplate, {
                        tagId: tag._id,
                        tagName: tag.name,
                        tagValue: tag.value,
                        autoTag: tag.autotag,
                        homeUses: home,
                        tagRelation: relation,
                        tagUsage: 0
                    }));
                    $('#tags-table tr#' + tag._id + ' td').off().click(self.onCellClick);
                }
            })
        };

        self.events = function () {
            $('#new-relation').click(function () {
                $(this).toggleClass('uk-icon-close').toggleClass('uk-icon-check');
            });
            $('#create-form #submit').click(self.create);
        };
        self.events();

        self.edit = function (id, field, value) {
            console.log("Edit", id, field, value);
            $.ajax({
                url: '/api/tag/edit',
                dataType: 'json',
                type: 'post',
                data: {property: field, value: value, tagId: id, usage: true},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                },
                success: function (tag) {
                    if (self.tagNames.indexOf(tag.name) === -1) {
                        self.tagNames.push(tag.name);
                        self.tagValues[tag.name] = [];
                    }
                    if (self.tagValues[tag.name].indexOf(tag.value) === -1)
                        self.tagValues[tag.name].push(tag.value);

                    var relation = '<i class="uk-icon-check"></i>';
                    if (!tag.relation)
                        relation = '<i class="uk-icon-close"></i>';

                    var home = '<i class="uk-icon-check"></i>';
                    if (!tag.home)
                        home = '<i class="uk-icon-close"></i>';
                    console.log(tag.relation, tag.home);

                    var row = render(self.rowTemplate, {
                        tagId: tag._id,
                        tagName: tag.name,
                        tagValue: tag.value,
                        autoTag: tag.autotag,
                        tagRelation: relation,
                        homeUses: home,
                        tagUsage: tag.usage,
                    });
                    $('#tags-table tr#' + tag._id).replaceWith(row);
                    $('#tags-table tr#' + tag._id + ' td').off().click(self.onCellClick);
                }
            })
        }

        self.onRcvTags = function (results) {
            // save tags
            self.tags = results;
            // create rows in the tag table
            for (var i = 0; i < results.length; i++) {
                var tag = results[i];
                var relation = '<i class="uk-icon-check"></i>';
                if (!tag.relation)
                    relation = '<i class="uk-icon-close"></i>';
                var home = '<i class="uk-icon-check"></i>';
                if (!tag.home)
                    home = '<i class="uk-icon-close"></i>';
                $('#tags-table #content').append(render(self.rowTemplate, {
                    tagId: tag._id,
                    tagName: tag.name,
                    tagValue: tag.value,
                    autoTag: tag.autotag,
                    homeUses: home,
                    tagRelation: relation,
                    tagUsage: tag.usage
                }));
                if (self.tagNames.indexOf(tag.name) == -1) {
                    self.tagNames.push(tag.name);
                    self.tagValues[tag.name] = [];
                }
                if (self.tagValues[tag.name].indexOf(tag.value) == -1)
                    self.tagValues[tag.name].push(tag.value);
            };
            // register click callbacl
            $('.tag-row td').click(self.onCellClick);

            // create new label row
            // populate select options with existing values for the autocompletion
            if (self.tagNames.length > 0) {
                var i = 0;
                $('#select-new-name').html(
                    self.tagNames.map(function (val) {
                        return '<option value="' + val + '" ' + (i++ == 0 ? 'selected': '') + '>' + val + '<options>'
                    }).join(''));
                i = 0;
                $("#select-new-value").html(
                    self.tagValues[self.tagNames[0]].map(function (val) {
                        return '<option value="' + val + '" ' + (i++ == 0 ? 'selected': '') + '>' + val + '<options>'
                    }).join(''));
            }
            // selectize the list
            $('#select-new-name').attr('disabled', false).selectize({
                create: true,
                onItemAdd: function (value, $item) {
                    var i = 0
                    var inst = $('#select-new-value')[0].selectize
                    if (inst)
                        inst.destroy();
                    if (!self.tagValues[value])
                        self.tagValues[value] = [];
                    $('#select-new-value').attr('disabled', false).html(
                        self.tagValues[value].map(function (val) {
                            return '<option value="' + val + '" ' + (i++ == 0 ? 'selected': '') + '>' + val + '<options>'
                        }).join(''));
                    $('#select-new-value').selectize({create: true});
                },
                onDropdownClose: function () {
                    if (!$('#select-new-name').val()) {
                        $('#select-new-value')[0].selectize.clearOptions();
                    }
                }
            });
            $('#select-new-value').attr('disabled', false).selectize({create: true});
            $('#submit').attr('disabled', false);
            spinLoading('stop');
        }

        self.load = function () {
            spinLoading();
            $.ajax({
                url: '/api/tag/get',
                dataType: 'json',
                data: {usage: true},
                type: 'post',
                success: self.onRcvTags,
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                }
            })
        };
        self.load();
    }
    new Tags();
});