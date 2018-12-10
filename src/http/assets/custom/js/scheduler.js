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
    */
    function Step(id, action, data, visualizer) {
        var self = this;

        self._id = id;
        self._action = action;
        self._data = data;

        self._preparedData = null;
        self._onExecutionDoneCb = null;
        self._executeCb = null;
        self._executed = false;
        self._successorStep = null;

        self._visualizer = visualizer

        self._preparators = self._visualizer.getActionPreparators();
        self._executors = self._visualizer.getActionExecutors();

        // called as soon as the object is built
        self.prepare = function () {
            self._preparators[action](self._data, self._onReady);
        }

        // called when the prepared data is ready
        self._onReady = function (preparedData) {
            self._preparedData = preparedData;
            if (self._executeCb) {
                self._executeCb(self._preparedData);
            }
        }

        // called to execute the action
        // execution will be delayed if prepared data isn't ready
        self.execute = function () {
            if (self._preparedData === null) {
                self._executeCb = function (preparedData) {
                    self._executors[action](preparedData);
                    // if execution ever needs to be asynchroneous, this can be passed as a callback
                    self.onExecuted();
                }
            }
            else {
                self._executors[action](self._preparedData);
                // if execution ever needs to be asynchroneous, this can be passed as a callback
                self.onExecuted();
            }
        }

        // called when execution finishes
        self.onExecuted = function () {
            if (self._successorStep && self._triggerSuccessor) {
                self._successorStep.execute();
                // note, if execution ever needs to be asynchroneous, this
                // can be passed as a parameter to execte, to be called by the onExecuted of the successor
                // this callback hell is getting out of hands tho :p
                if (self._onSuccessorTriggered) {
                    self._onSuccessorTriggered();
                }
            }
            self._executed = true;
        }

        // define a successor step.
        self.defineSuccessor = function (step) {
            self._successorStep = step;
        }

        // trigger call of the successor step execution
        // this won't happen if execution of the current step isn't finished yet.
        // In this case, it will happen as soon as the current step is terminated
        // returns the step that has been executed.
        // pass `onTriggered` to set a callback to be executed when the step has actually been triggered.
        // note: used to avoid scheduling a burst of steps when a step takes a long time to prepare
        self.triggerSuccessor = function (onTriggered) {
            self._triggerSuccessor = true;
            if (self._executed && self._successorStep !== null) {
                self._successorStep.execute();
                onTriggered();
            }
            else {
                self._onSuccessorTriggered = onTriggered;
            }
            return self._successorStep;
        }

        self.hasSuccessor = function () {
            return self._successorStep !== null;
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

        self._delay = options.delay || 1000.0/12.0;

        self._scheduledStepsById = {};
        self._scheduledSteps = [];
        self._executedSteps = [];
        self._lastExecutedStep = null;

        self._visualizer = visualizer;
        self._visTimeout = null;

        /*
         * Schedule visualizing the given action with the given parameter.
         * The action can be any of
         * * `displayFrame`: display the next frame
         */
        self.scheduleNextStep = function (id, action, data) {
            if (self._scheduledStepsById[id]) { return; }
            var step = new Step(id, action, data, self._visualizer);
            self._scheduledStepsById[id] = step;
            if (self._scheduledSteps.length > 0) {
                self._scheduledSteps[self._scheduledSteps.length - 1].defineSuccessor(step);
            }
            self._scheduledSteps.push(step);
        }

        /*
         * Execute the next step in the scheduled list of steps if there is one
         */
        self.executeNextStep = function() {
            var step;
            // if we already executed a step, trigger the execution of its successor
            if (self._lastExecutedStep !== null && self._lastExecutedStep.hasSuccessor()) {
                step = self._lastExecutedStep.triggerSuccessor(function () {
                    // only execute next step a delay *after* the successor has been executed
                    self._visTimeout = setTimeout(self.executeNextStep, self._delay);
                });
                self._executedSteps.push(step);
                self._lastExecutedStep = step;
                return;  // don't schedule next step right away, wait for the triggering of successor
            }
            // if exists, but does not have a successor at this point, do nothing
            // otherwise (and if there is any to execute), execute the first of the list
            else if (self._lastExecutedStep === null && self._scheduledSteps.length > 0) {
                step = self._scheduledSteps[0];
                self._executedSteps.push(step);
                self._lastExecutedStep = step;
                step.execute();
            }
            self._visTimeout = setTimeout(self.executeNextStep, self._delay);
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
    }

    window.Step = Step;
    window.Scheduler = Scheduler
});