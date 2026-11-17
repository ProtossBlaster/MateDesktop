**Install this one if Mate says it could not start, after waiting a while.** The app gave Mate 25
seconds to start and then stopped it. On some computers Mate takes longer than that, and every launch
ended with *Mate could not start* a moment before Mate answered
([#13](https://github.com/ProtossBlaster/MateDesktop/issues/13)). The app now waits as long as Mate is
still starting, up to three minutes, and stops waiting at once if Mate exits.

### Installing it

Run the setup over the app you have: your history and settings stay where they are. Then open Mate: it
downloads the newest Mate by itself. Don't uninstall first: uninstalling removes the data too.

On a Mac, drag it over the old app in Applications as usual.

### Nothing else changes

The same libraries as 1.2.4, the same windows and the same data folder. The installer carries Mate
v4.25.0, and the app moves to the newest Mate on its first launch.
