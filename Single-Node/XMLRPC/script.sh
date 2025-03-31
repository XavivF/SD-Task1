#!/bin/bash

echo "Starting InsultServiceHost.py"
python3 -u InsultServiceHost.py > InsultServiceHost.log 2>&1 &
PID_ISH=$!
sleep 2
echo "Starting InsultSubscriber.py"
python3 -u InsultSubscriber.py > InsultSubscriber.log 2>&1 &
PID_IS=$!
sleep 2
echo "Starting InsultClient.py"
python3 -u InsultClient.py > InsultClient.log 2>&1 &
PID_IC=$!


echo "$PID_ISH, $PID_IS, $PID_IC"
echo "All services have started successfully"
echo "Press enter K to stop the services or press I to read the current insult list"
while true; do
    read key
    if [ "$key" == "K" ]; then
        echo "Stopping services..."
        kill -15 $PID_ISH
        kill -15 $PID_IS
        kill -15 $PID_IC
        if ps -p $PID_ISH > /dev/null || ps -p $PID_IS > /dev/null || ps -p $PID_IC > /dev/null; then
            echo "Some services are still running"
        else
            echo "All services have stopped successfully"
        fi
        break
    elif [ "$key" == "I" ]; then
        kill -s SIGUSR1 $PID_ISH
        echo "Reading current insult list..."
        grep Insults: InsultServiceHost.log | tail -n 1
    else
        echo "Invalid key pressed."
    fi
    echo "Press enter K to stop the services or press I to read the current insult list"
done
exit 0