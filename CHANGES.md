Release Notes
==========

Version 0.2.0 (BETA 2)
---------------

* Added new action to tell the camera to go to one of its presets and, upon completion, either resume the current patrol or issue the Off command action - this allows for the ability to stop a current patrol to do something else and then come back once the specified time has elapsed
* The brightness of the device will now represent the preset the device is currently on, i.e., 5 if on preset 5
* Added ability to dim/brighten the device with each percentage representing the corresponding preset (1% = preset 1, 5% = preset 5, etc)
* Added options in the device config on how long to remain on a brightness command until it either resumes the patrol or returns to the Off position (setting to zero will move the camera to the positon and stop it there, regardless of the off setting)
* Enabled continuous mode, plugin can be run manually or can be set to restart the patrol based on the device configuration with an optional randomizer to prevent anyone from detecting a pattern
* Removed event log debug messages when duplicating a preset in a device
* Removed Homebridge actions from the device actions list
* Fixed minor issue with duplicating a preset list item where duplicating in rapid succession would create duplicate keys and, thus, cause two devices to share the same key and the entire list to act wonky
* Fixed bug where when the preset name was calculated it would always say "seconds" instead of the interval chosen (each item will need to be edited and updated in order to see any changes in existing devices)
* When saving a device it will now always revert the list action back to Edit and will make the Off action Stay unless otherwise chosen

Version 0.1.0 (BETA 1)
---------------

* Initial plugin release


Development Notes
==========


Known Issues As Of The Most Current Release
---------------

* None

User Requested Features
---------------

* None

Wish List
---------------

* None