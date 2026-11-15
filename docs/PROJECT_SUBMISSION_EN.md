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

https://github.com/Team-Arescope/arescope/blob/main/presentation/Arescope-V2-Deck.pdf

The form permits one demonstration link: a video of at most 30 seconds or a deck
of at most seven slides, including the title and introduction. The PDF above is
the seven-slide form option. The separate pitch with embedded video uses eight
slides within a ten-slide budget; that pitch exceeds the form's seven-slide
limit. The 30-second MP4 is the recommended form submission.

## Project

https://arescope.mrfenek.eu.cc

Submission note: use the public LAB URL above for this field. The source code
and technical evidence are also public and are linked in Project Details:

https://github.com/Team-Arescope/arescope

## Project Details

Arescope is a prototype for resilient Mars rover teamwork. A rover can lose useful camera detail, struggle to move or become disconnected while Earth cannot respond immediately. We explore how local risk detection, coordination at an uncrewed Mars home base and human oversight on Earth could help a fleet continue its mission.

The intended system has three levels. First, Guardian is the planned onboard risk monitor for each rover. Second, a home base on Mars is the core local coordination layer: a planned physical hub that maintains the fleet's shared map, allocates survey work, coordinates incident handling and relays data to Earth. Third, Earth Mission Control provides mission oversight, reviews serious incidents and approves learning updates.

The working product today is Arescope LAB, a public browser application that simulates fleet coordination. It places one to six simulated rovers on archived NASA terrain and shows positions, survey trails, coverage, warnings and events. Users can change simulation speed and inject faults. Guardian currently evaluates simulated telemetry in LAB, including sensing quality, connectivity and commanded versus observed movement. For minor simulated faults, a healthy neighbour can approach and run a timed recovery procedure. Serious faults require an operator decision. A halted rover resumes only after fresh nominal Guardian observations.

LAB records incidents and operator labels, trains a candidate model and validates it before human-approved activation. This is a reviewed learning workflow, without a guarantee that AI can diagnose or correct every failure. Mission rules and route search coordinate simulated movement.

NASA's HiRISE DTM DTEEC_001488_1750_001752_1750_U02 supplies a Gale crater terrain strip of approximately 40 square kilometres; MOLA MEGDR provides regional elevation context. Archived measurements remain separate from simulated routes and telemetry. Orbital terrain does not resolve wheel-scale obstacles.

LAB uses Python, FastAPI, SQLite, WebSockets, JavaScript, WebGL, HTML and CSS. A separate Unity/C# and OpenXR prototype targets Meta Quest 3S as a future sensor testbed; runtime verification remains outstanding. An optional Voice Copilot prototype explores telemetry-aware language models through OmniRoute.

Our contribution connects shared terrain awareness, risk monitoring, assistance, operator decisions and reviewed learning. Current evidence comes from software simulation: there is no physical Mars home base or tested onboard Guardian deployment. Terrestrial rover testing is the next milestone, with potential benefits for remote exploration and field robotics. AI tools assisted development and presentation preparation; the team reviews and tests their outputs.

Our longer-term vision connects future astronauts, rovers and the Mars home base through a common map and data exchange network, unifying surface operations toward a Mars surface "internet". The required communication protocols and physical infrastructure remain future work; current LAB demonstrates rover coordination in software.

Public LAB: https://arescope.mrfenek.eu.cc

Source code and technical evidence: https://github.com/Team-Arescope/arescope

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
