#!/bin/bash

echo "Starting InsultServiceHost.py"
python3 -u InsultServiceHost.py > InsultServiceHost.log 2>&1 &
PID1=$!
sleep 2
echo "Starting InsultSubscriber.py"
python3 -u InsultSubscriber.py > InsultSubscriber.log 2>&1 &
PID2=$!
sleep 2
echo "Starting InsultClient.py"
python3 -u InsultClient.py > InsultClient.log 2>&1 &
PID3=$!


echo "$PID1, $PID2, $PID3"
echo "All services have started successfully"
echo "Press enter key to stop the services"
read
kill -15 $PID1
kill -15 $PID2
kill -15 $PID3
if ps -p $PID1 > /dev/null || ps -p $PID2 > /dev/null || ps -p $PID3 > /dev/null; then
    echo "Some services are still running"
else
    echo "All services have stopped successfully"
fi