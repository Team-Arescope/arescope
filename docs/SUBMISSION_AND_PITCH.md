# ARESCOPE · Hackathon Submission, 3-Minute Live Demo & Judge Q&A

Prepared: 14 November 2026. Scope: **V2 Rover + Two-Loop Arescope Guardian**. The submission fields below have independent English and Russian variants. Choose one language for the form. Stage directions are separate from spoken copy.

**Evidence boundary:** this is an Earth prototype using a Quest 3S sensor-mast testbed and a rover simulator on archived NASA terrain. Guardian's reported performance comes from **synthetic hold-out validation**, not Mars telemetry, a Spirit reconstruction, rover chassis trials, or flight validation. The intended Fast Loop runs onboard; the current Quest client sends frames to LAB and receives Guardian results. Recovery outputs are recommendations, not demonstrated autonomous vehicle maneuvers.

## 1. Ready-to-paste hackathon submission fields

### 1A. English variant

#### Project title

ARESCOPE

#### One-line tagline

ARESCOPE · One perception and failure-protection module for Mars rovers

#### High-level summary

Arescope combines local 3D perception with early warnings for rover tracking and traction failures. Spirit's wheels began sinking at Troy on April 23, 2009; with a 3–22 minute one-way Earth–Mars signal delay, timely protection must be local. Our V2 prototype pairs a Quest 3S rover sensor-mast testbed with a HiRISE terrain simulator and Two-Loop Arescope Guardian: a Fast Loop for risk warnings and recovery guidance, and an Earth-based Slow Loop for incident labeling, retraining, validation, and human-approved model deployment. A Mission Control Voice Copilot helps operators interpret supplied telemetry. Validation is synthetic; there is no flight validation.

#### Detailed project description

Spirit's loss of mobility at Troy motivates a practical question: how can a rover recognize degrading perception or traction before Earth can respond? NASA records the start of wheel sinking on April 23, 2009. Arescope uses this historical case to explain the need; it does not claim to detect hidden soil strength or prove that it would have saved Spirit. Earth–Mars radio propagation takes 3–22 minutes one way, so operators cannot close a seconds-scale protection loop from Earth. [NASA/JPL: Spirit at Troy](https://science.nasa.gov/photojournal/spirits-view-from-troy/), [NASA: Mars communication delay](https://science.nasa.gov/blog/speaking-percys-language-how-to-talk-so-perseverance-will-listen/).

Arescope's proposed rover module combines a local 3D surface map with Guardian's risk assessment. Today, Quest 3S serves as an Earth-based sensor-mast testbed for local capture, tracking, compute, and operator feedback. It is a convenient prototype platform, not flight hardware or an astronaut use case. A software rover traverses an archived MRO HiRISE elevation grid in Gale crater and injects controlled optical, traction, and sensor/link degradation. Arescope LAB provides Mission Control with local scans, incident history, and HiRISE/MOLA terrain context. The Gale simulation is not a reconstruction of Spirit's Troy site.

Guardian has two timescales. The **Fast Loop** converts the latest five telemetry samples into compact features, predicts a cause and risk level, marks low-confidence data, and recommends a recovery action. Its onboard deployment design avoids dependence on Earth; the current demonstration evaluates Guardian in LAB and returns results to the Quest client. The **Slow Loop** runs on Earth: operators verify incident labels, retrain a candidate, compare separate hold-out results, and explicitly approve deployment. A candidate never replaces the active model through retraining alone.

The **Mission Control Voice Copilot** uses OmniRoute for speech recognition, streamed language-model assistance, and speech synthesis. It explains only the mission context supplied to it. It assists operators and field engineers; it neither supplies independent telemetry nor controls rover safety decisions or model approval.

On a synthetic hold-out of 36 trajectories and 1,152 windows, adaptation improves caught failures from 26/30 to 30/30 and macro F1 from 89.5% to 98.6%. The adapted model gives 14.8 seconds mean warning lead time and 11 false alarms on nominal windows; micro-slip recall rises from 0.0% to 95.4% after 192 reviewed synthetic adaptation windows. These demonstrate the prototype workflow, not general Mars reliability. Rover integration, environmental testing, and field validation remain next steps.

#### Realistic Mars failure modes

| Failure mode | What the prototype represents | Guardian cause |
| --- | --- | --- |
| Dust on optics / partial occlusion | Falling contrast and useful surface-point count | `dust` |
| Glare and deep shadow | Lighting-related loss of usable visual features; the deterministic fault replay exercises glare | `glare` |
| Low-texture sand | Too few stable landmarks for reliable tracking | `low_texture` |
| Wheel slip in soft soil | Observed motion falls behind commanded motion, including an emerging micro-slip pattern | `wheel_slip` |
| Sensor and link dropouts | Missing/degraded frames, falling frame rate, pose jumps, and link loss | `sensor_drop` |

