#!/usr/bin/env python3

"""
################################################################################
#                                                                              #
# sentinel2                                                                    #
#                                                                              #
################################################################################
#                                                                              #
# LICENCE INFORMATION                                                          #
#                                                                              #
# This program monitors a camera feed to detect motion. If movement is         #
# detected, a video of specified duration is recorded and an optional alert    #
# message is sent.                                                             #
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

    --detection_threshold=INT    detection threshold            [default: 30000]

    --launch_delay=INT           delay (s) before run           [default: 5]

    --record_duration=INT        record time (s)                [default: 10]

    --non_gui                    run without GUI (no window display)
"""

import socket
import subprocess
import time

import cv2
import docopt
import numpy as np

__version__  = "2025-01-08T2222ZS"

options = docopt.docopt(__doc__, version=__version__)

last_msg_time = 0

phone_number    = None if options["--phone_number"].lower() == "none" else options["--phone_number"]
threshold       = int(options["--detection_threshold"])
delay_launch    = int(options["--launch_delay"])
duration_record = int(options["--record_duration"])
non_gui_mode    = options["--non_gui"]
host_name       = socket.gethostname()

print(f'sentinel2 version {__version__}')
print('press \'q\' to quit')
print(f'phone number:    {phone_number}')
print(f'threshold:       {threshold}')
print(f'launch delay:    {delay_launch}')
print(f'record duration: {duration_record}')
print(f'non-GUI mode:    {non_gui_mode}')

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
    message = time.strftime('%Y-%m-%dT%H%M%SZ', time.gmtime()) + " " + host_name + " motion detected"
    print(message)
    if phone_number:
        send_signal_message(message=message)

    start_time = time.time()
    frames = []

    # Count the number of frames from the start time for saving purposes.
    while int(time.time() - start_time) < duration_record:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = time.strftime('%Y-%m-%dT%H%M%SZ', time.gmtime())
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_thickness = 1
        (text_width, text_height), _ = cv2.getTextSize(timestamp, font, font_scale, font_thickness)
        
        frame_height = frame.shape[0]
        frame_width = frame.shape[1]
        new_frame_height = frame_height + text_height + 10

        new_frame = np.zeros((new_frame_height, frame_width, 3), dtype=np.uint8)
        new_frame[0:frame_height, 0:frame_width] = frame

        text_x = int((frame_width - text_width) / 2)
        text_y = frame_height + text_height

        cv2.putText(
            new_frame,
            timestamp,
            (text_x, text_y),
            font,
            font_scale,
            (255, 255, 255),
            font_thickness
        )

        frames.append(new_frame)

    end_time = time.time()
    total_time = end_time - start_time
    frame_count = len(frames)

    if total_time > 0:
        actual_fps = frame_count / total_time
    else:
        actual_fps = 10.0 # fallback

    print(f"Recorded {frame_count} frames in {total_time:.2f} seconds.")
    print(f"Writing video at ~{actual_fps:.2f} FPS.")

    filename = time.strftime('%Y-%m-%dT%H%M%SZ', time.gmtime()) + '.mp4'
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    frame_height = frames[0].shape[0]
    frame_width = frames[0].shape[1]
    out = cv2.VideoWriter(filename, fourcc, actual_fps, (frame_width, frame_height))

    for f in frames:
        out.write(f)

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
            if "/dev/video" in block:
                lines = block.strip().split("\n")
                name = lines[0].strip()
                paths = [line.strip() for line in lines[1:] if '/dev/video' in line]
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
                print("Invalid selection. Please enter a number between 0 and", len(devices) - 1, ".")
            else:
                break
        except ValueError:
            print("Invalid selection. Please enter a number between 0 and", len(devices) - 1, ".")

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
else:
    print("Failed to open camera device.")
    exit()

# Create a background subtractor.
fgbg = cv2.createBackgroundSubtractorMOG2()

try:
    while True:
        # Read the current frame.
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

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

        if not non_gui_mode:
            # Show the output.
            cv2.imshow('sentinel2', frame)
            # Check if the user pressed the 'q' key.
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            # In non-GUI mode, add a small sleep to prevent high CPU usage.
            time.sleep(0.01)
except KeyboardInterrupt:
    print("Interrupted by user. Exiting...")

# Release the VideoCapture object and close windows.
cap.release()
cv2.destroyAllWindows()
