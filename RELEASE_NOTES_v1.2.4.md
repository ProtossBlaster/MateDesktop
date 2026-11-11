**Install this one if Mate stays on 4.25.0 on Windows.** Desktop 1.2.3 installed with the setup `.exe`
over an earlier version kept the earlier version's library records next to the new ones. The app read
the old ones and refused every Mate after 4.25.0: the version badge turns red, and restarting does not
change it ([#12](https://github.com/ProtossBlaster/MateDesktop/issues/12)). This installer removes the
previous version's libraries before it copies its own.

### Installing it

Run the setup over the app you have: your history and settings stay where they are. Then open Mate: it
downloads the newest Mate by itself. Don't uninstall first: uninstalling removes the data too.

On a Mac, drag it over the old app in Applications as usual.

### Nothing else changes

The same libraries as 1.2.3, the same windows and the same data folder. The installer carries Mate
v4.25.0, and the app moves to the newest Mate on its first launch.
