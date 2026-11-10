---
project: aiml-p10
client_industry: Manufacturing
date: 2023-12
duration_weeks: 12
repo: loom-vision
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Defect detection on a textile production line

## The problem
Faisal Textiles (Manufacturing) came to me because manual inspection missed small weaving defects at line speed.

## What I built
Over 12 weeks I delivered an object detector trained on 9k annotated frames and exported to run on edge devices beside each loom. The work used Python, deep learning model training, YOLOv8, OpenCV, NVIDIA Jetson.

## Results
- defect recall of 0.91 at 25 FPS on the device
- customer returns for weaving faults down 27%

> "Worked on the factory floor, not just in the demo." - Faisal Textiles team
