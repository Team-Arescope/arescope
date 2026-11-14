# 12 · Матрица тестирования

## Модульные тесты

Все строки матриц ниже — предлагаемые сценарии, а не отчёт о выполнении. Предусловия, шаги, ожидаемый результат и критерий провала являются проектными критериями `[ПРЕДПОЛОЖЕНИЕ]`, если в ячейке нет отдельного статуса. [ПРЕДПОЛОЖЕНИЕ: test design]

| ID | Предусловия | Шаги | Ожидаемый результат | Критерий провала |
|---|---|---|---|---|
| UT-01 ModePolicy | Unity Test Runner, test assembly | Проверить Passthrough/Mixed/Scan при `hasScan=false/true` | Passthrough допустим без меша; Mixed/Scan допустимы только при наличии геометрии | Невозможный режим разрешён либо доступный запрещён |
| UT-02 Triangle filtering | Синтетические массивы вершин/индексов | Подать корректные локальные треугольники, повторные индексы, out-of-range, NaN, длинное ребро | Валидные треугольники остаются; rejected counts логируются | Тихая порча меша или исключение индекса |
| UT-03 Minimap vertical band | Изолированный projection helper (его требуется отделить от MonoBehaviour) | Подать точки при y offset −0.031, −0.030, 0, +0.030, +0.031 m | Исключены только точки вне ±0.03 m | Фильтр зависит от pitch взгляда или использует неверные единицы |
| UT-04 ARSM parser | Бинарные fixtures v1/v2 | Проверить длину, версию, counts, кратность индексов 3 | Корректные тела принимаются, повреждённые отклоняются | Чтение за границами или неверная проверка длины |
| UT-05 Session retention | Временная SQLite DB | Создать истёкшие sessions, payload выше лимита и session на 2000 frames | Старые sessions удаляются, frames удаляются каскадно | Удалены новые данные или остались осиротевшие frames |

- Репозиторий содержит `Tests/ModePolicyTest.cs`; полный прогон набора тестов алгоритмов не зафиксирован. [ПРОВЕРЕНО: file listing]; запуск Unit Runner [ТРЕБУЕТ ПРОВЕРКИ]

## Интеграционные тесты

| ID | Предусловия | Шаги | Ожидаемый результат | Критерий провала |
|---|---|---|---|---|
| IT-01 Producer ingest | LAB работает, producer token в защищённом env | Отправить frame с 384 точками | HTTP 200, `ok=true`; latest имеет `source=live-quest`; session записана при соблюдении интервала | 401/422/5xx или latest отсутствует |
| IT-02 Rate guard | Тестовая room и контролируемые часы | Отправить два frames с интервалом <0.25 s | второй `throttled=true`, live state обновлён | история растёт быстрее лимита или live feed замер |
| IT-03 Session split | Тестовая DB | Выдержать >60 s без frame и отправить новый | создаётся новый session ID | продолжается старая session после gap |
| IT-04 PLY | Session с точками | Экспортировать `frame=last`, `frame=merged` | корректный ASCII PLY header и ≤400k vertices | неверный header/count/coordinates |
| IT-05 Mesh upload | Тестовая session, ARSM v1 и v2 | Загрузить body, прочитать mesh по session id | сохранён файл правильной длины/hash | принимается повреждённая длина или файла нет |
| IT-06 Log upload | Тестовый producer token | Загрузить непустой текст, запросить список и скачать | UTC filename, body hash совпадает | path traversal, токен не проверен или файл отсутствует |
| IT-07 Copilot | Copilot service и staging router | Тестовое audio → chat SSE → speech | ASR JSON, SSE complete, audio/mpeg | вызывается SDM, stream обрезан или ответ пуст |
| IT-08 Mixed view | Unity scene, camera/layer mock | Переключить режимы | renderer/passthrough соответствуют таблице режимов | mixed не показывает одновременно passthrough и mesh |

## Тесты на шлеме Quest 3S

| ID | Предусловия и шаги | Ожидаемый результат | Критерий провала |
|---|---|---|---|
| H-01 Launch/XR | Установить APK, выдать permissions, запустить | XR активен, нет crash, HUD виден | crash/black screen |
| H-02 Scan | Нажать X; сканировать 60 s, поворачиваясь и перемещаясь | растёт scan progress, точки обновляются, tracking остаётся отзывчивым | progress=0 или freeze |
| H-03 Minimap band | Смотреть на дверь, затем на пол; присесть/встать | показывается геометрия текущей высоты глаз ±3 см | пол отображается вне полосы или дверь на уровне глаз не видна |
| H-04 Mixed mode | После финализации переключить Y | одновременно видны passthrough и mesh | фон чёрный либо mesh пропал |
| H-05 Final mesh | Завершить скан | нет длинных линий через комнату; logged triangle counts доступны | spikes, mesh отсутствует, hang |
| H-06 Relocalization | Выйти за boundary на 10 s, вернуться; отдельно sleep/resume | геометрия остаётся выровненной; смещение измерено | объекты меняются местами или yaw скачет |
| H-07 Uplink | Смотреть HUD/LAB во время скана | HTTP 200, session получает frames | 401, timeout, frames отсутствуют |
| H-08 Mesh upload | После финализации проверить серверную session | `hasMesh=true`, bytes>0, ARSM/atlas ожидаемого типа | upload отсутствует или body повреждён |
| H-09 Diagnostic upload | Удерживать X+Y 2 s, запросить list/download logs | файл текущего запуска появляется | файла нет либо он старый/пустой |
| H-10 Thermal/battery | Непрерывный скан 10 min | записать FPS, заряд %, температуру; пороги требуется утвердить | thermal throttle, дискомфорт от motion, crash |

- Для 0.5.11/0.5.12 зафиксирован build success, но полная матрица H-01…H-10 не выполнена. [ПРОВЕРЕНО: release record]; runtime acceptance [ТРЕБУЕТ ПРОВЕРКИ]

## Формат записи регрессионного теста

Схема записи (не код):

```text
release, headset_os, openxr_runtime, room, duration, refresh_rate,
scan_seconds, finalize_seconds, fps_min_median, battery_delta,
mesh_vertices, raw_triangles, kept_triangles, median_edge, threshold,
anchor_transform_before_after, frame_count, mesh_uploaded, log_filename
```

[ПРЕДПОЛОЖЕНИЕ: предложенная схема записи]