Mars wind can transport dust and change visibility, but its thin atmosphere does not justify claims that ordinary gusts overturn a rover. Our scenarios concern optical contamination, lighting, feature scarcity, traction, and missing measurements. They are controlled degradations, not a validated atmospheric or soil-mechanics simulation. [NASA: The Fact and Fiction of Martian Dust Storms](https://www.nasa.gov/solar-system/the-fact-and-fiction-of-martian-dust-storms/).

#### Exact verified results — synthetic hold-out validation

**All results below use the same frozen synthetic hold-out: 36 trajectories, 1,152 evaluated five-sample windows. No flight validation.** The 36 trajectories comprise six nominal runs and 30 fault runs, six for each of five causes.

| Metric | Baseline v1 | Adapted candidate v2 |
| --- | --- | --- |
| Correctly attributed warnings before simulated failure | **26/30** failures | **30/30** failures |
| Macro F1 across six classes, including nominal | **89.5%** | **98.6%** |
| Micro-slip recall on relevant hold-out windows | **0.0%** | **95.4%** |
| Mean measured warning lead time, over caught failure trajectories | 14.9 s | **14.8 s** |
| False alarms on nominal-labeled windows | 10 / 492 | **11 / 492** |
| Nominal-window false-alarm rate | 2.03% | 2.24% |

Adaptation adds **192 reviewed adaptation windows** from a separate synthetic split. In the reproducible evaluation, these are review fixtures with simulator-derived labels representing operator review; they are not 192 real rover incidents or a completed human annotation study. Training, adaptation, and hold-out use distinct seeds and non-overlapping terrain corridors. Hold-out labels and failure times are used for evaluation, not as training examples.

A caught failure requires the correct cause and a non-nominal warning before the simulator's scheduled failure time. The **14.8 s** result is failure time minus first correct warning, averaged over the adapted model's 30 caught trajectories. It is not a guaranteed warning horizon or the live `leadTimeS` extrapolation. The **11** false alarms are overlapping nominal windows, not 11 independent incidents or 11 failed missions. F1 is a class-averaged score, not a percent of missions saved. The adaptation trades one additional false-alarm window for four additional caught failure trajectories.

#### NASA data used

We use archived NASA elevation products for **terrain and slope context**, not measured optical failures, wheel-slip labels, live Mars imagery, or safety ground truth.

| Data | Exact project use and resolution boundary |
| --- | --- |
| **MRO HiRISE DTM**, Gale crater, product `DTEEC_001488_1750_001752_1750_U02`; dataset `MRO-M-HIRISE-5-DTM-V1.0` | **129×129 display/simulation grid at approximately 8.09 m spacing**, sampled at stride 8 from a source with **1.0117 m native spacing**. The display does not preserve native detail or resolve wheel-scale sand traps. [HiRISE product catalog](https://www.uahirise.org/dtm/dtm.php?ID=PSP_001488_1750). |
| **MGS MOLA MEGDR**, product `MEGT90N000FB.IMG`; legacy dataset identifier `MGS-M-MOLA-5-MEGDR-L3-V1.0` | **65×65 regional grid at approximately 1.85 km spacing** for broad elevation context in Mission Control. Grid spacing is not effective resolving power; MOLA is not a wheel-scale navigation surface. [NASA PDS MOLA archive](https://pds-geosciences.wustl.edu/missions/mgs/megdr.html). |

Local Quest captures are Earth measurements. Simulator optics/chassis telemetry, fault onset, failure times, and labels are synthetic. Keeping these sources distinct makes the demonstration reproducible without overstating NASA validation.

#### AI use disclosure

We used AI coding and verification agents to assist implementation, test drafting, code review, and checks, and AI assistance for pitch/document drafting. People review the resulting code, evidence, and claims; agent output is not independent certification.

The operator Voice Copilot uses an **OmniRoute ASR → streamed LLM → TTS pipeline**. It receives an explicit context containing available Guardian outputs and telemetry, and is instructed to acknowledge missing data rather than invent readings or completed actions. The current service uses a Russian operator prompt. Its explanations are assistance, not verified sensor evidence or authorization to deploy a model.

Guardian is a **small supervised nearest-prototype classifier** (`nearest-prototype-v1`), using deterministic class-wise k-means compression of labeled telemetry windows. It is not an LLM. The baseline deliberately omits an emerging soft-sand micro-slip pattern; adaptation uses separately reviewed synthetic examples. A validated candidate requires explicit human approval before activation. Neither Guardian nor the Copilot autonomously rewrites and deploys the active model.

#### Impact, current maturity, and next steps

The intended benefit is earlier awareness of tracking and traction degradation, with a clear recovery recommendation and an auditable operator review process. Today we demonstrate an Earth mast testbed, controlled terrain/fault replay, and Guardian's label–retrain–validate–approve workflow. Next are rover chassis integration, measured compute/power budgets, controlled sensor and soft-ground trials, and independent field validation. Terrestrial analog, search-and-rescue (SAR), and geology robots are plausible trial platforms; no operational deployment, quantified mission savings, or field safety certification is claimed.

#### Links

- Source repository: [Team Arescope / arescope](https://github.com/Team-Arescope/arescope)
- Project and demo entry point: [Arescope](https://arescope.mrfenek.eu.cc)

### 1B. Русский вариант

#### Название проекта

ARESCOPE

#### Однострочный слоган

ARESCOPE · Единый модуль восприятия и защиты от сбоев для марсоходов

Английский оригинал для формы с фиксированным слоганом: ARESCOPE · One perception and failure-protection module for Mars rovers

#### Краткое описание

Arescope объединяет локальную 3D-карту с ранним предупреждением о потере трекинга и пробуксовке марсохода. Колёса Spirit начали проваливаться в грунт в районе Troy 23 апреля 2009 года. При задержке сигнала Земля–Марс 3–22 минуты в одну сторону своевременная защита должна работать локально. Прототип V2 сочетает Quest 3S как стенд сенсорной мачты ровера, симулятор на рельефе HiRISE и двухконтурный Arescope Guardian: быстрые предупреждения и рекомендации восстановления, затем наземную разметку, дообучение, валидацию и подтверждённое человеком применение модели. Голосовой Mission Control Copilot объясняет оператору переданную телеметрию. Валидация синтетическая; лётной валидации нет.

#### Подробное описание проекта

История Spirit в Troy ставит практический вопрос: как заметить ухудшение восприятия или сцепления до того, как Земля успеет ответить? NASA датирует начало погружения колёс 23 апреля 2009 года. Это мотивация проекта, а не доказательство, что Arescope видит скрытую прочность грунта или спас бы Spirit. Радиосигнал между Землёй и Марсом идёт 3–22 минуты в одну сторону, поэтому защитный контур с реакцией за секунды нельзя замыкать через земного оператора. [NASA/JPL: Spirit в Troy](https://science.nasa.gov/photojournal/spirits-view-from-troy/), [NASA: задержка связи с Марсом](https://science.nasa.gov/blog/speaking-percys-language-how-to-talk-so-perseverance-will-listen/).

Предлагаемый модуль ровера объединяет локальную 3D-карту поверхности и оценку риска Guardian. Сегодня Quest 3S — наземный стенд сенсорной мачты для съёмки, трекинга, вычислений и вывода информации оператору. Это доступная платформа прототипа, а не лётная аппаратура или сценарий для астронавтов. Программный ровер движется по архивной сетке высот MRO HiRISE кратера Гейла; оператор вводит контролируемые помехи оптики, пробуксовку и деградацию датчиков/связи. Arescope LAB объединяет локальные сканы, историю инцидентов и контекст HiRISE/MOLA в Mission Control. Симуляция в Гейле не является реконструкцией Troy.

У Guardian два контура. **Fast Loop** извлекает компактные признаки из пяти последних отсчётов телеметрии, определяет предполагаемую причину и уровень риска, помечает данные с низкой уверенностью и рекомендует восстановление. По архитектуре этот контур должен работать на борту без ожидания Земли; в текущем демо Guardian исполняется в LAB, а Quest получает результат от сервера. **Slow Loop** работает на Земле: оператор проверяет причины инцидентов, обучает кандидата, сравнивает результаты на отдельной hold-out выборке и явно подтверждает применение. Одно дообучение не заменяет активную модель.

**Mission Control Voice Copilot** использует OmniRoute для распознавания речи, потокового ответа языковой модели и синтеза речи. Он объясняет только явно переданный контекст. Это помощник оператора и полевого инженера, без независимого доступа к телеметрии и полномочий управлять защитой ровера или одобрять модель.

На синтетическом hold-out из 36 траекторий и 1 152 окон адаптация увеличивает число обнаруженных сбоев с 26/30 до 30/30, а macro F1 — с 89,5% до 98,6%. У адаптированной модели среднее опережение — 14,8 с и 11 ложных тревог на номинальных окнах; полнота обнаружения микропробуксовки растёт с 0,0% до 95,4% после 192 проверенных синтетических окон адаптации. Это результат прототипа, а не доказанная надёжность на Марсе. Интеграция с шасси, испытания среды и полевая валидация — следующие шаги.

#### Реалистичные причины сбоев на Марсе

| Причина | Что моделируется | Класс Guardian |
| --- | --- | --- |
| Пыль на оптике / частичное перекрытие | Падение контраста и числа полезных точек поверхности | `dust` |
| Блики и глубокие тени | Потеря визуальных признаков из-за освещения; в детерминированном прогоне реализована засветка | `glare` |
| Однообразный песок | Недостаток устойчивых ориентиров для трекинга | `low_texture` |
| Пробуксовка в мягком грунте | Реальное перемещение отстаёт от заданного, включая новый паттерн микропробуксовки | `wheel_slip` |
| Пропуски датчика и связи | Потеря кадров, снижение частоты, скачки позы и потеря канала | `sensor_drop` |

Ветер переносит пыль и меняет видимость, но разреженная атмосфера Марса не даёт оснований утверждать, что обычные порывы опрокидывают ровер. Мы моделируем загрязнение оптики, освещение, нехватку ориентиров, сцепление и пропуски измерений. Это управляемые деградации, а не проверенная модель атмосферы или механики грунта. [NASA: реальные свойства марсианских пылевых бурь](https://www.nasa.gov/solar-system/the-fact-and-fiction-of-martian-dust-storms/).

#### Точные проверенные результаты — синтетическая hold-out валидация

**Все числа получены на одной фиксированной синтетической hold-out выборке: 36 траекторий, 1 152 окна по пять отсчётов. Лётной валидации нет.** Это шесть номинальных траекторий и 30 траекторий со сбоями: по шесть на каждую из пяти причин.

| Метрика | Базовая модель v1 | Адаптированный кандидат v2 |
| --- | --- | --- |
| Предупреждения с верной причиной до модельного отказа | **26/30** сбоев | **30/30** сбоев |
| Macro F1 по шести классам, включая норму | **89,5%** | **98,6%** |
| Полнота обнаружения микропробуксовки на соответствующих hold-out окнах | **0,0%** | **95,4%** |
| Среднее измеренное опережение по обнаруженным траекториям со сбоем | 14,9 с | **14,8 с** |
| Ложные тревоги на окнах с номинальной меткой | 10 / 492 | **11 / 492** |
| Доля ложных тревог на номинальных окнах | 2,03% | 2,24% |

Для адаптации добавлены **192 проверенных окна** из отдельной синтетической выборки. В воспроизводимом эксперименте это фикстуры проверки с метками из симулятора, представляющие работу оператора; это не 192 реальных инцидента и не проведённое исследование ручной разметки. Обучение, адаптация и hold-out используют разные seeds и непересекающиеся коридоры рельефа. Метки и времена отказов hold-out используются для оценки, а не для обучения.

Сбой засчитывается как обнаруженный, если предупреждение с верной причиной появилось до заданного симулятором времени отказа. **14,8 с** — разность между этим временем и первым верным предупреждением, усреднённая по 30 обнаруженным траекториям адаптированной модели; это не гарантия и не текущий прогноз `leadTimeS`. **11** — число пересекающихся номинальных окон с тревогой, а не независимых инцидентов или потерянных миссий. F1 усреднён по классам и не означает долю спасённых миссий. Цена четырёх дополнительно обнаруженных сбоев — одно дополнительное окно ложной тревоги.

#### Использованные данные NASA

Архивные высотные продукты NASA дают **рельеф и контекст уклонов**, но не измеренные сбои оптики, метки пробуксовки, прямой эфир с Марса или эталон безопасности.

| Данные | Применение и границы разрешения |
| --- | --- |
| **MRO HiRISE DTM**, кратер Гейла, продукт `DTEEC_001488_1750_001752_1750_U02`, набор `MRO-M-HIRISE-5-DTM-V1.0` | **Сетка отображения/симуляции 129×129 с шагом около 8,09 м**, выборка каждой восьмой точки источника с **исходным шагом 1,0117 м**. Отображение не сохраняет исходную детализацию и не разрешает песчаные ловушки масштаба колеса. [Каталог HiRISE](https://www.uahirise.org/dtm/dtm.php?ID=PSP_001488_1750). |
| **MGS MOLA MEGDR**, продукт `MEGT90N000FB.IMG`, прежний идентификатор набора `MGS-M-MOLA-5-MEGDR-L3-V1.0` | **Региональная сетка 65×65 с шагом около 1,85 км** для общего высотного контекста Mission Control. Шаг сетки не равен эффективной разрешающей способности; MOLA не подходит для навигации на масштабе колёс. [Архив NASA PDS MOLA](https://pds-geosciences.wustl.edu/missions/mgs/megdr.html). |

Локальные сканы Quest — земные измерения. Телеметрия оптики/шасси симулятора, начало помех, времена отказов и метки — синтетические. Эти источники различаются явно, чтобы не приписывать NASA проверку нашего классификатора.

#### Раскрытие использования AI

AI-агенты помогали писать код и тесты, проводить ревью и проверки; AI также использовался при подготовке текста питча и документации. Люди проверяют код, доказательства и заявления. Вывод агента не является независимой сертификацией.

Голосовой Copilot оператора использует цепочку **OmniRoute ASR → потоковый LLM → TTS**. В него явно передаются доступные результаты Guardian и телеметрия; при нехватке данных он должен сообщать об этом, а не придумывать показания или выполненные действия. Текущий сервис настроен на русскоязычного оператора. Его объяснение не является показанием датчика или разрешением применить модель.

Guardian — **небольшой обучаемый с учителем классификатор ближайшего прототипа** (`nearest-prototype-v1`) с детерминированным k-means сжатием размеченных окон отдельно по классам. Это не LLM. Базовое обучение намеренно не содержит нового паттерна микропробуксовки; адаптация использует отдельно проверенные синтетические примеры. Применение прошедшего валидацию кандидата требует явного решения человека. Ни Guardian, ни Copilot самостоятельно не переписывают и не развёртывают активную модель.

#### Эффект, зрелость и следующие шаги

Ожидаемая польза — раньше замечать ухудшение трекинга и сцепления, получать понятную рекомендацию восстановления и сохранять проверяемую историю решений оператора. Сегодня показаны наземный стенд мачты, управляемый прогон рельефа/помех и цикл «разметить — обучить — проверить — одобрить». Далее нужны интеграция с шасси, измерения вычислений и энергопотребления, контролируемые испытания датчиков и мягкого грунта, независимая полевая валидация. Земные аналоговые испытания, поисково-спасательные и геологические роботы — возможные площадки проверки. Внедрение в реальную службу, измеренная экономия миссии и сертификация безопасности не заявляются.

#### Ссылки

- Исходный код: [Team Arescope / arescope](https://github.com/Team-Arescope/arescope)
- Проект и вход в демо: [Arescope](https://arescope.mrfenek.eu.cc)

## 2. Minute-by-minute 3-minute live demo and fallback script

### Rehearsal setup — outside the three-minute clock

This is a runbook, not a claim that services, recordings, or hardware have already been checked for this presentation. The presenter speaks; a second operator handles the clicks. Use the English spoken track below, with one short Russian Copilot exchange because the current service prompt is Russian. Do not read stage directions aloud.

1. Open the presentation and [Arescope LAB](https://arescope.mrfenek.eu.cc). Confirm the HiRISE view, Guardian panel, moving nominal rover stream, and fresh timestamps. Connect the viewer and prepare operator access before screen sharing. Keep credentials out of the projected view. Distinguish the simulated rover from the Quest `mast-testbed` carrier.
2. Rehearse **Dust** as the short live fault: start with a warmed-up five-sample window, inject the fault, and verify that its warning arrives within the allotted 22 seconds. **Wheel slip** is the alternative if already rehearsed. Use the stream's actual risk, cause, model version, and action; do not promise a specific live lead time.
3. Prepare the Slow Loop review state. For the exact benchmark, the review fixture contains 192 separate synthetic adaptation windows; leave one representative fault window awaiting its final correct label and the other 191 labeled, with v1 active. Show that last review live, then retrain and inspect the resulting candidate before approval. Keep newly injected live incidents pending for this controlled benchmark. This requires rehearsal preparation; it is not a claim that the UI imports this fixture automatically. If that state is unavailable, demonstrate the genuine current review workflow and identify the published metrics as the separate reproducible benchmark. One newly labeled incident does not explain the published improvement.
4. Keep a real recording of the complete label → retrain → hold-out review → human approval sequence ready if live training is too slow. Verify the saved material before stage use; this document creates no recording. If none exists, use the presentation's pipeline diagram and explain the workflow without pretending to execute it.
5. Have Quest 3S charged, scanning a nearby surface, and ready to cast, or queue a verified recording of an actual mast-testbed session. Show room geometry and the carrier identity. A brief partial occlusion or low-texture view may illustrate degraded perception if rehearsed. Do not promise that a particular physical perturbation will reproduce a synthetic benchmark result.
6. Test the full **microphone → ASR → LLM stream → TTS** exchange, not just a health endpoint. Supply a recent, timestamped Guardian/telemetry snapshot as explicit Copilot context, including the actual cause, risk, recovery action, and whether the source is simulation or Quest. The Copilot does not fetch this context independently. Rehearse a typed query as the microphone fallback and prepare a verified prior response only if one actually exists.
7. Put the exact metrics on the evidence slide: 36 trajectories / 1,152 windows; 26/30 → 30/30; 14.8 s after adaptation; 11 false-alarm windows; F1 89.5% → 98.6%; micro-slip recall 0.0% → 95.4% after 192 adaptation windows; **synthetic, no flight validation**. A current demo candidate may differ if trained on different labels.

**Timing rule:** switch to fallback after five seconds without useful progress. The operator may finish an action while the presenter continues speaking. Reach Minute 3 at 2:00 regardless of service state, and stop at 3:00. Do not wait through backend timeout limits onstage.

### Minute 1 · 0:00–1:00 — problem, Spirit, and architecture

| Time | Presenter — spoken English | Operator / visible evidence |
| --- | --- | --- |
| **0:00–0:15** | “Arescope: one perception and failure-protection module for Mars rovers. We combine a local surface map with early warnings when visual tracking or traction starts to degrade.” | Show the title slide and exact tagline. |
| **0:15–0:35** | “In April 2009, Spirit began sinking at Troy. A surface can look safe while traction deteriorates. With a three-to-twenty-two-minute one-way signal delay, a rover cannot wait for Earth to handle a seconds-scale hazard.” | Show the Spirit slide. If toggling its scan overlay, keep its illustrative label visible. Historical references are the NASA links in §1. |
| **0:35–1:00** | “We target dust on optics, glare and deep shadow, featureless sand, wheel slip, and sensor or link drops. Guardian has two loops: rapid risk assessment designed for the rover, and supervised learning on Earth. Today's demonstration uses LAB, a HiRISE simulator, and a Quest mast testbed.” | Briefly show the two-loop pipeline, then switch to the prepared nominal LAB stream. |

### Minute 2 · 1:00–2:00 — live rover, Fast Loop, Slow Loop, Quest mast

| Time | Presenter — spoken English | Operator / visible evidence |
| --- | --- | --- |
| **1:00–1:22** | “This rover is simulated on NASA HiRISE terrain. I inject dust now. Watch the useful points degrade, Guardian identify the risk, mark low confidence, and recommend checking the optical sensor. Here inference runs in LAB; onboard inference is the deployment design.” | In Guardian, use **Start** if needed, then **Dust**. Point to the actual risk level, predicted cause, low-confidence flag, and recovery recommendation. The injected telemetry is synthetic. If the actual output differs, describe it honestly or switch to the fallback. |
| **1:22–1:44** | “On Earth, an operator verifies the incident's cause. We retrain from reviewed windows and inspect independent hold-out results. The active version stays unchanged until a human explicitly approves this validated candidate. This is supervised adaptation, not autonomous model drift.” | Select the known cause and **Save label** on the prepared review window; click **Retrain & validate**. Show active/candidate versions and before/after metrics; review the gate, then deliberately click **Approve & deploy**. Point to the changed active version. If the candidate fails validation, say so and leave it unapplied. |
| **1:44–2:00** | “Quest 3S stands in for a rover sensor mast. This is local room geometry from our Earth testbed, separate from the simulated Mars surface. The headset lets us exercise capture, tracking, and operator feedback before integrating a rover chassis.” | Show the live Quest cast and its `mast-testbed` stream. If unavailable, play a verified actual capture labeled **Recorded Quest mast testbed**. A physical camera perturbation is optional; preserve the time limit. |

If **Wheel slip** replaces Dust, replace the first spoken row with: “This rover is simulated on NASA HiRISE terrain. I inject wheel slip now. Commanded and observed motion diverge; Guardian warns and recommends reducing speed, stopping, and rerouting. The telemetry is synthetic; here inference runs in LAB, with onboard inference the deployment design.”

### Minute 3 · 2:00–3:00 — live operator Copilot, evidence, impact

| Time | Presenter — spoken copy | Operator / visible evidence |
| --- | --- | --- |
| **2:00–2:25** | “Our Voice Copilot explains supplied telemetry to Mission Control.” Ask aloud in Russian: **«Что означает предупреждение Guardian и что проверить оператору?»** Let the actual short response play. Then: “It assists the operator; human approval remains separate.” | Pass the fresh displayed fault context, run microphone → ASR → streamed answer → TTS, and keep the transcript visible. The response should explain the actual cause and relevant check. Do not read a scripted answer as though the service generated it. |
| **2:25–2:48** | “On thirty-six synthetic hold-out trajectories, eleven hundred fifty-two windows, caught failures rise from twenty-six of thirty to thirty of thirty. F1 rises from eighty-nine point five to ninety-eight point six percent. The adapted model gives fourteen point eight seconds' mean warning and eleven false-alarm windows. No flight validation.” | Show the evidence slide or verified benchmark panel. Keep the separate micro-slip result visible: **0.0% → 95.4% after 192 reviewed adaptation windows**. If the live candidate differs, identify this as the controlled benchmark. |
| **2:48–3:00** | “Next: rover chassis trials, then terrestrial analog and search-and-rescue robots. We aim for earlier risk awareness with accountable human review. The code and demo are linked here.” | Show both project links. End at 3:00. |

**Copilot answer boundary:** for a supplied dust warning, an acceptable response would explain the reported optical degradation and recommend stopping to check the sensor. For wheel slip, it should recommend reducing speed, stopping, and verifying a different route. These are response criteria, not a promised transcript. It must not invent a speed, risk score, failure time, successful recovery, or approved deployment. If context is absent or stale, demonstrate its limitation instead of prompting for invented telemetry.

### Exact fallback lines — keep the same three-minute structure

| Failure / time slot | Switch to | Say this verbatim |
| --- | --- | --- |
| LAB, network, or rover stream unavailable during Minute 2 | A verified recorded run; if absent, the slide 5 pipeline/link-state interaction | “The live service is unavailable. This is a recorded prototype run.” **Or, for the slide:** “This is an architecture diagram, not live telemetry. It illustrates the intended local protection loop while Earth review waits.” |
| No warning or unexpected classification after fault injection | The actual result, then a verified prior fault replay or slide 6 evidence | “This run has not produced the expected warning. The figures shown here come from the separate reproducible synthetic benchmark.” |
| Retraining exceeds five seconds, or the candidate fails the gate | Verified Slow Loop recording, or pipeline diagram plus benchmark evidence | “This candidate is not ready to apply. Deployment requires validated results and explicit human approval. I will show the recorded workflow.” **Without a recording:** “This diagram shows the review workflow; no deployment is being performed here.” |
| Quest casting or live capture fails | Verified Quest video; otherwise the hardware/testbed slide | “This is a recording of our Quest sensor-mast testbed on Earth.” **Without a recording:** “The Quest testbed is not live in this demonstration; this slide shows its role.” |
| Microphone/ASR fails at 2:00 | Submit the same query as text with the actual context | “I will type the same operator question and use the available text and speech output.” |
| TTS fails but a genuine text answer arrives | Display the actual streamed answer and read it | “Speech output is unavailable; this is the Copilot's actual text response.” |
| LLM/router unavailable, or no useful response within five seconds | Verified prior response with its saved context; otherwise show Guardian's own recommendation | “The voice service is unavailable. This is a recorded response using the context shown.” **Without a recording:** “Here is Guardian's recovery recommendation; I am explaining it myself.” |
| Asked to demonstrate a link interruption | Slide 5 **Link interrupted**, then **Link available** | “This diagram illustrates the onboard design. It is not a test proving that the current Quest-to-LAB inference path survives a disconnected LAB link.” |

Never call a replay live, a diagram a measurement, a pending candidate deployed, or a server reply autonomous onboard protection. If fallback begins early, use the saved time to explain the actual evidence; do not extend the closing.

### Russian delivery substitutions

Use these as an alternative spoken track with the same click schedule, not extra narration added to the English track. Keep the actual Copilot response short and switch to fallback on the same five-second rule.

- **0:00–1:00:** «Arescope — единый модуль восприятия и защиты от сбоев для марсоходов. В апреле 2009 года Spirit начал проваливаться в грунт в Troy. При задержке сигнала 3–22 минуты в одну сторону нельзя ждать Землю для реакции за секунды. Мы отслеживаем пыль на оптике, блики и тени, нехватку ориентиров, пробуксовку и пропуски датчиков или связи. У Guardian два контура: быстрая оценка риска для борта и проверяемое человеком обучение на Земле. Сегодня показываем наземный прототип».
- **1:00–1:22:** «Ровер движется по рельефу NASA HiRISE, телеметрия синтетическая. Включаем пыль: полезные точки деградируют, Guardian определяет риск и рекомендует проверить оптику. Сейчас расчёт выполняется в LAB; бортовой Fast Loop — архитектура дальнейшего развёртывания».
- **1:22–1:44:** «Оператор проверяет причину инцидента. Дообучаем кандидата на размеченных окнах, сравниваем отдельный hold-out. Активная версия не меняется, пока человек явно не одобрит прошедшего проверку кандидата. Метрики относятся к подготовленной выборке адаптации, а не к одному новому инциденту».
- **1:44–2:00:** «Quest 3S — стенд сенсорной мачты ровера. Здесь локальная геометрия земного помещения, отдельно от симуляции Марса. Стенд позволяет проверить съёмку, трекинг и обратную связь до интеграции с шасси». При видео: «Это запись реального сеанса стенда».
- **2:00–2:25:** «Copilot помогает оператору объяснить переданные данные. Что означает предупреждение Guardian и что проверить оператору?» После фактического ответа: «Это помощь оператору; одобрение модели остаётся отдельным решением человека».
- **2:25–2:48:** «На синтетическом hold-out — 36 траекторий и 1 152 окна — обнаружение растёт с 26 из 30 до 30 из 30, F1 — с 89,5 до 98,6 процента. После адаптации среднее опережение 14,8 секунды и 11 окон ложных тревог. Лётной валидации нет».
- **2:48–3:00:** «Далее — испытания на шасси, земные аналоги и поисково-спасательные роботы. Наша цель — раньше замечать риск и сохранять проверяемое решение человека. Здесь код и демо».

## 3. Tough judge Q&A — short answers with evidence

Answer the question directly, then show the named evidence if requested. English is the main answer; the Russian line is a concise delivery alternative.

### Q1. “Mars has a thin atmosphere. Are your wind hazards exaggerated?”

**Answer:** We model dust degrading optics, lighting extremes, sparse visual features, traction loss, and missing measurements. We do not model ordinary wind gusts knocking a rover over. Dust transport can matter even when aerodynamic force is small. The injected faults are deliberately simplified, not a validated Mars weather model. [NASA's dust-storm explanation](https://www.nasa.gov/solar-system/the-fact-and-fiction-of-martian-dust-storms/) supports this distinction; `rover_sim.py: RoverSimulator.step` shows what is actually simulated.

**RU:** «Мы моделируем ухудшение оптики и трекинга, пробуксовку и пропуски данных. Опрокидывание ровера обычным марсианским ветром не заявляется; модель погоды не валидирована».

### Q2. “Is 3–22 minutes one way or round trip? Does your demo reproduce that delay?”

**Answer:** One way, depending on orbital geometry. A signal out and back therefore takes roughly 6–44 minutes before processing or scheduling. That motivates the intended onboard Fast Loop; the local demo does not emulate an actual deep-space communications channel or establish disconnected onboard operation. [NASA's communication explanation](https://science.nasa.gov/blog/speaking-percys-language-how-to-talk-so-perseverance-will-listen/). The prototype Quest path calls LAB for Guardian inference; the link-state slide is an architecture illustration.

**RU:** «3–22 минуты — в одну сторону; туда и обратно примерно 6–44 без обработки и расписания. Это обоснование бортового контура, а не измеренная задержка локального демо».

### Q3. “Why a Quest 3S? Are you putting a headset on a Mars rover?”

**Answer:** It is an available sensor-and-compute platform for an Earth mast testbed. We can exercise local 3D capture, tracking, stream integration, and operator feedback before building a dedicated rover module. It is neither a flight-qualified sensor nor proof of rover navigation accuracy. Current Unity code sends mast frames and receives LAB's Guardian response; rover hardware integration comes next. Evidence: the V2 plan's positioning, presentation hardware/testbed slide, and `LiveFrameSender.cs`.

**RU:** «Quest — доступный наземный стенд мачты для съёмки, трекинга и обмена с LAB. Это не лётный датчик и не доказательство точности навигации ровера».

### Q4. “Does the Slow Loop learn on its own and drift into an unsafe model?”

**Answer:** Retraining creates a candidate; it does not activate it. `GuardianEngine.candidate_ready` requires strictly higher F1, no fewer caught failures, no lower accuracy, and a nominal-window false-alarm rate no greater than `max(0.05, current rate)`. Deployment additionally requires literal `approved=True`. The API/UI preserves a separate review and approval step; a changed reviewed label invalidates a candidate trained on that label. This limits uncontrolled replacement; it is not a proof of safety under every new condition.

**RU:** «Дообучение создаёт только кандидата. Нужны улучшение F1, отсутствие ухудшения обнаружения и accuracy, допустимые ложные тревоги, затем явное одобрение человека. Изменённая обучающая метка отменяет соответствующего кандидата».

### Q5. “If false alarms increase from 10 to 11, how can the candidate pass?”

**Answer:** The gate is a rate ceiling, not a requirement that the count never increases. The adapted model has 11 alarms on 492 nominal windows, about 2.24%, below the current 5% ceiling. It catches four additional failure trajectories and improves macro F1, while its mean lead changes from 14.9 to 14.8 seconds. We report those tradeoffs rather than claiming every metric improves. A mission team would need an operationally justified threshold and false-stop cost model. Evidence: `guardian.py: candidate_ready` and the reproduced before/after evaluation.

**RU:** «Порог проверяет долю ложных тревог: 11/492 ≈ 2,24%, ниже текущих 5%. Четыре дополнительных обнаружения получены ценой одного окна ложной тревоги; опережение не улучшилось».

### Q6. “What is really NASA data, and what did you invent?”

**Answer:** NASA contributes archived HiRISE and MOLA elevations. Our HiRISE display is 129×129 at 8.09 m spacing, sampled from 1.0117 m native data; MOLA is a 65×65 regional grid at about 1.85 km. The simulator synthesizes optical/chassis telemetry, fault progression, and labels. Quest contributes Earth room captures. None of those synthetic faults are NASA-measured rover failures, and orbital grids do not reveal wheel-scale soil strength. Evidence: terrain JSON metadata, `rover_sim.py`, and §1's data provenance fields.

**RU:** «NASA даёт архивные высоты. Телеметрия и метки сбоев синтетические; Quest снимает земное помещение. Ни сетки, ни метрики не доказывают распознавание прочности грунта под колесом».

### Q7. “Did training leak into the hold-out? What exactly are the 192 windows?”

**Answer:** Training, adaptation, and hold-out are split by complete trajectories, seeds, and non-overlapping terrain corridors, not randomly mixed neighboring windows. The adaptation fixture uses 192 windows from six separate wheel-slip trajectories, including nominal transition windows and emerging micro-slip. Hold-out labels are used only for scoring. This controls direct leakage, but overlapping windows are correlated and all splits share a synthetic generator; fresh real-world validation is still needed. Repeated candidate selection on this hold-out also does not make it a final external certification set. Evidence: `generate_dataset`, `_base_samples`, `retrain`, and `tests/test_guardian.py: adaptation_incidents` and corridor checks.

**RU:** «Разделены целые траектории, seeds и коридоры рельефа. 192 окна — отдельная синтетическая адаптация, а не hold-out. Окна коррелируют и используют общий генератор; нужна независимая проверка на реальных данных».

### Q8. “You caught 30/30 failures. Why isn't F1 100%, and what does 14.8 seconds mean?”

**Answer:** They measure different units. A failure trajectory counts as caught after one correct-cause warning before its scheduled failure; other windows may still be misclassified. F1 is macro-averaged across six window classes, including nominal. The 14.8 seconds is mean scheduled failure time minus first correct warning across the adapted model's 30 caught trajectories. The live `leadTimeS` instead extrapolates a telemetry trend toward a limit; it is not that benchmark statistic. Neither number is a guaranteed physical stopping margin. Evidence: `_evaluate` versus `predict_model`.

**RU:** «30/30 — траектории с хотя бы одним своевременным предупреждением; F1 — классификация окон. 14,8 с измерены относительно модельного отказа, а текущий `leadTimeS` — экстраполяция тренда».

### Q9. “What is the onboard compute budget? Can a flight computer run it?”

**Answer:** The classifier uses five samples, six telemetry channels, and mean/minimum/trend features: 18 inputs. The baseline has at most eight prototypes per class; adaptation is bounded at 16 per class, at most 96 across six classes. The reproduced adapted candidate has 64 prototypes and about 22.5 kB of JSON, and inference needs no LLM or network. That is a compact algorithmic footprint, not a measured flight-computer timing, RAM, or power budget. We have not benchmarked flight hardware or ported and validated disconnected Quest inference. Evidence: `extract_features`, `_train`, `retrain`, `export_model`.

**RU:** «Пять отсчётов, 18 признаков, максимум 96 прототипов; воспроизведённый кандидат — 64 прототипа и около 22,5 кБ JSON. Время, RAM и энергопотребление на лётном процессоре ещё не измерены».

### Q10. “Would you actually have saved Spirit? Can you see beneath the surface?”

**Answer:** We cannot establish that counterfactual. Spirit is the motivating case, not a validated intervention. Arescope observes surface geometry and telemetry degradation; it does not measure buried crust strength or subsurface bearing capacity. The presentation's Troy scan overlay is illustrative, and our simulator uses Gale terrain, not a physical replay of Troy. Evidence: the presentation's Spirit speaker note, V2 scope, and `rover_sim.py` terrain source.

**RU:** «Нельзя доказать, что мы спасли бы Spirit. Скан показывает поверхность, не прочность скрытого грунта. Troy на слайде — иллюстрация; симулятор использует рельеф Гейла».

### Q11. “Can the Voice Copilot hallucinate or approve a model?”

**Answer:** It can make language-model errors, so operators must check its answer against the supplied context. OmniRoute handles ASR, streamed LLM output, and TTS; the Copilot has no independent telemetry access. Its prompt requires brief explanations, acknowledgment of missing data, and human review. It has no deployment tool: Guardian's validation and explicit approval remain in the separate LAB workflow. A spoken assertion that a model is approved is not a deployment. Evidence: `copilot_core.py: SYSTEM_PROMPT` and `chat`, plus LAB's `/api/guardian/deploy` contract.

**RU:** «LLM может ошибаться; оператор сверяет ответ с переданными данными. Copilot не получает телеметрию самостоятельно и не имеет инструмента применения модели. Слова об одобрении не равны деплою».

### Q12. “Does a warning stop the rover? Is the risk score a failure probability?”

**Answer:** The prototype emits a risk level, predicted cause, low-confidence flag, estimated lead time, and recovery recommendation. It does not demonstrate a validated motor controller, emergency-stop interface, automatic lens cleaning, or safe reverse maneuver. Its risk score is a bounded heuristic based on the predicted class and telemetry severity, not a calibrated probability. Stop, inspect, reduce speed, or reroute are guidance; actual motion needs rover integration and validated procedures. Evidence: `predict_model`, `ACTIONS`, and the Copilot recovery constraints.

**RU:** «Сейчас выдаются риск и рекомендация, а не проверенное управление двигателями. Оценка риска — эвристика, не калиброванная вероятность; остановку и манёвры ещё нужно проверить на шасси».

### Q13. “Are you claiming NASA rovers have no autonomy? What is your baseline?”

**Answer:** No. The 89.5% baseline is our own Guardian v1, intentionally missing the emerging micro-slip pattern. The improvement measures this prototype on its own synthetic benchmark, not superiority over NASA rover autonomy or an external rover safety system. Our contribution is the integrated perception, warning, incident review, retraining, and human approval demonstration. Evidence: `guardian.py` module documentation, `_baseline`, and the presentation's evidence-slide speaker note.

**RU:** «Базовая модель — наш Guardian v1 без нового паттерна микропробуксовки. Это внутреннее сравнение, не доказательство превосходства над автономией NASA».

### Q14. “Can you transfer these results to search-and-rescue or geology robots?”

**Answer:** Those are proposed terrestrial trial platforms, not validated deployments. Degraded visibility, feature scarcity, slip, and intermittent links motivate similar monitoring, but each robot needs measured sensor inputs, independently labeled failures, appropriate recovery procedures, and fresh held-out testing. A sensible next experiment is a controlled chassis trial that measures warnings, missed events, false stops, latency, and recovery outcomes. We cannot carry the synthetic Mars percentages across unchanged. Evidence: V2 impact/roadmap and the presentation's final slide.

**RU:** «SAR и геологические роботы — площадки будущих испытаний. Нужны собственные датчики, метки, процедуры и независимая оценка; переносить синтетические проценты напрямую нельзя».

### Q15. “Do you validate deep shadows, actual dusty lenses, and real soil physics?”

**Answer:** Not with the reported benchmark. Its `glare` replay brightens a synthetic contrast proxy; dust reduces useful points, contrast, and frame rate; slip changes commanded-versus-observed motion. Deep shadow is a realistic target condition, not a separately validated replay here. Quest can support physical perception experiments, but those captures are not the 36-trajectory synthetic validation. Physical optics and chassis trials are required before broader claims. Evidence: `RoverSimulator.step` and the current telemetry feature contract.

**RU:** «Опубликованные метрики относятся к синтетическим деградациям. Глубокая тень — целевое условие, не отдельно проверенный прогон. Реальные линзы и грунт требуют физических испытаний».

## 4. Evidence and claim-control record

### Primary project sources — read before drafting

| Source | What it supports |
| --- | --- |
| [V2 Rover + Guardian plan](C:/Users/Timur/Desktop/arescope-project/docs/PLAN_V2_ROVER_GUARDIAN.md) | Rover focus, Quest as mast stand, realistic hazards, two loops, human approval, operator Copilot, terrestrial roadmap. The plan includes proposed work; it is not completion evidence for every item. |
| [English presentation](<C:/Users/Timur/Desktop/arescope-project/presentation/Arescope — NASA Space Apps Challenge 2026.html>) | Exact tagline, Spirit/April 2009 story, one-way delay, published rounded numbers, illustrative-overlay caveat, Earth prototype versus onboard design. |
| [Guardian implementation](C:/Users/Timur/Desktop/arescope-project/services/arescope-lab/guardian.py) | Actual supervised classifier, five-sample features, cause/action mapping, split generation, metrics definitions, candidate gate, explicit human approval. |

### Read-only corroboration used to avoid unsupported demo claims

| Source | What was checked |
| --- | --- |
| [Rover simulator](C:/Users/Timur/Desktop/arescope-project/services/arescope-lab/rover_sim.py) | Five synthetic fault causes, Gale terrain replay, telemetry generation, progressive degradation, and actual recovery-input boundary. |
| [Guardian tests](C:/Users/Timur/Desktop/arescope-project/services/arescope-lab/tests/test_guardian.py) | The 192-window adaptation fixture, disjoint corridors/windows, candidate-versus-active behavior, and model-size bounds. The test suite was inspected; no claim is made here that the full suite was rerun for this documentation edit. |
| [HiRISE metadata](C:/Users/Timur/Desktop/arescope-project/services/arescope-lab/static/data/hirise-gale.json) and [MOLA metadata](C:/Users/Timur/Desktop/arescope-project/services/arescope-lab/static/data/mola-gale.json) | Product IDs, grid sizes, native/effective spacing, archive provenance, regional-versus-local resolution limits. |
| [LAB backend](C:/Users/Timur/Desktop/arescope-project/services/arescope-lab/app.py) and [LAB interface](C:/Users/Timur/Desktop/arescope-project/services/arescope-lab/static/index.html) | Real button labels, labeled-incident selection, changed-label invalidation, version checks, approval API, and status displays. |
| [Quest frame sender](C:/Users/Timur/Desktop/arescope-project/unity/arescope-quest/Assets/Arescope/LiveFrameSender.cs) | Current mast-testbed frame upload and server-returned Guardian results; no assertion of a completed disconnected onboard inference port. |
| [Copilot core](C:/Users/Timur/Desktop/arescope-project/services/arescope-copilot/copilot_core.py), [service contract](C:/Users/Timur/Desktop/arescope-project/services/arescope-copilot/README.md), and [Quest Copilot client](C:/Users/Timur/Desktop/arescope-project/unity/arescope-quest/Assets/ArescopeClient/CopilotClient.cs) | OmniRoute voice pipeline, explicit optional context, Russian operator prompt, absence of independent telemetry access, and typed-query fallback capability. |

NASA's Spirit and communication sources linked in §1 were checked for the April 23 date and the one-way 3–22 minute range. NASA's dust-storm explanation was checked for wind realism. Product catalog links establish archive provenance; the **project's local metadata**, not a generic catalog resolution claim, supplies the exact displayed grid spacing.

### Numeric reproduction for this document

The existing Python implementation was run with bytecode writing disabled. A fresh `GuardianEngine` was evaluated, then retrained in memory on the same 192-window adaptation fixture represented in `adaptation_incidents`. No model was deployed and no service/database state was changed by this verification.

| Returned value | Baseline | Adapted candidate |
| --- | --- | --- |
| `holdoutTrajectories` / `evaluatedWindows` | 36 / 1152 | 36 / 1152 |
| `caughtFailures` / `totalFailures` | 26 / 30 | 30 / 30 |
| `F1` | 0.8950747548026402 | 0.9864308083449758 |
| `meanLeadTimeS` | 14.923076923076923 | 14.8 |
| `falseAlarms` | 10 | 11 |
| `falseAlarmRate` | 0.02032520325203252 | 0.022357723577235773 |
| `microSlipRecall` | 0.0 | 0.9540229885057471 |

The reproduced candidate passed `candidate_ready`; it remained a candidate. Rounded public figures in §1 match the presentation. The website and repository links are submission links, not assertions that a live deployment or physical demonstration was tested during preparation of this document.



