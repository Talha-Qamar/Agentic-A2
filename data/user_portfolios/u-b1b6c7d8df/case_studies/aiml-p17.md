---
project: aiml-p17
client_industry: Healthcare
date: 2023-03
duration_weeks: 10
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Case study: RadAssist

**Situation.** Radiologists needed urgent studies pushed to the top of the reading list.
**Task.** Deliver a production-ready fix within 10 weeks for a healthcare business.
**Action.** A DenseNet classifier with Grad-CAM heatmaps that reorders the worklist; never used for diagnosis. Tooling: Python, deep learning model training, MONAI, DICOM.
**Result.** sensitivity 0.92 for urgent findings on the retrospective set; time-to-read for urgent cases down 31% in the pilot.
