# Run the unittests when DBus isn't present.  This is usfull for running the
# tests in a non-X environment.

# this comes from http://www.estamos.de/blog/2009/05/08/running-syncevolution-as-cron-job/
# env `dbus-launch` sh -c 'trap "kill $DBUS_SESSION_BUS_PID" EXIT; ./run.sh --unittest utiltest > /home/pcf/test_output.txt 1>&2' || true
env `dbus-launch` bash -c "trap \"kill $DBUS_SESSION_BUS_PID\" EXIT; ./run.sh --unittest $@"
