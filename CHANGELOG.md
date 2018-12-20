### Changelog

### *Thursday Dec 20*

* Make visually apparent the fact that a video has been analyzed: add an icon somewhere in the video title and the "Analyze" label making obvious that this has been done already
* Support forcing re-analysis when it has already been completed. Only generate minivid if needed
* Fixed thumbnail delete issue when thumbnail was never set

### *Wednesday Dec 19*

* Display the face time, face time propertion and face ratio average in the video details
* Display the time it took between the execution of a frame and the execution of the subsequent one, if more than the expected delay happened between the two (whether due to server lag between two steps due to slower generation than display, server lag to load the image or delay in the actual execution (tho this is already implemented))


### *Tuesday Dec 18 2018*

* If the analysis was interrupted or cleaned up, restart when reopening the modal.
  (if got completed, don't, as it would cleanup the completed existing analysis)
  Be sure to reset the state of the visualizer when doing so.
* Fixed mouse over the sparkline not displaying the right frame
* Retrieve detection confidence value (only for the dlib extractr)

### *Mon Dec 17 2018*

* Support control the current visualizing step using the sparkline mouseover
* Support interrupting the analysis
* Support cleaning up analysis workspace (a button appearing when the analysis is complete?)

### *Sun Dec 16*

* Move minivid images to `./workspace`
* Add progress bar to minivid generation
* Add progress bar to batches analysis and post-processing
* Log download related web requests as debug
* Store completed analysis cache in the snapshot folder
* Fix bugs where images were not presented in the right order to the annotator causing analysis
  result of the wrong frame to be rendered.
  It was due to the alphabetical order not matching the frame order when the number of digits of the
  frame number was exceeding the allowed number (e.g. 10000+ on a 4 digits-basis)

### *Thursday Dec 11 2018*

(and previous days)

* Revamp of the analyzer code to support two other face extraction algorithm both based on DeepFaceLab
* Add visualization of the rect detection progress (pre-step of the face detection)
* Add rewind & image-per-image mode to the analysis visualizer
* Don't log download-related web requests

### *Sun Dec 09 2018*

* Fixed vidsnap jankyness when initially adding all snapshots
* Added video activity sparkline to the tags displayer
* Added more video details to the tags displayer and made it sticky
* Added black overlay when visualizing video snapshots
* Fixed drop-down z-index between the player controls drop-down, the tag selectize drop-down and the snapshots container

### *Sat Dec 08 2018*

* Fixed some vidsnap zoom jankyness
* Added video seen/displayed/favorite/tagged history and fixed the 'last favorite' sort order
* Added negation of filters
* Made "Open Folder" and "Analyze" vid player control part of drop-down


### *Tue Dec 03 2018*

* Save the current state of the filters, page and sort order in the URL instead of the server memory. What the heck was I thinking.

### *Thu Dec 06 2018*

* Improved db update tool to use websocket instead of ajax calls. I won't go into the details of how awesome this is because it shouldn't have been implemented with ajax calls in the first place. Hey, everybody has to start somewhere!
* Fixed the use of `time.time()` as default argument value as it would generate the time when the interpreter start and never ever update it for the entire lifetime of the server. How dumb!

### *Somewhere in 2016...*

Re-implementation in python + complete rewrite of the client code

### *Somewhere in 2014...*

Initial implementation in PHP...