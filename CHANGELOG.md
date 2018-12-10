### Changelog

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