# Run the unittests on a box without a X Display

# this comes from http://www.estamos.de/blog/2009/05/08/running-syncevolution-as-cron-job/
# env `dbus-launch` sh -c 'trap "kill $DBUS_SESSION_BUS_PID" EXIT; ./run.sh --unittest utiltest > /home/pcf/test_output.txt 1>&2' || true
env `dbus-launch` bash -c 'trap "kill $DBUS_SESSION_BUS_PID" EXIT; ./run.sh --unittest'
