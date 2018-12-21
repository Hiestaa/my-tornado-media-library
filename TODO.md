
## bugs

* When creating a new tag by changing the value of a tag attached to a video to a value that doesn't exist, two tags end up being created. One for the specified value, and what for the specified value capitalized.

## Short term

* Post-processing
    * "Smoothing" function, like a moving average, because the motion in the video can be assumed to be smooth
    * ignore 'flickering' faces a face that only shows up for less than N frames
    * Using landmarks, discard faces with unstable landmarks (note: in the reference of the rect for normalization, this doesn't apply to motion), as it must indicate an unconfident face detection (a similar image, the next frame, should have landmarks at the similar position, the face couldn't possibly have changed much)

## Long term

* Make a bulk analysis page (similar to db update process)
* filter album by tags and properties, random should only use those tags
* albums playlist
* sorting order for albums (including 'random')