#!/bin/bash

echo "Starting InsultServiceHost.py"
python3 InsultServiceHost.py > InsultServiceHost.log 2>&1 &
PID1=$!
sleep 2
echo "Starting InsultSubscriber.py"
python3 InsultSubscriber.py > InsultSubscriber.log 2>&1 &
PID2=$!
sleep 2
echo "Starting InsultClient.py"
python3 InsultClient.py > InsultClient.log 2>&1 &
PID3=$!


echo "$PID1, $PID2, $PID3"
echo "All services started successfully"
echo "Press any key to stop the services"
read
kill -9 $PID1
kill -9 $PID2
kill -9 $PID3

