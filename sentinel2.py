#!/usr/bin/env python

"""
################################################################################
#                                                                              #
# sentinel2                                                                    #
#                                                                              #
################################################################################
#                                                                              #
# LICENCE INFORMATION                                                          #
#                                                                              #
# This program is a security monitoring program that uses video to detect      #
# motion, that records motion video, and attempts to communicate alerts as     #
# configured.                                                                  #
#                                                                              #
# copyright (C) 2023 Will Breaden Madden, wbm@protonmail.ch                    #
#                                                                              #
# This software is released under the terms of the GNU General Public License  #
# version 3 (GPLv3).                                                           #
#                                                                              #
# This program is free software: you can redistribute it and/or modify it      #
# under the terms of the GNU General Public License as published by the Free   #
# Software Foundation, either version 3 of the License, or (at your option)    #
# any later version.                                                           #
#                                                                              #
# This program is distributed in the hope that it will be useful, but WITHOUT  #
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or        #
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for     #
# more details.                                                                #
#                                                                              #
# For a copy of the GNU General Public License, see                            #
# <http://www.gnu.org/licenses>.                                               #
#                                                                              #
################################################################################

usage:
    program [options]

options:
    -h, --help                   display help message

    --version                    display version and exit

    --phone_number=STRING        phone number (starting with "+") used for
                                 Signal alerts (no alerts sent if not specified)
                                                                [default: none]

    --detection_threshold=INT    detection threshold            [default: 50000]

    --launch_delay=INT           delay (s) before run           [default: 5]

    --record_duration=INT        record time (s)                [default: 5]
"""

import cv2
import docopt

import socket
import subprocess
import time

__version__  = "2023-09-06T1614Z"

options = docopt.docopt(__doc__, version = __version__)

last_msg_time = 0

phone_number    = None if options["--phone_number"].lower() == "none" else\
                          options["--phone_number"]
threshold       =     int(options["--detection_threshold"])
delay_launch    =     int(options["--launch_delay"])
duration_record =     int(options["--record_duration"])
host_name       = socket.gethostname()

print(f'sentinel2 version {__version__}')
print('press \'q\' to quit')
print(f'phone number:    {phone_number}')
print(f'threshold:       {threshold}')
print(f'launch delay:    {delay_launch}')
print(f'record duration: {duration_record}')

def send_signal_message(
    sender_number    = phone_number,
    recipient_number = phone_number,
    message          = "motion detected"
    ):
    global last_msg_time
    current_time = time.time()
    if current_time - last_msg_time < 30:
        return False
    try:
        cmd = f'signal-cli -a {sender_number} send {recipient_number} -m "{message}"'
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        last_msg_time = current_time
        return True
    except Exception as e:
        print(f"error sending Signal message: {e}")
        return False

def actions_on_motion_detection():
    message = time.strftime("%y-%m-%dT%H%M%S") + " " + host_name + " motion detected"
    print(message)
    if phone_number:
        send_signal_message(message=message)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'mp4v'))
    filename = time.strftime("%y-%m-%dT%H%M%S") + ".mp4"
    out = cv2.VideoWriter(
        filename,
        cv2.VideoWriter_fourcc(*'mp4v'),
        25,
        (int(cap.get(3)),
        int(cap.get(4))))
    start_time = time.time()
    while int(time.time() - start_time) < duration_record:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
    out.release()

def list_camera_devices():
    # List available camera devices using the v4l2-ctl command-line utility.
    devices = []
    try:
        output = subprocess.check_output(
            ["v4l2-ctl", "--list-devices"],
            stderr=subprocess.STDOUT)
        blocks = output.decode("utf-8").split("\n\n")
        for block in blocks:
            if "video" in block:
                lines = block.strip().split("\n")
                name = lines[0].strip().split(": ")[1]
                paths = [line.strip() for line in lines[1:]]
                devices.append((name, paths))
    except Exception:
        pass
    return devices

# Prompt the user to select a camera device.
devices = list_camera_devices()
if not devices:
    print("no camera devices found")
    exit()
elif len(devices) == 1:
    selection = 0
else:
    print("available camera devices:")
    for i, (name, paths) in enumerate(devices):
        print(f"{i}: {name}")
    while True:
        try:
            selection = int(input("Enter the number of the camera device you want to use: "))
            if selection < 0 or selection >= len(devices):
                print("Invalid selection. Please enter a number between 0 and ", len(devices) - 1)
            else:
                break
        except ValueError:
            print("Invalid selection. Please enter a number between 0 and ", len(devices) - 1)

print(f'waiting {delay_launch} s delay before launch')
time.sleep(delay_launch)
print('launching sentinel2 on ' + host_name)

# Open the selected camera device.
paths = devices[selection][1]
for path in paths:
    cap = cv2.VideoCapture(path)
    if cap.isOpened():
        print(f"camera device {selection}: {devices[selection][0]} ({path}) open")
        break

# Create a background subtractor.
fgbg = cv2.createBackgroundSubtractorMOG2()

while True:
    # Read the current frame.
    _, frame = cap.read()
    # Apply the background subtractor.
    fgmask = fgbg.apply(frame)
    # Find contours in the mask.
    contours, _ = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Draw the contours on the original frame.
    cv2.drawContours(frame, contours, -1, (0, 255, 0), 2)
    # Calculate the total contour area.
    total_area = sum(cv2.contourArea(c) for c in contours)
    # Check if the total area exceeds the threshold.
    if total_area > threshold:
        actions_on_motion_detection()
    # Show the output.
    cv2.imshow('sentinel2', frame)
    # Check if the user pressed the 'q' key.
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the VideoCapture object.
cap.release()
