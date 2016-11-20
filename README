===========================================================================

Seeking a maintainer

This project is seeking a maintainer. The original authors abandoned
the project, even the web-site is now gone.

I (htgoebel) exhumed the source, split it into sub-projects and
converted it to git. But I'm not able to maintain it. So If you are
interested in this software, I'll happily hand over ownership of the
project.

===========================================================================

===========================================================================
Coherence - a DLNA/UPnP Media Server and  Framework for the Digital Living
===========================================================================

Coherence is a framework written in Python,
providing several UPnP MediaServers and MediaRenderers,
and enabling your application to participate in digital living networks.

It is licenced under the MIT licence.

Coherence is known to work with various clients
   - Sony Playstation 3
   - XBox360
   - Denon AV Receivers
   - WD HD Live MediaPlayers
   - Samsung TVs
   - Sony Bravia TVs

and much more...
   http://coherence-project.org/wiki/SupportedDevices

As time evolves you will find in this file more detailed
installation and basic configuration instructions.

For now please pardon the inconvenience
and have a look @ http://coherence-project.org


Installation from source
========================

After downloading and extracting the archive or having done a git
clone, move into the freshly created 'Coherence' folder and install
the files with

  sudo python ./setup.py install

This will copy the Python module files into your local Python package
folder and the coherence executable to '/usr/bin/coherence'.

http://coherence-project.org/wiki/DocumentationDepartment


Quickstart
==========

To just export some files on your hard-disk fire up Coherence with
an UPnP MediaServer with a file-system backend enabled::

  coherence --plugin=backend:FSStore,content:/path/to/your/media/files

A list of all available backends will get printed with::

  coherence --help

More information about the backends and their specific configuration:

  http://coherence-project.org/wiki/Backends

For a continuous operation the use of a config file is highly recommended.

  http://coherence-project.org/wiki/XMLConfig

The config file can be placed anywhere, coherence looks by default for
``$HOME/.coherence``, but you can pass the path via the commandline option
'-c' to it too::

  coherence -o /path/to/config/file -more -options


Troubleshooting
===============

If your MediaServer doesn't show up on your client most of the time
networking issue are responsible for that.

 - Your system has more than one network interface?
 
   Specify the network interface to use in the config file.

 - Add a multicast route, pointing to the proper network interface::

     route add -net 239.0.0.0 netmask 255.0.0.0 eth0

 - Any firewall on your system?

Writing and integrating your own backend/plugin
===============================================

You can extend the functionality of coherence by writing your own backends/plugins.
 
- A good starting point for coders, interested in writing their own backend,
  would be taking a look at the LolCatsStorage example. The LolCatsStorage
  is a very simple and well commented backend. You can find it inside the
  backends directory of coherence.

- To integrate your own backend, open the file ``setup.py`` of the coherence
  installer and add it to the list of ``entry_points``. Also copy your backend 
  into the subfolder ``coherence/backends`` of the coherence installer. Finally 
  start the installation like described above (Installation from source). 

Support
=======

First there is our wiki at http://coherence-project.org/. If you find
an error there or think there is some information missing please get
yourself an account and correct that issue. Thx!

Then we have a mailinglist coherence-dev@lists.beebits.net.
You add yourself here:

  http://lists.beebits.net/cgi-bin/mailman/listinfo/coherence-dev

And last but not least, there is our irc channel

  irc://irc.freenode.net/#coherence

where a lot of other users and most of the developers are around.

..
  Local Variables:
  mode: rst
  ispell-local-dictionary: "american"
  End:
