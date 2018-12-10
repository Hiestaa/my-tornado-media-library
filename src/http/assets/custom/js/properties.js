$(function () {
    function SelectizeProperty($element, type, name, onSelect, options) {
        var self = this;
        self.template = '\
<li>\
    <div class="uk-button-group properties-item">\
        <button class="uk-button uk-button-success" id="sender"><i class="uk-icon-check"></i></button>\
        <select id="selectize-{{name}}"><select>\
    </div>\
</li>';
        self.optionTemplate = '\
<option value="{{val}}">{{display}}</option>';
        self.values = options.values;
        self.formatter = options.formatter || function (v) { return v };
        $element.append(render(self.template, {
            name: name
        }));
        for (var i = 0; i < self.values.length; i++) {
            $element.find('#selectize-' + name).append(render(self.optionTemplate, {
                val: self.values[i],
                display: self.formatter(self.values[i])
            }));
        };
        $element.find('#selectize-' + name).selectize({
            onDropdownOpen: function ($dropdown) {
                var height = 265;
                if ($dropdown.children().children().length < 8)
                    height = 65 + 25 * $dropdown.children().children().length
                $element.parent().attr('style', 'height: ' + height + 'px !important');
            },
            onDropdownClose: function () {
                $element.parent().attr('style', 'height: 0');
            },
            create: true
        });
        $element.find('#sender').click(function () {
            onSelect(type, name, $element.find('#selectize-' + name).val());
        })
    }
    function ListProperty($element, type, name, onSelect, options) {
        var self = this;
        self.listItemTemplate = '\
<li class="{{name}}-option properties-item" data-value="{{value}}">{{display}}</li>\
';
        self.values = options.values;
        self.formatter = options.formatter || function (v) { return v; };
        for (var i = 0; i < self.values.length; i++) {
            $element.append(render(self.listItemTemplate, {
                name: name,
                value: self.values[i],
                display: self.formatter(self.values[i])
            }));
        };
        $('.' + name + '-option').click(function () {
            onSelect(type, name, $(this).attr('data-value'))
        });
    };
    function CustomSliderProperty($element, type, name, onSelect, options) {
        var self = this;
        self.template = '\
<li>\
    <div class="uk-button-group properties-item">\
        <button class="uk-button uk-button-success" id="sender"><i class="uk-icon-check"></i></button>\
        <div class="slider" title="{{titleVal}}" data-uk-tooltip="{cls: \'tooltip-{{name}}\', pos:\'left\'}">\
            <span class="slider-handle">\
        </div>\
    </div>\
</li>';
        self.name = name;
        self.isActive = false;
        self.initialX = 0;
        self.barL = 0;
        self.minVal = options.min || 0;
        self.maxVal = options.max || 100;
        self.initVal = options.val || 0;
        self.formatter = options.formatter || function (v) { return v; };
        self.currentX = 0;
        $element.append(render(self.template, {
            name: name,
            titleVal: self.formatter(self.initVal)
        }));
        self.handler = $element.find('.slider-handle');
        self._valToX = function (val) {
            // transform to percentage
            var pc = val / (self.maxVal - self.minVal);
            pc = Math.max(0, Math.min(pc, 1));
            // transform to x
            return pc * self.barL;
        }
        self._XToVal = function (x) {
            // get progress
            var progress = Math.max(0, x);
            // transform to percentage
            var pc = progress / self.barL;
            // transform in min/max space
            return parseInt(self.minVal + pc * (options,self.maxVal - self.minVal));
        };
        self._clamp = function (val) {
            return Math.max(-1, Math.min(self.barL, val));
        };
        self._update = function (posX) {
            self.currentX = self._clamp(posX - 6 - self.initialX + 1);
            self.handler.css('transform', 'translateX(' + self.currentX + 'px)');
            $('.tooltip-' + self.name).html(self.formatter(self._XToVal(self.currentX)));
        }
        self._events = function () {
            $element.find('#sender').click(function () {
                onSelect(type, name, self._XToVal(self.currentX));
            });
            self.handler.on('mousedown', function (e) {
                self.isActive = true;
                // in the case where the initial X has not be set set it now
                // (this is most likely to be due to a hidden element that has no position in the flow)
                if (!self.initialX) {
                }
            });
            $element.on('mousemove', function (e) {
                if (self.isActive) {
                    self._update(e.pageX);
                    if ($('.tooltip-' + self.name).css('display') == 'none')
                        $('.tooltip-' + self.name).css('display', 'block')
                }
            }).on('mouseup', function (e) {
                self.isActive = false;
            });
            self.handler.parent().on('mousedown', function (e) {
                self.isActive = true;
                self._update(e.pageX);
            });
        };
        self.onShow = function () {
            if (!self.initialX)
                self.initialX = self.handler.parent().offset().left;
            if (!self.barL)
                self.barL = self.handler.parent().width() - 6;
            if (!self.currentX) {
                self.currentX = self._valToX(self.initVal || 0) - 6;
                self.handler.css('transform', 'translateX(' + self.currentX + 'px)');
            }
        }

        self._events();
        return self;
    };
    function SliderProperty($element, type, name, onSelect, min, max, val) {
        var self = this;
        self.template = '\
<li>\
<div class="uk-button-group properties-item">\
    <div class="uk-form">\
        <button class="uk-button uk-button-success" id="sender"><i class="uk-icon-check"></i></button>\
        <input type="range" id="{{name}}-value" class="input-slider" min="{{min}}" max="{{max}}" value="{{val}}" title="Selected: 30min" data-uk-tooltip="{pos:\'bottom-right\'}"/>\
    </div>\
</div>\
</li>';
        $element.append(render(self.template, {
            name: name,
            min: min,
            max: max,
            val: val
        }));
        $element.find('#sender').click(function () {
            onSelect(type, name, $element.find('#' + name + '-value').val())
        });
        return self;
    };
    function TextProperty($element, type, name, onSelect) {
        var self = this;
        self.template = '\
<li>\
    <div class="uk-button-group properties-item text">\
        <div class="uk-form">\
            <button class="uk-button uk-button-success" id="sender"><i class="uk-icon-check"></i></button>\
            <input type="text" id="{{name}}-value">\
        </div>\
    </div>\
</li>';
        $element.append(render(self.template, {
            name: name
        }));
        $element.find('#sender').click(function () {
            onSelect(type, name, $element.find('#' + name + '-value').val())
        });
        return self;
    }
    function Properties($openers, onSelect, options) {
        var self = this;
        /*
        Create and manage the off-canva property selector.
        $openers is a list of jQuery elements that should open the
        off-canvas selector,
        onSelect is the function that is called wheionn something is selected.
        It should have the following prototype:
        function (type, name, value) where:
        * type is either 'video' or 'tag' depending on the filter type
        */
        self.offcanvaTemplate = '\
<div id="properties-panel" class="uk-offcanvas properties-select">\
    <div class="uk-offcanvas-bar uk-offcanvas-bar-show">\
        <ul class="uk-nav uk-nav-offcanvas uk-nav-parent-icon" data-uk-nav>\
            <li class="uk-nav-header" id="attribute-filters">Attribute Filters</li>\
            <li class="uk-nav-header" id="tag-filters">Tags Filters</li>\
        </ul>\
    </div>\
</div>';
        self.propertyContainerTemplate = '\
<li class="uk-parent">\
    <a>{{displayName}}</a>\
    <div ><ul class="uk-nav-sub" id="property-container-{{name}}"></ul></div>\
</li>';
        options = options || {};
        self.tagsOnly = options.tagsOnly !== undefined ? options.tagsOnly : false;
        self.flipped = options.flipped !== undefined ? options.flipped : true;
        self.closeOnSelect = options.closeOnSelect !== undefined ? options.closeOnSelect : true;
        /*
        list of Property object. Each property is an object that
        has at least the function:
        * `constructor($element, type, name, onSelect)`:
            initialize the property.
            `$element` is the jquery element to wich the html of this property
            will be appended.
            `onSelect` should be called when
            the user select this property or anything related to
            this property. `name` and `type` should be given to the `onSelect`
            function when called, along with the selected value
        * onShow(): [optional] do anything that can only be done when the properties bar is opened
        */
        self.properties = [];
        self.onSelect = function (type, name, value) {
            if (self.closeOnSelect)
                $.UIkit.offcanvas.hide();
            onSelect(type, name, value);
        };
        self.initialize = function () {
            $('body').append(self.offcanvaTemplate);
            self.$offCanva = $('#properties-panel');
            for (var i = $openers.length - 1; i >= 0; i--) {
                $openers[i].click(function () {
                    $.UIkit.offcanvas.show('#' + self.$offCanva.attr('id'));
                    for (var i = 0; i < self.properties.length; i++) {
                        if (self.properties[i].onShow)
                            self.properties[i].onShow()
                    };
                });
            };
            if (self.tagsOnly)
                self.$offCanva.find('li#attribute-filters').remove();
            if (self.flipped)
                self.$offCanva.find('.uk-offcanvas-bar').addClass('uk-offcanvas-bar-flip');
        };
        self.initialize();
        self.preparePropertyContainer = function (type, name, displayName) {
            if (type == 'video') {
                self.$offCanva.find('#tag-filters').before(
                    render(self.propertyContainerTemplate, {
                        name: name,
                        displayName: displayName
                    })
                );
                $('.uk-parent > a').off().click(function () {
                    $(this).parent().toggleClass('uk-open');
                });
                return '#property-container-' + name;
            }
            if (type == 'tag') {
                self.$offCanva.find('#tag-filters').after(
                    render(self.propertyContainerTemplate, {
                        name: name,
                        displayName: displayName
                    })
                );
                $('.uk-parent > a').off().click(function () {
                    $(this).parent().toggleClass('uk-open');
                });
                return '#property-container-' + name;
            }
        };
        /*
        Add a new text input to the properties panel.
        * type is the type of the property ('tag' or 'video')
        * name is the name of the property, will be sent back if something
          related to this property is sent, along with the corresponding value
        * displayName is the name that should be displayed
        It returns the formatter used to convert a value into a name, or nothing if no special
        format should be used.
        */
        self.addBoolean = function (type, name, displayName) {
            self.$offCanva.find('#tag-filters').before(
                render('<li id="{{name}}-sender"><a>{{displayName}}</a></li>',
                    {displayName: displayName, name: name})
            );
            $('#' + name + '-sender').click(function () {
                self.onSelect(type, name, true);
            })
            // formatter returns nothing.
            return function (v) { return '' }
        };
        self.addTextInput = function (type, name, displayName) {
            var elementSelector = self.preparePropertyContainer(type, name, displayName);
            self.properties.push(
                new TextProperty($(elementSelector), type, name, self.onSelect));
        };
        self.addSlider = function (type, name, displayName, min, max, val) {
            var elementSelector = self.preparePropertyContainer(type, name, displayName);
            self.properties.push(
                new CustomSliderProperty($(elementSelector), type, name, self.onSelect, {
                    min: min, max: max, val: val
            }));
        }
        self.addTimeSlider = function (type, name, displayName, min, max, val) {
            var elementSelector = self.preparePropertyContainer(type, name, displayName);
            var formatter = function (v) {
                return (parseInt(v / 60)) + ' min, ' + v % 60 +' s';
            }
            self.properties.push(
                new CustomSliderProperty($(elementSelector), type, name, self.onSelect, {
                    min: min, max: max, val: val, formatter: formatter
                }));
            return formatter;
        };
        self.addResolutionSlider = function (type, name, displayName) {
            // the formatter function returned is guarantee to return a value of
            // the format: <width>x<height>
            var elementSelector = self.preparePropertyContainer(type, name, displayName);
            var formatter = function (v) {
                if (v == 1) return '640x480';
                if (v == 2) return '800x600';
                if (v == 3) return '1280x720';
                if (v >= 4) return '1920x1080';
            }
            self.properties.push(
                new CustomSliderProperty($(elementSelector), type, name, self.onSelect, {
                    min: 1, max: 5, val: 1, formatter: formatter
                }))
            return formatter;
        }
        self.__selectTagType = function (options) {
            // tag may be an integer (in which case a slider will be used)
            // a short list of < 5 items (will then be displayed as is)
            // or a long list, a selectize drop-down will then be used.
            var keys = Object.keys(options);
            var min = options[keys[0]], max = options[keys[0]];
            if (isPositiveInteger(min) && isPositiveInteger(max)) {
                min = parseInt(min);
                max = parseInt(max);
            }
            else
                return {type: 'list', len: keys.length}
            for (var i = 0; i < keys.length; i++) {
                var val = options[keys[i]];
                if (!isPositiveInteger(val))
                    break;
                val = parseInt(val);
                if (val < min)
                    min = val;
                if (val > max)
                    max = val;
                if (i == keys.length - 1)
                    return {type: 'int', min: min, max: max}
            };
            return {type: 'list', len: keys.length}
        }
        self.addTagProperty = function (type, name, displayName, options) {
            // options should be a object {<value>: <displayName>}
            var tagType = self.__selectTagType(options)
            var elementSelector = self.preparePropertyContainer(type, name, displayName);
            if (tagType.type == 'list') {
                var formatter = function (value) {
                    return options[value];
                }
                if (tagType.len < 5) {
                    self.properties.push(
                        new ListProperty($(elementSelector), type, name, self.onSelect, {
                            formatter: formatter,
                            values: Object.keys(options)
                        }));
                    return formatter;
                }
                else {
                    self.properties.push(
                        new SelectizeProperty($(elementSelector), type, name, self.onSelect, {
                            formatter: formatter,
                            values: Object.keys(options)
                        }));
                    return formatter;
                }
            }
            if (tagType.type == 'int') {
                var formatter = function (value) {
                    if (options[value] == 0)
                        return '0';
                    var symbol = '<i class="uk-icon-star"></i>';
                    var res = '';
                    for (var i = 0; i < options[value]; i++) {
                        res += symbol;
                    };
                    return res;
                }
                if (tagType.max > 10)
                    formatter = function (value) { return value };
                self.properties.push(
                    new ListProperty($(elementSelector), type, name, self.onSelect, {
                        formatter: formatter,
                        values: Object.keys(options)
                    }));
                return formatter;
            }
        }
        return self;
    }
    window.Properties = Properties;
});