# Your custom files

This directory belongs to you. Section 11 updates preserve its files.

Keep your own files here or outside the data folder. Outside `section11/`, updates
remove files in any folder named exactly like a Section 11 release or historical
file, except the keep list in the installed `section11/examples/maintenance/UPDATING.md`.
Protection ignores case; removal requires exact spelling.

You may override official guidance, but a customization can break assumptions,
conflict with another file or become incompatible with a later release. Record
which files are active, which official rules they override and why.

To recover, deactivate or remove the custom file, tell the AI to disregard what
it took from that file, refresh its connector or uploaded sources, and re-read
the official rule. Use a fresh chat or clean project if old context persists.
Removing a file does not erase prior conversations or prove the AI forgot it.

Keep credentials in GitHub Secrets or your private local configuration. Never
commit credentials here. The dossier lives as `DOSSIER.md` in the data-folder
root (repository root on GitHub), not in `custom/`. A repository containing it
must stay private because Git keeps old versions. A public repository exposes
its custom files, training data and route maps.
