# Arescope: English project submission

Ready-to-copy field text for the supplied submission form, 15 November 2026.
Copy the paragraphs beneath each field label. Submission notes explain link and
format choices; resource tables supply the **Link Text** and **Link Url** entries.

## Project Name

Arescope: Mars Rovers and Their Home Base

## Summary

Arescope is a mission-control prototype designed to connect Mars rovers, an uncrewed home base on Mars and Mission Control on Earth. Its target architecture has three levels: Guardian on each rover monitors risk; the Mars home base coordinates the local fleet, maintains a shared map, handles incidents and relays data to Earth; Earth Mission Control oversees decisions and reviews learning updates.

Our working public LAB is a browser-based software simulation of fleet coordination on archived NASA terrain. Up to six simulated rovers share survey work, report faults and coordinate simulated assistance, while serious incidents require operator approval. Guardian currently runs in LAB; onboard operation and a physical Mars base remain planned.

Arescope brings terrain awareness, incident handling and human-reviewed model improvement into one workflow. The next step is terrestrial rover testing to assess whether this approach can make remote exploration more resilient.

Future astronauts could later join rovers and the Mars home base on a common map and data exchange network, unifying surface operations toward a Mars surface "internet". This vision requires future communications development and testing.

## Project Demonstration

https://arescope.mrfenek.eu.cc/static/demo/Arescope-Fleet-Demo-30s.mp4

Submission note: use this 30-second MP4 for the demonstration field. It replays
states from the implemented LAB simulator and Guardian through the LAB terrain
and rover renderer offline, at 30 fps, with a simplified presentation overlay.
Adjacent starting survey lanes are staged and phase timing is accelerated and
edited. English captions and a visible AI-assistance and simulation disclosure
identify the software demonstration. The footage shows simulated rover
assistance, not physical repair or a built Mars home base. It is a rendered
simulation, not generative video. A copy is in presentation/demo in the public
GitHub repository.

Slide alternative:

https://github.com/Team-Arescope/arescope/blob/main/presentation/Arescope-V2-Pitch-With-Demo.pdf

The strict limit is seven slides including the greeting, video and closing.
The current pitch with embedded video meets it by combining the Spirit story,
communication delay and rover risks into one slide. Its standalone HTML works
offline; its PDF shows a linked video poster. The 30-second MP4 remains a direct
demonstration option for the form.

## Project

https://arescope.mrfenek.eu.cc

Submission note: use the public LAB URL above for this field. The source code
and technical evidence are also public and are linked in Project Details:

https://github.com/Team-Arescope/arescope

## Project Details

Arescope is a mission-control prototype for Mars rover teams, designed around three connected levels: each rover, an uncrewed home base on Mars, and Mission Control on Earth. It brings terrain awareness, vehicle condition, coordinated assistance and reviewed learning into one workflow. Our first working product is Arescope LAB, a public browser application that demonstrates these functions in software.

The problem is maintaining a useful operational picture when cameras lose detail, wheels slip, sensors drop out or communications fail. Earth cannot always intervene immediately. Operators need to know where each rover is, what it has surveyed, which data are becoming unreliable and whether another rover can help. Arescope complements existing autonomous navigation by connecting risk warnings with fleet coordination and operator decisions.

In the target architecture, Guardian runs onboard each rover to monitor recent telemetry and recommend a response. The Mars home base is the fleet's local coordination hub: it maintains a shared map, assigns survey areas, coordinates incident handling and relays mission data to Earth. Earth Mission Control provides oversight, reviews serious incidents and approves model updates. Today, Guardian inference and fleet coordination run in LAB; onboard deployment and the physical Mars base remain development goals.

Visitors can start one to six simulated rovers, adjust mission speed and introduce controlled faults. LAB displays terrain, positions, survey trails, coverage, warnings and events. Guardian evaluates signals including point count, frame rate, position jumps, lighting proxies, connectivity and commanded versus observed movement. Explicit mission rules and route search coordinate the response. Language models do not directly command the simulated wheels.

Our demonstration follows a complete recovery cycle. A rover encounters a simulated wheel obstruction and halts. A healthy neighbour follows a checked route, approaches and performs a timed service procedure while another rover continues surveying. Minor problems, such as wheel slip, obstruction or camera dust, can receive automatic simulated assistance. Serious faults, including sensor dropout and HQ link loss, require a Mission Control decision. The affected rover resumes only after three consecutive fresh nominal Guardian observations. The animation represents a simulated procedure, not a demonstration of physical repair.

LAB records incidents and operator labels, retrains a candidate model and evaluates it before human-approved activation. On a frozen synthetic hold-out of 36 trajectories and 1,152 windows, the adapted Guardian model detected 30 of 30 induced failures, compared with 26 of 30 for the baseline. Its mean warning lead time was 14.8 seconds, with 11 false-alarm windows among 492 overlapping nominal windows. These results describe that synthetic evaluation, not field reliability or guaranteed prediction. The learning loop keeps new model activation under human review.

NASA data provide the geographic foundation. HiRISE DTM DTEEC_001488_1750_001752_1750_U02 supplies a Gale crater strip approximately 9.97 by 4.05 km, about 40 square kilometres. MOLA MEGDR product MEGT00N000GB.IMG supplies regional elevation context. Source coordinates, sampling and attribution are documented in the repository. Archived elevation measurements remain separate from synthetic telemetry and routes. The orbital display grid cannot resolve wheel-scale traps or hidden ground strength.

LAB uses Python, FastAPI, SQLite, WebSockets, JavaScript, WebGL, HTML and CSS. A separate Unity/C# and OpenXR project targets Meta Quest 3S as a sensor-mast testbed; headset runtime verification remains outstanding. A server-side Voice Copilot prototype explores telemetry-aware language assistance through OmniRoute. AI tools assisted coding, debugging, research, interface design and presentation preparation; the team reviews and tests their outputs.

