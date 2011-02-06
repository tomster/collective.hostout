Some notes on using collective.hostout with FreeBSD jails using `ezjail <http://erdgeist.org/arts/software/ezjail/>`_.

Bootstrapping a default jail
============================

While ezjail supports so-called `flavours <http://erdgeist.org/arts/software/ezjail/#Flavours>`_ our aim here is to keep as much customization work as possible inside hostout (instead of re-implementing -- and maintaining -- hostout's policies in every OS we support). Therefore these instructions simply contain instructions on how to bring a default jail to a state where hostout's  ``bootstrap_users`` step can run.

To create a new jail use the provided fabfile ``fab_freebsd.py``. It expects to be run against the jail host with sudo privileges and ezjail installed. It also provides a hostout flavour that allows hostout to bootstrap itself.

Create Jail
***********

To create a jail and fire it up::

  sudo ezjail-admin create JAILNAME 192.168.91.7
  sudo /usr/local/etc/rc.d/ezjail.sh start JAILNAME

Enable SSH
**********


Bootstrap as root
*****************



Since the whole point of jails is privilege isolation, we will assume that it is safe to connect as ``root``
