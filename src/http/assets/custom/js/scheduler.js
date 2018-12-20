$(function() {
    /*
    * Allow the execution of an ordered, chained list of steps which requires asynchroneous
    * data loading before execution.
    * The chain of events is as follow:
    * 1. The step is initialized, preparation happens immediately
    * 2. If execution happens before the preparation is finished, a flag is set to
    *    execute the step as soon as the preparation is ready
    * 3. When the preparation is ready, a flag is set to execute the step whenever requested.
    *    If execution was already requested, it happens now.
    * 4. At any time, a 'next' step can be scheduled to be executed when the current one
    *    finishes
    * 5. The next step can be triggered at any (later) time, but will only be executed once
    *    the current one finishes. It won't be until it is triggered tho.
    * 5. When execution finishes, if a next step is defined AND triggered, it is executed.
    * PArameters:
    * * id: unique id for this step
    * * action: action this step is going to execute. The action should have a corresponding
    *       preparator and executor on the given visualizer.
    * * data: action data
    * * visualizer: an object able to visualize the execution of this step.
    *       It should hold two functions: `getActionPreparators()` and `getActionExecutors()`,
    *       The former should return a mapping where each action supported by the visualizer is associated
    *           with a preparation function, that takes `(data, done)` as param and should call `done(preparedData)`
    *       The latter should return a mapping where each action supported by the vusializer is associated
    *           with an execution function, that takes the prepared data as param and renders the step.
    * * callbacks:
    *       * onExecuted(execReport): called after execution of the step, providing a small
    *           execution report as a {preparationDuration, executionDuration, executionDelay} where:
    *               * preparationDuration is the duration of the preparation
    *               * executionDuration is the duration of the execution
    *               * executionDelay is the delay incurred due to an unprepared execution
    *                   It does not account for a delay between preparation and execution due to scheduling
    */
    function Step(id, action, data, visualizer, callbacks) {
        var self = this;

        self._id = id;
        self._action = action;
        self._data = data;

        self._executed = false;
        self._triggerSuccessor = false;
        self._reversed = false;
        self._ready = false;

        self._preparedData = null;
        self._onExecutionDoneCb = null;
        self._executeCb = null;
        self._successorStep = null;
        self._predecessorStep = null;

        self._visualizer = visualizer

        self._preparators = self._visualizer.getActionPreparators();
        self._executors = self._visualizer.getActionExecutors();

        self._startPreparation = null;
        self._preparationDuration = null;
        self._startExecution = null;
        self._startRealExecution = null;
        self._triggered = null;
        self._predecessorTriggered = null;

        self._callbacks = {
            onExecuted: (callbacks || {}).onExecuted || function() {}
        };

        // called as soon as the object is built
        self.prepare = function () {
            self._startPreparation = Date.now()
            self._preparators[action](self._data, self._onReady);
        }

        // called when the prepared data is ready
        self._onReady = function (preparedData) {
            self._preparationDuration = Date.now() - self._startPreparation;
            self._preparedData = preparedData;
            self._ready = true;
            if (self._executeCb) {
                self._executeCb(self._preparedData);
            }
        }

        // called to execute the action
        // execution will be delayed if prepared data isn't ready
        // pass in the timestamp when the predecessor got triggered to provide monitoring capability
        self.execute = function (predecessorTriggered) {
            self._startExecution = Date.now();
            self._predecessorTriggered = predecessorTriggered;
            if (self._preparedData === null) {
                self._executeCb = function (preparedData) {
                    self._startRealExecution = Date.now();
                    self._executors[action](preparedData, self._id);
                    // if execution ever needs to be asynchroneous, this can be passed as a callback
                    self.onExecuted();
                }
            }
            else {
                self._startRealExecution = self._startExecution;
                self._executors[action](self._preparedData, self._id);
                // if execution ever needs to be asynchroneous, this can be passed as a callback
                self.onExecuted();
            }
        }

        // called when execution finishes
        self.onExecuted = function () {
            var executionDuration = Date.now() - self._startRealExecution;
            var executionDelay = self._startRealExecution - self._startExecution;
            var triggerDelay = Date.now() - self._predecessorTriggered
            if (self._successorStep && self._triggerSuccessor) {
                self._triggerSuccessor = false;
                self._successorStep.execute(self._triggered);
                // note, if execution ever needs to be asynchroneous, this
                // can be passed as a parameter to execte, to be called by the onExecuted of the successor
                // this callback hell is getting out of hands tho :p
                if (self._onSuccessorTriggered) {
                    var fn = self._onSuccessorTriggered;
                    self._onSuccessorTriggered = null;
                    fn();
                }
            }
            self._executed = true;
            self._executeCb = null;

            self._callbacks.onExecuted({
                id: self._id,
                executionDuration,
                executionDelay,
                preparationDuration: self._preparationDuration,
                triggerDelay
            });
        }

        // define a successor step.
        self.defineSuccessor = function (step) {
            self._successorStep = step;
        }

        // define a predecessor step
        self.definePredecessor = function (step) {
            self._predecessorStep = step;
        }

        // trigger call of the successor step execution
        // this won't happen if execution of the current step isn't finished yet.
        // In this case, it will happen as soon as the current step is terminated
        // returns the step that has been executed.
        // pass `onTriggered` to set a callback to be executed when the step has actually been triggered.
        // note: used to avoid scheduling a burst of steps when a step takes a long time to prepare
        self.triggerSuccessor = function (onTriggered) {
            var _onTriggered = function () {
                // re-reverse so next time it is triggered we'll get back in the right order
                if (self._reversed) {
                    self.reverse();
                    self._reversed = false;
                }
                onTriggered();
            }
            var step = self._successorStep;
            self._triggered = Date.now();
            if (self._executed && step !== null) {
                self._executed = false;
                step.execute(self._triggered);
                _onTriggered();
            }
            else {
                self._triggerSuccessor = true;
                self._onSuccessorTriggered = _onTriggered;
            }
            return step;
        }

        self.hasSuccessor = function () {
            return self._successorStep !== null;
        }

        self.hasPredecessor = function () {
            return self._predecessorStep !== null;
        }

        // reverse the steps execution -
        self.reverse = function() {
            [self._successorStep, self._predecessorStep] = [self._predecessorStep, self._successorStep];
            self._reversed = true;
        }

        self.prepare();
    }

    /*
     * Schedules visualization steps as they are made available by the server
     * Executes scheduled visualization steps at constant timesteps.
     * Prepares the scheduled steps in advance so that no lag will happen upon execution due to loading time
     * The `visualizer` parameter should be an object able to prepare and execute scheduled actions
     * The `options` parameter can hold the following fields:
     * * `delay`: delay between visualization steps in ms. Default 1000ms.
     */
    function Scheduler(visualizer, options) {
        var self = this;

        options = options || {}

        self._delay = options.delay || 1000.0;

        // self._scheduledStepsById = {};
        self._steps = [];
        self._stepIdToPos = {};
        self._lastExecutedStep = null;

        self._visualizer = visualizer;
        self._visTimeout = null;
        self._lockReversed = false;

        self.reset = function () {
            self._steps = [];
            self._lastExecutedStep = null;
        }

        self._onStepExecutionReport = function (report) {
            var {executionDuration, executionDelay, preparationDuration, triggerDelay} = report;
            if (executionDuration + executionDelay > self._delay) {
                self._visualizer.notifyOvertime(executionDuration + executionDelay);
            }
            else if (triggerDelay  > self._delay) {
                self._visualizer.notifyOvertime(triggerDelay );
            }
            else {
                self._visualizer.notifyOvertime();
            }
        }

        /*
         * Schedule visualizing the given action with the given parameter.
         * The action can be any of
         * * `displayFrame`: display the next frame
         */
        self.scheduleNextStep = function (id, action, data) {
            // we expect the analyzer to send some annotation_raw more than once for a given frame
            // and that's ok! We'll display them twice, there is likely more data available the second time
            // TODO: identify the stages of 'annotation_raw' differently then bring back the de-duplication code below
            // if (self._scheduledStepsById[id]) { return; }
            var step = new Step(id, action, data, self._visualizer, {
                onExecuted: self._onStepExecutionReport
            });
            // self._scheduledStepsById[id] = step;
            if (self._steps.length > 0) {
                // double chained list
                var lastStep = self._steps[self._steps.length - 1];
                lastStep.defineSuccessor(step);
                step.definePredecessor(lastStep);
            }
            self._steps.push(step);
            self._stepIdToPos[id] = self._steps.length - 1;
        }

        /*
         * Execute the next step in the scheduled list of steps if there is one
         */
        self.executeNextStep = function(schedule, reverse) {
            var step;
            var doneReverse = false;
            // default to true is weird, but makes things a bit easier to make recurrent scheduling work
            if (schedule === undefined) { schedule = true; }


            // if the last executed step has no successor, we'll never move forward or backward and
            // thus we'll never put the state in the reversed state the user ask.
            // So when pressing 'backward' at the end of the play, we'll never go one step back
            // Ditto when pressing 'forward' at the beginning of the play (in reverse lock), we'll never go one step back
            if (self._lastExecutedStep !== null && !self._lastExecutedStep.hasSuccessor()) {
                if ((reverse && !self._lastExecutedStep._reversed) ||
                    (!reverse && self._lastExecutedStep._reversed)) {
                    self._lastExecutedStep.reverse();
                    doneReverse = true;
                }
            }

            // if we already executed a step, trigger the execution of its successor
            if (self._lastExecutedStep !== null && self._lastExecutedStep.hasSuccessor()) {
                if ((reverse || self._lockReversed) && !doneReverse) { self._lastExecutedStep.reverse(); }
                if (self._lastExecutedStep.hasSuccessor()) {  // that may have changed if we reversed the first step
                    step = self._lastExecutedStep.triggerSuccessor(function () {
                        // only execute next step a delay *after* the successor has been executed
                        if (schedule) {
                            self._visTimeout = setTimeout(self.executeNextStep, self._delay);
                        }
                    });
                    self._lastExecutedStep = step;
                    return;  // don't schedule next step right away, wait for the triggering of successor
                }
            }
            // if exists, but does not have a successor at this point, do nothing
            // otherwise (and if there is any to execute), execute the first of the list
            else if (self._lastExecutedStep === null && self._steps.length > 0) {
                step = self._steps[0];
                self._lastExecutedStep = step;
                step.execute(Date.now());
            }

            if (schedule) {
                self._visTimeout = setTimeout(self.executeNextStep, self._delay);
            }
        }

        self.speedUp = function () {
            self._delay *= 0.5;
            return self._delay;
        }
        self.speedDown = function () {
            self._delay *= 2;
            return self._delay;
        }

        self.pause = function () {
            if (self._visTimeout) {
                clearTimeout(self._visTimeout);
            }
            self._visTimeout = null;
        }

        self.play = function () {
            if (self._visTimeout) { clearTimeout(self._visTimeout); }
            self.executeNextStep();
        }

        // if currently playing, early schedule of the next step
        // if currently in pause, just display the next step
        self.step = function (reverse) {
            if (self._visTimeout) {
                clearTimeout(self._visTimeout);
                self.executeNextStep(true, reverse);
            }
            else {
                self.executeNextStep(false, reverse);
            }
        }

        // go to and execute the step that has the specified id
        self.goto = function(stepId) {
            var stepN = self._stepIdToPos[stepId];
            if (stepN >= self._steps.length || stepN === undefined || stepN === null || stepN < 0) {
                console.error("Unable to find step with id: ", stepId);
                return;
            }
            self._lastExecutedStep = self._steps[stepN];
            self._lastExecutedStep.execute(Date.now());
        }

        self.reverse = function () {
            self._lockReversed = !self._lockReversed;
            if (self._lastExecutedStep !== null && !self._lastExecutedStep.hasSuccessor()) {
                // we'll never actually revert since that happens upon triggering execution of
                // the successor, and this guy doesn't have any. Do it now.
                // note: this applies whether we're in reverse lock on step 1 and
                // when we're on last step in standard mode
                self._lastExecutedStep.reverse();

            }

        }
    }

    window.Step = Step;
    window.Scheduler = Scheduler
});