The next practical milestone is testing on a terrestrial rover chassis and transferring Guardian onboard. Remote inspection, field science and other robots with unreliable connectivity are potential Earth applications. In the longer term, astronauts could join rovers and the Mars home base through the same map and data exchange network. This would support a Mars surface "internet" unifying robots, bases and people. Its communications protocols and physical infrastructure require further development and testing.

Public prototype: https://arescope.mrfenek.eu.cc
Source code: https://github.com/Team-Arescope/arescope

## Use of Super Intelligence (SI)

Select all six categories used in this project:

- Coding, Debugging, or Troubleshooting
- Data Analysis and Interpretation
- Research or Information Gathering
- Building SI/ML Into the Project
- Presentation, Video, or Audio
- Visual Design or Image Creation

Disclosure text, if the form provides an explanation field:

OpenAI Codex and language-model agents assisted coding, debugging, testing, synthetic telemetry analysis, research synthesis, interface design, presentation writing and demo preparation. Guardian is an ML risk monitor currently evaluated in LAB with synthetic telemetry; the optional Voice Copilot uses server-side language models through OmniRoute. NASA measurements are kept separate from synthetic data. The video renders implemented simulation states with AI-assisted preparation and visible disclosure. The team reviews and tests the outputs; onboard Guardian and the physical Mars home base remain planned.

Submission note: the form requires visible SI-generated watermarks on generated
images and videos, and descriptive text plus metadata disclosure for generated
audio, code and data. Apply those labels to the relevant assets, with separate
attribution for NASA measurements and synthetic telemetry. The demo MP4 is a
rendered software simulation with AI-assisted preparation. Its disclosure should
describe that actual use. SI-generated content must not use, contain or modify
NASA branding or design elements, as stated in the supplied form.

## NASA Data

Enter each row as a separate resource. The first two are the NASA elevation
datasets used by LAB; the other three credit NASA background material used in
the presentations.

| Link Text | Link Url |
| --- | --- |
| NASA MRO HiRISE — Gale crater DTM DTEEC_001488_1750_001752_1750_U02 | https://www.uahirise.org/dtm/dtm.php?ID=PSP_001488_1750 |
| NASA MGS MOLA — MEGDR elevation data, product MEGT00N000GB.IMG | https://pds-geosciences.wustl.edu/missions/mgs/megdr.html |
| NASA/JPL — Spirit's View from Troy | https://science.nasa.gov/photojournal/spirits-view-from-troy/ |
| NASA — Speaking Percy's Language: Mars communication delay | https://science.nasa.gov/blog/speaking-percys-language-how-to-talk-so-perseverance-will-listen/ |
| NASA/JPL — Perseverance autonomous navigation background | https://www.nasa.gov/missions/mars-2020-perseverance/perseverance-rover/nasas-self-driving-perseverance-mars-rover-takes-the-wheel/ |

Dataset files, source coordinates and sampling details are documented at:
https://github.com/Team-Arescope/arescope/blob/main/services/arescope-lab/static/docs/terrain-sources.md

## Space Agency Partner & Other Data

Enter each row as a separate resource. These credits cover development tools,
dependencies, design resources and prototype work, including historical use
where labelled. Retain the bundled licence and attribution notices for reused
code, icons, fonts and other assets.

| Link Text | Link Url |
| --- | --- |
| Python | https://www.python.org/ |
| FastAPI | https://github.com/fastapi/fastapi |
| Uvicorn | https://github.com/encode/uvicorn |
| HTTPX | https://github.com/encode/httpx |
| python-dotenv | https://github.com/theskumar/python-dotenv |
| SQLite | https://www.sqlite.org/ |
| Unity — Quest sensor-mast prototype | https://unity.com/ |
| Meta XR SDK — Quest development | https://developers.meta.com/horizon/ |
| OpenXR | https://www.khronos.org/openxr/ |
| QuestRoomScan — reconstruction dependency, pinned source | https://github.com/arghyasur1991/QuestRoomScan/tree/4791b24b81015641d4cfb010a93c6283d4eb3dee |
| Lucide icons — ISC licence | https://lucide.dev/license |
| Tabler icons — MIT licence, Quest HUD | https://github.com/tabler/tabler-icons |
| Manrope font — SIL Open Font License | https://github.com/googlefonts/manrope |
| DM Mono font — SIL Open Font License | https://github.com/googlefonts/dm-mono |
| Marcellus font — original archived presentation | https://fonts.google.com/specimen/Marcellus |
| Quicksand font — original archived presentation | https://fonts.google.com/specimen/Quicksand |
| unslop — UI methodology by Damir Sokolovsky, CC BY 4.0 | https://github.com/heydamir/unslop |
| Poly Haven — CC0 resources in historical simulator preparation | https://polyhaven.com/ |
| Playwright — browser testing and screen capture | https://github.com/microsoft/playwright |
| pytest — automated tests | https://github.com/pytest-dev/pytest |
| FFmpeg — demo encoding | https://ffmpeg.org/ |
| OpenAI Codex — AI-assisted development | https://openai.com/codex/ |
| OmniRoute — server-side AI routing | https://github.com/cheaper-inference/OmniRoute |
| InstaBox — cloud development environment | https://instabox.sh/ |

## Project Submission Verification

The form supplies two final confirmation checkboxes, with no free-text field:

- Agree to Terms and Conditions
- Confirm All Work is Original

The submitting participant completes these confirmations after reviewing the
linked requirements and the team's original work and external-resource credits.
