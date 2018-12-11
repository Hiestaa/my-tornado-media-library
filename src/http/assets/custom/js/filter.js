$(function() {
    function Filter($filterList, $addFilterBtn, callbacks) {
        var self = this;

        self.$filterList = $filterList;
        self.$addFilterBtn = $addFilterBtn;

        callbacks = callbacks || {};
        self._onFilterAdded = callbacks.onFilterAdded || function (type, uid, fid, value, options) {};
        self._onFilterRemoved = callbacks.onFilterRemoved || function (type, uid) {};
        self._onFilterNegated = callbacks.onFilterNegated || function (type, uid, criteria) {};
        self._onCriteriaUpdated = callbacks.onCriteriaUpdated || function (criteria, options) {};

        self.criteria = {
            video: {},
            tag: {}
        }
        self.propertyTemplate = '\
<div class="uk-button-group property-filter" data-filter-id="{{filterId}}" data-filter-type={{type}}>\
    <button class="uk-button uk-button-success negate-filter"><i class="uk-icon-minus-circle hidden" /><i class="uk-icon-check-circle" /></button>\
    <button class="uk-button">{{text}}</button>\
    <button class="uk-button uk-button-danger remove-filter"><i class="uk-icon-close"></i></button>\
</div>';
        // for each video property, associate the id to the real displayed name
        self.vpId2display = {
            name: 'Video Title',
            maxDuration: 'Max. Length',
            minDuration: 'Min. Length',
            resolution: 'Min. Resolution',
            minFavorite: 'Min. Favorite',
            maxFavorite: 'Max. Favorite',
            toWatch: 'To Watch',
            minSeen: 'Min. Times Watched',
            maxSeen: 'Max. Times Watched'
        }
        // for each video property, associate the id to the corresponding video document field
        self.vpId2name = {
            name: 'name',
            maxDuration: 'duration',
            minDuration: 'duration',
            resolution: 'resolution',
            minFavorite: 'favorite',
            maxFavorite: 'favorite',
            toWatch: 'toWatch',
            minSeen: 'seen',
            maxSeen: 'seen'
        }
        // for each property, associate the id to the formatter that transform
        // the value into the displayed name
        self.formatters = {}

        self.uid = 0;

        self.getCriteria = function () {
            return self.criteria;
        }

        self.renderFilter = function (name, type, text, negated) {
            var rendered = render(self.propertyTemplate, {
                filterId: self.uid,
                type: type,
                text: text,
            });
            $rendered = $(rendered);
            if (negated) {
                $rendered.find('.negate-filter > i').toggleClass('hidden');
                $rendered.find('.negate-filter').toggleClass('uk-button-warning').toggleClass('uk-button-success');
            }

            self.$filterList.append($rendered);
            self.$filterList.find('.remove-filter').off().click(function () {
                var filterUid = parseInt($(this).parent().attr('data-filter-id'));
                var type = $(this).parent().attr('data-filter-type');
                $(this).parent().remove();
                // special case for the resolution: if the width has been added
                // the next filter in the list should be the height and should be deleted as well
                if (type == 'video' && Object.keys(self.criteria[type][filterUid]).indexOf('width') !== -1)
                    delete self.criteria[type][filterUid + 1];
                delete self.criteria[type][filterUid];
                self._onFilterRemoved(type, filterUid);
            });
            self.$filterList.find('.negate-filter').off().click(function (e) {
                var filterUid = parseInt($(this).parent().attr('data-filter-id'));
                var type = $(this).parent().attr('data-filter-type');

                // special case for the resolution: if the width has been added
                // the next filter in the list should be the height and should be updated as well
                if (type == 'video' && Object.keys(self.criteria[type][filterUid]).indexOf('width') !== -1)
                    self.criteria[type][filterUid + 1]['$negated'] = !self.criteria[type][filterUid + 1]['$negated'];
                self.criteria[type][filterUid]['$negated'] = !self.criteria[type][filterUid]['$negated'];

                $(this).find('i').toggleClass('hidden');
                $(this).toggleClass('uk-button-warning').toggleClass('uk-button-success');
                self._onFilterNegated(type, filterUid, self.criteria);
            });
        };

        self.createVidFilterCriteria = function (fid, name, value, formatter, negated, uid) {
            var filter = {};
            filter[name] = value;
            filter.$negated = negated;
            if (fid == 'maxDuration' || fid == 'maxFavorite' || fid == 'maxSeen')
                filter.$comparator = '<';
            else if (fid == 'minDuration' || fid == 'minFavorite' || fid == 'minSeen')
                filter.$comparator = '>';
            else
                filter.$comparator = '=';
            if (fid == 'resolution') {
                // special case for the resolution, there will be two filter, one for the width, one for the height
                filter = {'width': parseInt(formatter(value).split('x')[0]), $comparator: '>'}
                self.criteria.video[uid++] = filter;
                filter = {'height': parseInt(formatter(value).split('x')[1]), $comparator: '>'}
                self.criteria.video[uid++] = filter;
            }
            else {
                self.criteria.video[uid++] = filter;
            }
        };

        self.onAddProperty = function (type, fid, value, uid, options) {
            console.log ("Adding " + type + "property fid=" + fid + ", value=" + value);
            var name, text, formatter;
            options = options || {}

            // uid is optional but can force the value of the UID
            var _uid = uid !== undefined ? parseInt(uid, 10) : self.uid + 1
            if (_uid > self.uid)
                self.uid = _uid;

            // notify server?
            self._onFilterAdded(type, self.uid, fid, value, options)
            formatter = self.formatters[fid] || function (v) { return v };
            // populate fields for the rendering
            if (type == 'video') {
                name = self.vpId2name[fid];
                // note: if the formatter returns nothing, do not display the ': value'
                text = self.vpId2display[fid] + (formatter(value) ? (': ' + formatter(value)) : '')
            }
            else {
                name = self.tagNames[fid];
                text = name + ': ' + formatter(value);
            }
            // render the filter
            self.renderFilter(name, type, text, options.negated);
            // create the filter object that will actually be used when issuing the query
            if (type == 'video')
                self.createVidFilterCriteria(fid, name, value, formatter, !!options.negated, _uid);
            else if (type == 'tag') {
                self.criteria.tag[_uid] = {$value: value, $negated: !!options.negated};
            }
            else {
                console.error("Unrecognized type: " + type);
                $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
            }
            self._onCriteriaUpdated(self.criteria, options);
        };

        self.afterTagsReceivedCb = null;
        self.onRcvTags = function (tags) {
            self.tagNames = [];
            self.tagValues = {};
            for (var i = 0; i < tags.length; i++) {
                var tag = tags[i]
                if (self.tagNames.indexOf(tag.name) === -1) {
                    self.tagNames.push(tag.name)
                    self.tagValues[tag.name] = {};
                }
                if (!(tag._id in self.tagValues))
                    self.tagValues[tag.name][tag._id] = tag.value;
            };
            for (var i = 0; i < self.tagNames.length; i++) {
                var name = self.tagNames[i];
                var options = self.tagValues[name];
                self.formatters[i] = self.propertiesPanel.addTagProperty(
                    'tag', i, name, options);
            };

            if (self.afterTagsReceivedCb) {
                self.afterTagsReceivedCb();
                self.afterTagsReceivedCb = null;
            }

            spinLoading('stop');
        }
        self.loadTags = function () {
            spinLoading();
            $.ajax({
                url: '/api/tag/get',
                dataType: 'json',
                type: 'post',
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                },
                success: self.onRcvTags
            });
        }


        self.loadExistingFilters = function (filters, done) {
            if (!filters) { return; }
            // delay if tags aren't loaded yet
            if (!self.tagNames) {
                self.afterTagsReceivedCb = () => self.loadExistingFilters(filters, done);
                return;
            }

            for (type in filters) {
                if (!filters[type]) { continue; }
                for (uid in filters[type]) {
                    if (!filters[type][uid]) { continue; }
                    if (isPositiveInteger(filters[type][uid].value))
                        value = parseInt(filters[type][uid].value);
                    else
                        value = filters[type][uid].value;
                    self.onAddProperty(
                        type, filters[type][uid].name,
                        value, uid,
                        {do_not_save: true, do_not_reload: true, negated: filters[type][uid].negated});
                }
            }

            if (done) {
                done();
            }
        }

        self.initialize = function () {
            // create properties manager, and add all properties available for filtering the video
            self.propertiesPanel = new Properties([self.$addFilterBtn], self.onAddProperty);
            self.formatters.name = self.propertiesPanel.addTextInput(
                'video', 'name', self.vpId2display['name']);
            self.formatters.minDuration = self.propertiesPanel.addTimeSlider(
                'video', 'minDuration', self.vpId2display['minDuration'], 60, 1500, 600);
            self.formatters.maxDuration = self.propertiesPanel.addTimeSlider(
                'video', 'maxDuration', self.vpId2display['maxDuration'], 60, 1500, 600);
            self.formatters.resolution = self.propertiesPanel.addResolutionSlider(
                'video', 'resolution', self.vpId2display['resolution']);
            self.formatters.minFavorite = self.propertiesPanel.addSlider(
                'video', 'minFavorite', self.vpId2display['minFavorite'], 1, 10, 1);
            self.formatters.maxFavorite = self.propertiesPanel.addSlider(
                'video', 'maxFavorite', self.vpId2display['maxFavorite'], 1, 10, 1);
            // should be a simple boolean filter
            self.formatters.toWatch = self.propertiesPanel.addBoolean(
                'video', 'toWatch', self.vpId2display['toWatch']);
            self.formatters.minSeen = self.propertiesPanel.addSlider(
                'video', 'minSeen', self.vpId2display['minSeen'], 1, 20, 1);
            self.formatters.maxSeen = self.propertiesPanel.addSlider(
                'video', 'maxSeen', self.vpId2display['maxSeen'], 1, 20, 1);
            self.loadTags();
        }

        self.clear = function (type, uid) {
            self.criteria = {
                video: {},
                tag: {}
            }

            self.$filterList.find('.property-filter').remove();
        }

        self.initialize();
    }
    window.Filter = Filter;
});