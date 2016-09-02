#!/bin/bash
cd ~/cachet-uptime-robot
source bin/activate
python update_status.py config.ini
