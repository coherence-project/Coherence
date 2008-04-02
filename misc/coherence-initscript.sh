#!/bin/bash
#
#	/etc/rc.d/init.d/coherence
#
# Starts the coherence server
#
# chkconfig: 345 90 56
# description: An UPnP/DLNA MediaServer
# processname: coherence
# securlevel: 80
#
### BEGIN INIT INFO
# Provides: coherence
# Default-Start: 3 4 5
# Required-Start: $network messagebus
# Required-Stop: $network messagebus
# Short-Description: Starts the coherence server
# Description: An UPnP/DLNA MediaServer
### END INIT INFO

# Source function library.
. /etc/rc.d/init.d/functions

PROGNAME=coherence
CONFIGFILE=/etc/coherence/coherence.conf
LOGFILE=/var/log/coherence
test -x /usr/bin/$PROGNAME || exit 0

RETVAL=0

#
# See how we were called.
#

start() {
	# Check if it is already running
	if [ ! -f /var/lock/subsys/$PROGNAME ]; then
	    gprintf "Starting %s daemon: " "$DAEMON"
	    daemon python /usr/bin/$PROGNAME -d -c $CONFIGFILE -l $LOGFILE
	    RETVAL=$?
	    [ $RETVAL -eq 0 ] && touch /var/lock/subsys/$PROGNAME
	    echo
	fi
	return $RETVAL
}

stop() {
	gprintf "Stopping %s daemon: " "$DAEMON"
	killproc python /usr/bin/$PROGNAME
	RETVAL=$?
	[ $RETVAL -eq 0 ] && rm -f /var/lock/subsys/$PROGNAME
	echo
        return $RETVAL
}


restart() {
	$0 stop
	$0 start
}	

reload() {
	trap "" SIGHUP
	killall -HUP $PROGNAME
}	

case "$1" in
start)
	start
	;;
stop)
	stop
	;;
reload)
	reload
	;;
restart)
	restart
	;;
condrestart)
	if [ -f /var/lock/subsys/$PROGNAME ]; then
	    restart
	fi
	;;
status)
	status $PROGNAME 
	;;
*)
	INITNAME=`basename $0`
	gprintf "Usage: %s {start|stop|restart|condrestart|status}\n" "$INITNAME"
	exit 1
esac

exit $RETVAL
