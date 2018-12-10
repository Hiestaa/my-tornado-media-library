$(function () {
    var isDisplayed = {};
    function notifyOnce(msg, options) {
        var status = options.status || 'info';

        if (isDisplayed[status]) { return; }

        isDisplayed[status] = true;
        $.UIkit.notify(msg, Object.assign({
            onClose: () => { isDisplayed[status] = false; }
        }, options));
    }

    function DbUpdateStatus() {
        var self = this;

        self.updateStatus = function (progress) {
            if (progress['errorred']) {
                notifyOnce('An error occurred during the update process. See logs for details.', {status: 'danger', timeout: 10000000});
                $('#current-status #title').text('Update error');
            }
            else if (progress['interrupted']) {
                $('#current-status #title').text('Update interupted');
                notifyOnce('The update proces was successfully interrupted.', {status: 'warning', timeout: 10000000});
            }
            else if (progress['finished']) {
                $('#current-status #title').text('Update complete');
                notifyOnce('The update process completed successfully.', {status: 'success', timeout: 10000000});
            }
            if (progress['finished'] || progress['errorred'] || progress['interrupted']) {
                $('#current-status #duration').text(progress['duration']);
                $('#current-status #nb-dones').text(progress['dones']);
                $('#current-status #description-running').addClass('hidden');
                $('#current-status #update').removeClass('hidden');
                $('#current-status #interrupt').addClass('hidden');

            }
            else {
                $('#current-file').html(progress['file']);
                $('#current-step').html(progress['step']);
                $('#duration').html(progress['duration']);
                $('#nb-dones').html(progress['dones']);
            }
        };

        self.updateCurrentFileList = function (fileList) {
            // TODO: maybe don't need to update the whole file list?
            var body = '';
            for (var i = 0; i < fileList.length; i++) {
                if ($('#table-current tbody #' + fileList[i].id).length) { continue; }
                var line = '<tr id="' + fileList[i].id + '" ';
                if (fileList[i].snapshot) {
                    line += 'class="uk-table-middle" title="<img style=\'max-width: 400px; max-height: 400px\' src=\'' + fileList[i].snapshot + '\'>" data-uk-tooltip="{pos:\'bottom-left\'}">';
                }
                else {
                    line += 'class="uk-table-middle" title="' + fileList[i].fileName + '" data-uk-tooltip="{pos:\'bottom-left\'}">';
                }
                if (fileList[i].link){
                    line += '<td><a href="' + fileList[i].link + '">' + fileList[i].fileName + '</a></td>';
                }
                else{
                    line += '<td>' + fileList[i]['fileName'] + '</td>';
                }
                line += '<td>' + (fileList[i]['error'] || '') + '</td>';
                line += '<td>' + (fileList[i]['success'] ? '<i class="uk-icon-check"></i>' : '<i class="uk-icon-close"></i>')+ '</td>';
                line += '</tr>';
                body += line;
            };
            $('#table-current tbody').append(body);
        };


        self.onReceiveData = function (progress) {
            // TODO: maybe don't need to update the whole file list?
            self.updateStatus(progress['status']);
            if (progress['status']['fileList'] && progress['status']['fileList'].length > 0)
                self.updateCurrentFileList(progress['status']['fileList']);
        };

        self.onopen = function () {

        };

        self.onclose = function () {
            $.UIkit.notify("Connection interrupted. Please refresh the page to reconnect.", {status:'danger'});
        };

        self.onmessage = function (message) {
            self.onReceiveData(JSON.parse(message.data));
        };

        self.onInterruptUpdate = function () {
            self._socket.send(JSON.stringify({action: 'stop'}));
        };

        self.onStartUpdate = function () {
            self._socket.send(JSON.stringify({action: 'start'}));
            $('#current-status #update').addClass('hidden');
            $('#current-status #interrupt').removeClass('hidden');
            $('#current-status #description-running').removeClass('hidden');
        };

        self.initialize = function () {
            self._socket = new WebSocket('ws://localhost:666/subscribe/db/update');
            self._socket.onopen = self.onopen;
            self._socket.onclose = self.onclose;
            self._socket.onmessage = self.onmessage;

            $('#current-status #update').click(self.onStartUpdate);
            $('#current-status #interrupt').click(self.onInterruptUpdate);
        };

        self.initialize();
    }
    dbUpdateStatus = new DbUpdateStatus();
});