using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace Arescope.Hud
{
    [DisallowMultipleComponent]
    public sealed class ArescopeHudController : MonoBehaviour
    {
        public const int HudLayer = 5;
        private const float RefWidth = 1280f;
        private const float SideInset = 112f;
        private const float TopEdgeY = 316f;
        private const float BottomEdgeY = -276f;
        private const float DefaultFillAlpha = 0.25f;
        private const float MapScaleUnitsPer10M = 74f;
        private const int MaxStatusSlots = 5;

        public static readonly Color PaletteInk = new Color32(0x10, 0x0B, 0x09, 0xFF);
        public static readonly Color PalettePaper = new Color32(0xF5, 0xE8, 0xDF, 0xFF);
        public static readonly Color PaletteMuted = new Color32(0xA2, 0x94, 0x8C, 0xFF);
        public static readonly Color PaletteRule = new Color32(0x51, 0x30, 0x26, 0xFF);
        public static readonly Color PaletteCopper = new Color32(0xEE, 0x8A, 0x5B, 0xFF);
        public static readonly Color GlyphShadowColor = new Color(0f, 0f, 0f, 0.72f);
        public static readonly Vector2 GlyphShadowOffset = new Vector2(1f, -1f);

        private static readonly string[] CardinalNames = { "N", "NE", "E", "SE", "S", "SW", "W", "NW" };
        private static readonly float[] CardinalBearings = { 0f, 45f, 90f, 135f, 180f, 225f, 270f, 315f };

        public Transform targetCamera;
        public Canvas worldCanvas;
        public RectTransform panel;
        public float followDistance = 1.15f;
        public float followSmoothing = 14f;
        public int followMode = 0; // 0=Smooth, 1=Hard
        public Vector2 canvasSize = new Vector2(1.7f, 1.0f);

        private readonly Dictionary<string, RectTransform> panelRects = new Dictionary<string, RectTransform>(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, MaskableGraphic> cardBackdrops = new Dictionary<string, MaskableGraphic>(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, Sprite> iconCache = new Dictionary<string, Sprite>(StringComparer.OrdinalIgnoreCase);
        private readonly List<Texture2D> ownedIconTextures = new List<Texture2D>();
        private readonly List<string> activeStatusRows = new List<string>(MaxStatusSlots);

        private Font sansFont;
        private Font monoFont;

        // Status panel
        private Text statusHeaderLabel;
        private readonly Image[] statusIcons = new Image[MaxStatusSlots];
        private readonly Text[] statusRowLabels = new Text[MaxStatusSlots];
        private readonly RectTransform[] statusRowRects = new RectTransform[MaxStatusSlots];

        // Event panel
        private RectTransform eventRoot;
        private Text eventBodyLabel;
        private float eventHideAt = -1f;

        // Map panel
        private Text mapHeaderLabel;
        private Text mapCountLabel;
        private ArescopeMapPointsGraphic mapPointsGraphic;

        // Assistant panel
        private Text assistantHeaderLabel;
        private Text assistantBodyLabel;

        // Compass panel
        private Text compassHeaderLabel;
        private ArescopeCompassTicksGraphic compassTicksGraphic;
        private RectTransform compassStripRect;
        private readonly Text[] compassCardinalLabels = new Text[8];
        private float currentHeadingDeg;
        private bool headingExplicitlySet;

        // Voice panel
        private Text voiceStateLabel;
        private ArescopeVoiceMeterGraphic voiceMeterGraphic;

        private bool built;
        private bool hudEnabled = true;

        private void Awake()
        {
            EnsureBuilt();
            ApplyEnvironmentPreviewIfRequested();
        }

        private void OnDestroy()
        {
            foreach (var kv in iconCache)
            {
                if (kv.Value != null)
                {
                    DestroyImmediate(kv.Value);
                }
            }
            iconCache.Clear();
            ownedIconTextures.Clear();
        }

        private void Update()
        {
            if (eventRoot != null && eventRoot.gameObject.activeSelf && eventHideAt > 0f && Time.unscaledTime >= eventHideAt)
            {
                eventHideAt = -1f;
                eventRoot.gameObject.SetActive(false);
            }
        }

        private void LateUpdate()
        {
            EnsureBuilt();
            if (worldCanvas == null)
            {
                return;
            }

            Transform cam = ResolveCameraTransform();
            if (cam == null)
            {
                return;
            }

            Vector3 desiredPos = cam.position + cam.forward * Mathf.Max(0.25f, followDistance);
            Quaternion desiredRot = cam.rotation;

            float blend = followMode == 1
                ? 1f
                : 1f - Mathf.Exp(-Mathf.Max(0.1f, followSmoothing) * Mathf.Max(Time.unscaledDeltaTime, 1f / 90f));

            Transform canvasTf = worldCanvas.transform;
            if (blend >= 0.999f || (canvasTf.position - desiredPos).sqrMagnitude > 25f)
            {
                canvasTf.position = desiredPos;
                canvasTf.rotation = desiredRot;
            }
            else
            {
                canvasTf.position = Vector3.Lerp(canvasTf.position, desiredPos, blend);
                canvasTf.rotation = Quaternion.Slerp(canvasTf.rotation, desiredRot, blend);
            }

            if (!headingExplicitlySet)
            {
                Vector3 flatFwd = Vector3.ProjectOnPlane(cam.forward, Vector3.up);
                if (flatFwd.sqrMagnitude > 1e-4f)
                {
                    float yaw = Mathf.Atan2(flatFwd.x, flatFwd.z) * Mathf.Rad2Deg;
                    UpdateCompassVisuals(yaw);
                }
            }
        }

        public void SetStatus(string label, string value)
        {
            EnsureBuilt();
            string combined = string.IsNullOrWhiteSpace(value)
                ? (label ?? string.Empty).Trim()
                : $"{(label ?? string.Empty).Trim()} {value.Trim()}";

            string cleanLabel = (label ?? string.Empty).Trim();
            if (string.IsNullOrEmpty(combined))
            {
                activeStatusRows.Clear();
            }
            else
            {
                int existingIdx = activeStatusRows.FindIndex(r =>
                    string.Equals(r, cleanLabel, StringComparison.OrdinalIgnoreCase) ||
                    (!string.IsNullOrEmpty(cleanLabel) && r.StartsWith(cleanLabel + " ", StringComparison.OrdinalIgnoreCase)));
                if (existingIdx >= 0)
                {
                    activeStatusRows[existingIdx] = combined;
                }
                else if (activeStatusRows.Count < MaxStatusSlots)
                {
                    activeStatusRows.Add(combined);
                }
                else
                {
                    activeStatusRows[MaxStatusSlots - 1] = combined;
                }
            }

            RefreshStatusRows();
        }

        public void SetStatusRows(IEnumerable<string> rows)
        {
            EnsureBuilt();
            activeStatusRows.Clear();
            if (rows != null)
            {
                foreach (var row in rows)
                {
                    if (!string.IsNullOrWhiteSpace(row))
                    {
                        activeStatusRows.Add(row.Trim());
                        if (activeStatusRows.Count >= MaxStatusSlots)
                        {
                            break;
                        }
                    }
                }
            }

            RefreshStatusRows();
        }

        public void SetStatuses(IEnumerable<string> rows)
        {
            SetStatusRows(rows);
        }

        public void ShowEvent(string message, float duration = 4f)
        {
            EnsureBuilt();
            if (eventRoot == null || eventBodyLabel == null)
            {
                return;
            }

            if (string.IsNullOrWhiteSpace(message))
            {
                eventHideAt = -1f;
                eventRoot.gameObject.SetActive(false);
                return;
            }

            eventBodyLabel.text = message.Trim();
            eventRoot.gameObject.SetActive(true);
            eventHideAt = duration > 0f && Application.isPlaying ? Time.unscaledTime + duration : -1f;
        }

        public void SetMapPoints(IReadOnlyList<Vector2> points, float rangeMeters, bool scanCloud = true)
        {
            EnsureBuilt();
            if (mapPointsGraphic == null || mapCountLabel == null)
            {
                return;
            }

            float safeRange = Mathf.Max(0.5f, rangeMeters);
            int count = points != null ? points.Count : 0;
            int cap = scanCloud ? 192 : 64;
            int shown = Mathf.Min(count, cap);

            if (mapHeaderLabel != null)
            {
                mapHeaderLabel.text = $"LOCAL MAP · ±{Mathf.RoundToInt(safeRange)} m";
            }

            mapCountLabel.text = scanCloud ? $"POINTS {shown}" : $"CONTACTS {shown}";
            mapPointsGraphic.SetPoints(points, safeRange, scanCloud, MapScaleUnitsPer10M);
        }

        public void SetHeadingDeg(float headingDeg)
        {
            EnsureBuilt();
            headingExplicitlySet = true;
            UpdateCompassVisuals(headingDeg);
        }

        public void SetVoiceState(string state, float level = 0f)
        {
            EnsureBuilt();
            string cleanState = string.IsNullOrWhiteSpace(state) ? "-" : state.Trim().ToUpperInvariant();
            if (voiceStateLabel != null)
            {
                voiceStateLabel.text = $"VOICE  {cleanState}";
            }

            if (voiceMeterGraphic != null)
            {
                voiceMeterGraphic.Level = Mathf.Clamp01(level);
            }
        }

        public void SetAssistantText(string text)
        {
            EnsureBuilt();
            if (assistantBodyLabel != null)
            {
                assistantBodyLabel.text = string.IsNullOrWhiteSpace(text) ? "No response yet" : text.Trim();
            }
        }

        public void SetHudEnabled(bool enabled)
        {
            EnsureBuilt();
            hudEnabled = enabled;
            if (worldCanvas != null)
            {
                worldCanvas.gameObject.SetActive(hudEnabled);
            }
        }

        public void SetFollowMode(string mode)
        {
            if (string.Equals(mode, "hard", StringComparison.OrdinalIgnoreCase))
            {
                followMode = 1;
            }
            else if (string.Equals(mode, "smooth", StringComparison.OrdinalIgnoreCase))
            {
                followMode = 0;
            }
        }

        public void SetCardBackdropAlpha(string cardKey, float alpha)
        {
            EnsureBuilt();
            float clamped = Mathf.Clamp01(alpha);
            if (string.IsNullOrWhiteSpace(cardKey) || string.Equals(cardKey, "all", StringComparison.OrdinalIgnoreCase))
            {
                foreach (var kv in cardBackdrops)
                {
                    if (kv.Value != null)
                    {
                        Color c = kv.Value.color;
                        c.a = clamped;
                        kv.Value.color = c;
                    }
                }
                return;
            }

            if (cardBackdrops.TryGetValue(cardKey.Trim(), out var graphic) && graphic != null)
            {
                Color c = graphic.color;
                c.a = clamped;
                graphic.color = c;
            }
        }

        public Dictionary<string, RectTransform> GetPanelRects()
        {
            EnsureBuilt();
            return new Dictionary<string, RectTransform>(panelRects, StringComparer.OrdinalIgnoreCase);
        }

        public void ApplyPreviewFixture()
        {
            EnsureBuilt();

            if (string.Equals(Environment.GetEnvironmentVariable("ARESCOPE_PREVIEW_EMPTY"), "1", StringComparison.Ordinal))
            {
                SetStatusRows(Array.Empty<string>());
                ShowEvent(string.Empty, 0f);
                SetMapPoints(Array.Empty<Vector2>(), 10f, true);
                SetHeadingDeg(0f);
                SetVoiceState("-", 0f);
                SetAssistantText(string.Empty);
                return;
            }

            SetStatusRows(new[]
            {
                "PREVIEW: SCAN READY",
                "PREVIEW: DEPTH STREAMING",
                "PREVIEW: UPLINK 200 2s",
                "PREVIEW: POWER 84%"
            });
            ShowEvent("PREVIEW: Room anchor locked", 0f);
            SetHeadingDeg(85f);
            SetVoiceState("LISTENING", 0.65f);
            SetAssistantText("PREVIEW: Corridor clear ahead; door opening 3.2 m to the right.");

            string mapMode = Environment.GetEnvironmentVariable("ARESCOPE_PREVIEW_MAP");
            if (string.Equals(mapMode, "walls", StringComparison.OrdinalIgnoreCase))
            {
                SetMapPoints(BuildPreviewWallPoints(), 10f, scanCloud: true);
            }
            else
            {
                SetMapPoints(BuildPreviewContacts(), 10f, scanCloud: false);
            }
        }

        private void ApplyEnvironmentPreviewIfRequested()
        {
            bool hasPreviewEnv =
                !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("ARESCOPE_HUD_PREVIEW_PATH")) ||
                !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("ARESCOPE_PREVIEW_MAP")) ||
                !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("ARESCOPE_PREVIEW_EMPTY")) ||
                !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("ARESCOPE_PREVIEW_BG"));

            if (hasPreviewEnv)
            {
                ApplyPreviewFixture();
            }
        }

        private void EnsureBuilt()
        {
            if (built && worldCanvas != null && panel != null && panelRects.Count == 6)
            {
                return;
            }

            LoadFonts();
            BuildCanvasHierarchy();
            built = true;

            // Default clean initial state.
            RefreshStatusRows();
            ShowEvent(string.Empty, 0f);
            SetMapPoints(Array.Empty<Vector2>(), 10f, true);
            UpdateCompassVisuals(0f);
            SetVoiceState("-", 0f);
            SetAssistantText("No response yet");
            SetHudEnabled(hudEnabled);
        }

        private void LoadFonts()
        {
            sansFont = Resources.Load<Font>("ArescopeFonts/Manrope-SemiBold");
            monoFont = Resources.Load<Font>("ArescopeFonts/DMMono-Medium");

            Font fallback = null;
            try
            {
                fallback = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            }
            catch (Exception)
            {
                // Ignore if LegacyRuntime.ttf is unavailable in stripped runtime.
            }

            if (fallback == null)
            {
                try
                {
                    fallback = Resources.GetBuiltinResource<Font>("Arial.ttf");
                }
                catch (Exception)
                {
                    fallback = Font.CreateDynamicFontFromOSFont("Arial", 16);
                }
            }

            if (sansFont == null)
            {
                sansFont = fallback;
            }

            if (monoFont == null)
            {
                monoFont = sansFont != null ? sansFont : fallback;
            }
        }

        private void BuildCanvasHierarchy()
        {
            panelRects.Clear();
            cardBackdrops.Clear();

            float refHeight = RefWidth * (canvasSize.y / Mathf.Max(0.1f, canvasSize.x));

            if (worldCanvas == null)
            {
                Transform existing = transform.Find("ArescopeHudCanvas");
                GameObject canvasGo = existing != null ? existing.gameObject : new GameObject("ArescopeHudCanvas");
                canvasGo.transform.SetParent(transform, false);
                worldCanvas = canvasGo.GetComponent<Canvas>();
                if (worldCanvas == null)
                {
                    worldCanvas = canvasGo.AddComponent<Canvas>();
                }
                if (canvasGo.GetComponent<CanvasScaler>() == null)
                {
                    canvasGo.AddComponent<CanvasScaler>();
                }
            }

            worldCanvas.gameObject.layer = HudLayer;
            worldCanvas.renderMode = RenderMode.WorldSpace;
            Camera camComponent = targetCamera != null ? targetCamera.GetComponent<Camera>() : Camera.main;
            worldCanvas.worldCamera = camComponent;

            RectTransform canvasRect = worldCanvas.GetComponent<RectTransform>();
            canvasRect.sizeDelta = new Vector2(RefWidth, refHeight);
            float scale = canvasSize.x / RefWidth;
            canvasRect.localScale = new Vector3(scale, scale, scale);

            if (panel == null)
            {
                Transform existingPanel = worldCanvas.transform.Find("HudRoot");
                if (existingPanel != null)
                {
                    DestroyImmediate(existingPanel.gameObject);
                }

                GameObject rootGo = new GameObject("HudRoot", typeof(RectTransform));
                rootGo.layer = HudLayer;
                rootGo.transform.SetParent(worldCanvas.transform, false);
                panel = rootGo.GetComponent<RectTransform>();
            }
            else
            {
                for (int i = panel.childCount - 1; i >= 0; i--)
                {
                    DestroyImmediate(panel.GetChild(i).gameObject);
                }
            }

            panel.anchorMin = new Vector2(0.5f, 0.5f);
            panel.anchorMax = new Vector2(0.5f, 0.5f);
            panel.pivot = new Vector2(0.5f, 0.5f);
            panel.anchoredPosition = Vector2.zero;
            panel.sizeDelta = new Vector2(RefWidth, refHeight);

            float leftEdge = -RefWidth * 0.5f + SideInset;  // -528
            float rightEdge = RefWidth * 0.5f - SideInset;  // +528

            BuildStatusPanel(leftEdge, TopEdgeY);
            BuildEventPanel(leftEdge, BottomEdgeY + 46f + 14f);
            BuildVoicePanel(leftEdge, BottomEdgeY);
            BuildCompassPanel(0f, TopEdgeY);
            BuildMapPanel(rightEdge, TopEdgeY);
            BuildAssistantPanel(rightEdge, BottomEdgeY);
        }

        private void BuildStatusPanel(float leftEdge, float topEdge)
        {
            const float w = 300f;
            const float h = 146f;
            var card = CreateChamferPanel("status", new Vector2(leftEdge + w * 0.5f, topEdge - h * 0.5f), new Vector2(w, h), true);

            statusHeaderLabel = CreateLabel(card.transform, "Header", sansFont, 14, PaletteMuted, TextAnchor.UpperLeft);
            SetRect(statusHeaderLabel.rectTransform, 14f, -8f, w - 28f, 18f, new Vector2(0f, 1f), new Vector2(0f, 1f));
            statusHeaderLabel.text = "SYSTEM STATUS";

            float startY = -29f;
            const float rowHeight = 23f;
            for (int i = 0; i < MaxStatusSlots; i++)
            {
                GameObject rowGo = new GameObject($"Row_{i}", typeof(RectTransform));
                rowGo.layer = HudLayer;
                rowGo.transform.SetParent(card.transform, false);
                RectTransform rowRt = rowGo.GetComponent<RectTransform>();
                SetRect(rowRt, 14f, startY - i * rowHeight, w - 24f, rowHeight, new Vector2(0f, 1f), new Vector2(0f, 1f));
                statusRowRects[i] = rowRt;

                GameObject iconGo = new GameObject("Icon", typeof(RectTransform), typeof(Image));
                iconGo.layer = HudLayer;
                iconGo.transform.SetParent(rowRt, false);
                Image iconImg = iconGo.GetComponent<Image>();
                iconImg.color = PalettePaper;
                iconImg.preserveAspect = true;
                SetRect(iconImg.rectTransform, 0f, -3.5f, 16f, 16f, new Vector2(0f, 1f), new Vector2(0f, 1f));
                statusIcons[i] = iconImg;

                Text rowText = CreateLabel(rowRt, "Label", sansFont, 16, PalettePaper, TextAnchor.MiddleLeft);
                rowText.verticalOverflow = VerticalWrapMode.Overflow;
                rowText.horizontalOverflow = HorizontalWrapMode.Overflow;
                SetRect(rowText.rectTransform, 22f, 0f, w - 46f, rowHeight, new Vector2(0f, 1f), new Vector2(0f, 1f));
                statusRowLabels[i] = rowText;
            }
        }

        private void BuildEventPanel(float leftEdge, float bottomEdge)
        {
            const float w = 260f;
            const float h = 64f;
            eventRoot = CreateChamferPanel("event", new Vector2(leftEdge + w * 0.5f, bottomEdge + h * 0.5f), new Vector2(w, h), true);

            eventBodyLabel = CreateLabel(eventRoot.transform, "Body", sansFont, 16, PalettePaper, TextAnchor.MiddleLeft);
            eventBodyLabel.verticalOverflow = VerticalWrapMode.Overflow;
            SetRect(eventBodyLabel.rectTransform, 14f, -8f, w - 28f, h - 16f, new Vector2(0f, 1f), new Vector2(0f, 1f));
            eventRoot.gameObject.SetActive(false);
        }

        private void BuildVoicePanel(float leftEdge, float bottomEdge)
        {
            const float w = 240f;
            const float h = 46f;
            var card = CreateChamferPanel("voice", new Vector2(leftEdge + w * 0.5f, bottomEdge + h * 0.5f), new Vector2(w, h), true);

            voiceStateLabel = CreateLabel(card.transform, "State", monoFont, 16, PalettePaper, TextAnchor.MiddleLeft);
            voiceStateLabel.verticalOverflow = VerticalWrapMode.Overflow;
            voiceStateLabel.horizontalOverflow = HorizontalWrapMode.Overflow;
            SetRect(voiceStateLabel.rectTransform, 14f, -6f, w - 72f, 34f, new Vector2(0f, 1f), new Vector2(0f, 1f));

            GameObject meterGo = new GameObject("Meter", typeof(RectTransform), typeof(CanvasRenderer), typeof(ArescopeVoiceMeterGraphic));
            meterGo.layer = HudLayer;
            meterGo.transform.SetParent(card.transform, false);
            RectTransform meterRt = meterGo.GetComponent<RectTransform>();
            SetRect(meterRt, -14f, -13f, 36f, 18f, new Vector2(1f, 1f), new Vector2(1f, 1f));
            voiceMeterGraphic = meterGo.GetComponent<ArescopeVoiceMeterGraphic>();
            voiceMeterGraphic.color = PaletteCopper;
            voiceMeterGraphic.InactiveColor = new Color(PaletteRule.r, PaletteRule.g, PaletteRule.b, 0.7f);
        }

        private void BuildCompassPanel(float centerX, float topEdge)
        {
            const float w = 360f;
            const float h = 86f;
            var card = CreateChamferPanel("compass", new Vector2(centerX, topEdge - h * 0.5f), new Vector2(w, h), true);

            compassHeaderLabel = CreateLabel(card.transform, "HeadingReadout", monoFont, 12, PalettePaper, TextAnchor.UpperCenter);
            compassHeaderLabel.verticalOverflow = VerticalWrapMode.Overflow;
            SetRect(compassHeaderLabel.rectTransform, 0f, -10f, w - 24f, 18f, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f));

            GameObject stripGo = new GameObject("Strip", typeof(RectTransform), typeof(RectMask2D));
            stripGo.layer = HudLayer;
            stripGo.transform.SetParent(card.transform, false);
            compassStripRect = stripGo.GetComponent<RectTransform>();
            SetRect(compassStripRect, 0f, -30f, w - 28f, 48f, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f));

            for (int i = 0; i < CardinalNames.Length; i++)
            {
                Text lbl = CreateLabel(compassStripRect, $"Cardinal_{CardinalNames[i]}", monoFont, 12, PalettePaper, TextAnchor.UpperCenter);
                lbl.verticalOverflow = VerticalWrapMode.Overflow;
                lbl.horizontalOverflow = HorizontalWrapMode.Overflow;
                SetRect(lbl.rectTransform, 0f, -2f, 28f, 18f, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f));
                lbl.text = CardinalNames[i];
                compassCardinalLabels[i] = lbl;
            }

            GameObject ticksGo = new GameObject("Ticks", typeof(RectTransform), typeof(CanvasRenderer), typeof(ArescopeCompassTicksGraphic));
            ticksGo.layer = HudLayer;
            ticksGo.transform.SetParent(compassStripRect, false);
            RectTransform ticksRt = ticksGo.GetComponent<RectTransform>();
            SetRect(ticksRt, 0f, -22f, w - 28f, 24f, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f));
            compassTicksGraphic = ticksGo.GetComponent<ArescopeCompassTicksGraphic>();
            compassTicksGraphic.color = new Color(PaletteRule.r, PaletteRule.g, PaletteRule.b, 0.9f);
            compassTicksGraphic.LubberColor = PalettePaper;
        }

        private void BuildMapPanel(float rightEdge, float topEdge)
        {
            const float diameter = 240f;
            GameObject go = new GameObject("Panel_map", typeof(RectTransform), typeof(CanvasRenderer), typeof(ArescopeCircleCardGraphic), typeof(Mask));
            go.layer = HudLayer;
            go.transform.SetParent(panel, false);

            RectTransform rt = go.GetComponent<RectTransform>();
            rt.anchorMin = new Vector2(0.5f, 0.5f);
            rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.anchoredPosition = new Vector2(rightEdge - diameter * 0.5f, topEdge - diameter * 0.5f);
            rt.sizeDelta = new Vector2(diameter, diameter);

            ArescopeCircleCardGraphic circle = go.GetComponent<ArescopeCircleCardGraphic>();
            circle.color = new Color(PaletteInk.r, PaletteInk.g, PaletteInk.b, DefaultFillAlpha);
            circle.BorderColor = new Color(PaletteRule.r, PaletteRule.g, PaletteRule.b, 0.9f);
            circle.BorderWidth = 1.5f;

            Mask mask = go.GetComponent<Mask>();
            mask.showMaskGraphic = true;

            panelRects["map"] = rt;
            cardBackdrops["map"] = circle;

            // Inset labels inside circular safe area.
            mapHeaderLabel = CreateLabel(rt, "Header", sansFont, 14, PalettePaper, TextAnchor.UpperCenter);
            mapHeaderLabel.verticalOverflow = VerticalWrapMode.Overflow;
            SetRect(mapHeaderLabel.rectTransform, 0f, -26f, 168f, 20f, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f));
            mapHeaderLabel.text = "LOCAL MAP · ±10 m";

            mapCountLabel = CreateLabel(rt, "Count", sansFont, 12, PaletteCopper, TextAnchor.UpperCenter);
            mapCountLabel.verticalOverflow = VerticalWrapMode.Overflow;
            SetRect(mapCountLabel.rectTransform, 0f, -45f, 150f, 18f, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f));
            mapCountLabel.text = "POINTS 0";

            // Map points and car-nav chevron centered at (0, -20).
            GameObject pointsGo = new GameObject("MapPoints", typeof(RectTransform), typeof(CanvasRenderer), typeof(ArescopeMapPointsGraphic));
            pointsGo.layer = HudLayer;
            pointsGo.transform.SetParent(rt, false);
            RectTransform pointsRt = pointsGo.GetComponent<RectTransform>();
            pointsRt.anchorMin = new Vector2(0.5f, 0.5f);
            pointsRt.anchorMax = new Vector2(0.5f, 0.5f);
            pointsRt.pivot = new Vector2(0.5f, 0.5f);
            pointsRt.anchoredPosition = new Vector2(0f, -20f);
            pointsRt.sizeDelta = new Vector2(diameter, diameter);
            mapPointsGraphic = pointsGo.GetComponent<ArescopeMapPointsGraphic>();
            mapPointsGraphic.color = PaletteCopper;

            GameObject chevronGo = new GameObject("Chevron", typeof(RectTransform), typeof(CanvasRenderer), typeof(ArescopeChevronGraphic));
            chevronGo.layer = HudLayer;
            chevronGo.transform.SetParent(rt, false);
            RectTransform chevRt = chevronGo.GetComponent<RectTransform>();
            chevRt.anchorMin = new Vector2(0.5f, 0.5f);
            chevRt.anchorMax = new Vector2(0.5f, 0.5f);
            chevRt.pivot = new Vector2(0.5f, 0.5f);
            chevRt.anchoredPosition = new Vector2(0f, -20f);
            chevRt.sizeDelta = new Vector2(14f, 16f);
            ArescopeChevronGraphic chevron = chevronGo.GetComponent<ArescopeChevronGraphic>();
            chevron.color = PaletteCopper;
        }

        private void BuildAssistantPanel(float rightEdge, float bottomEdge)
        {
            const float w = 420f;
            const float h = 155f;
            var card = CreateChamferPanel("assistant", new Vector2(rightEdge - w * 0.5f, bottomEdge + h * 0.5f), new Vector2(w, h), true);

            assistantHeaderLabel = CreateLabel(card.transform, "Header", sansFont, 14, PaletteCopper, TextAnchor.UpperLeft);
            assistantHeaderLabel.verticalOverflow = VerticalWrapMode.Overflow;
            SetRect(assistantHeaderLabel.rectTransform, 14f, -10f, w - 28f, 20f, new Vector2(0f, 1f), new Vector2(0f, 1f));
            assistantHeaderLabel.text = "COPILOT";

            assistantBodyLabel = CreateLabel(card.transform, "Body", sansFont, 20, PalettePaper, TextAnchor.UpperLeft);
            assistantBodyLabel.verticalOverflow = VerticalWrapMode.Overflow;
            SetRect(assistantBodyLabel.rectTransform, 14f, -34f, w - 28f, h - 44f, new Vector2(0f, 1f), new Vector2(0f, 1f));
        }

        private RectTransform CreateChamferPanel(string key, Vector2 anchoredPos, Vector2 size, bool showTopRule)
        {
            GameObject go = new GameObject($"Panel_{key}", typeof(RectTransform), typeof(CanvasRenderer), typeof(ArescopeChamferCardGraphic));
            go.layer = HudLayer;
            go.transform.SetParent(panel, false);

            RectTransform rt = go.GetComponent<RectTransform>();
            rt.anchorMin = new Vector2(0.5f, 0.5f);
            rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.anchoredPosition = anchoredPos;
            rt.sizeDelta = size;

            ArescopeChamferCardGraphic card = go.GetComponent<ArescopeChamferCardGraphic>();
            card.color = new Color(PaletteInk.r, PaletteInk.g, PaletteInk.b, DefaultFillAlpha);
            card.BorderColor = new Color(PaletteRule.r, PaletteRule.g, PaletteRule.b, 0.9f);
            card.BorderWidth = 1.25f;
            card.ChamferSize = 10f;
            card.ShowTopRule = showTopRule;
            card.TopRuleHeight = 2f;
            card.TopRuleColor = PaletteCopper;

            panelRects[key] = rt;
            cardBackdrops[key] = card;
            return rt;
        }

        private Text CreateLabel(Transform parent, string name, Font font, int fontSize, Color textColor, TextAnchor alignment)
        {
            GameObject go = new GameObject(name, typeof(RectTransform), typeof(CanvasRenderer), typeof(Text), typeof(Shadow));
            go.layer = HudLayer;
            go.transform.SetParent(parent, false);

            Text txt = go.GetComponent<Text>();
            txt.font = font;
            txt.fontSize = fontSize;
            txt.color = textColor;
            txt.alignment = alignment;
            txt.supportRichText = false;
            txt.raycastTarget = false;

            Shadow shadow = go.GetComponent<Shadow>();
            shadow.effectColor = GlyphShadowColor;
            shadow.effectDistance = GlyphShadowOffset;
            shadow.useGraphicAlpha = true;

            return txt;
        }

        private static void SetRect(
            RectTransform rt,
            float x,
            float y,
            float width,
            float height,
            Vector2 anchor,
            Vector2 pivot)
        {
            rt.anchorMin = anchor;
            rt.anchorMax = anchor;
            rt.pivot = pivot;
            rt.anchoredPosition = new Vector2(x, y);
            rt.sizeDelta = new Vector2(width, height);
        }

        private void RefreshStatusRows()
        {
            if (statusRowRects[0] == null)
            {
                return;
            }

            if (activeStatusRows.Count == 0)
            {
                statusRowRects[0].gameObject.SetActive(true);
                statusIcons[0].sprite = LoadIconSprite("dot");
                statusIcons[0].color = PaletteMuted;
                statusRowLabels[0].text = "—";
                for (int i = 1; i < MaxStatusSlots; i++)
                {
                    if (statusRowRects[i] != null)
                    {
                        statusRowRects[i].gameObject.SetActive(false);
                    }
                }
                return;
            }

            for (int i = 0; i < MaxStatusSlots; i++)
            {
                if (i < activeStatusRows.Count)
                {
                    string row = activeStatusRows[i];
                    statusRowRects[i].gameObject.SetActive(true);
                    string iconKey = PickIconForRow(row);
                    Sprite sp = LoadIconSprite(iconKey);
                    statusIcons[i].sprite = sp;
                    statusIcons[i].enabled = sp != null;
                    statusIcons[i].color = PalettePaper;
                    statusRowLabels[i].text = row;
                }
                else
                {
                    statusRowRects[i].gameObject.SetActive(false);
                }
            }
        }

        private void UpdateCompassVisuals(float yawDeg)
        {
            currentHeadingDeg = yawDeg;
            float norm = Mathf.Repeat(yawDeg, 360f);
            int displayDeg = Mathf.RoundToInt(norm) % 360;
            int cardIdx = Mathf.RoundToInt(norm / 45f) % 8;

            if (compassHeaderLabel != null)
            {
                compassHeaderLabel.text = $"LOCAL · {CardinalNames[cardIdx]} · {displayDeg:000}°";
            }

            if (compassTicksGraphic != null)
            {
                compassTicksGraphic.YawDeg = norm;
            }

            if (compassStripRect != null)
            {
                float stripWidth = compassStripRect.rect.width > 10f ? compassStripRect.rect.width : 332f;
                for (int i = 0; i < CardinalBearings.Length; i++)
                {
                    Text lbl = compassCardinalLabels[i];
                    if (lbl == null)
                    {
                        continue;
                    }

                    float delta = Mathf.DeltaAngle(norm, CardinalBearings[i]);
                    float x = (delta / 180f) * stripWidth;
                    bool visible = Mathf.Abs(delta) <= 95f;
                    lbl.gameObject.SetActive(visible);
                    if (visible)
                    {
                        lbl.rectTransform.anchoredPosition = new Vector2(x, -2f);
                    }
                }
            }
        }

        private Transform ResolveCameraTransform()
        {
            if (targetCamera != null)
            {
                return targetCamera;
            }

            Camera mainCam = Camera.main;
            return mainCam != null ? mainCam.transform : null;
        }

        private string PickIconForRow(string rowText)
        {
            string lower = (rowText ?? string.Empty).ToLowerInvariant();
            if (lower.Contains("scan")) return "scan";
            if (lower.Contains("depth")) return "depth";
            if (lower.Contains("link") || lower.Contains("net") || lower.Contains("ping") || lower.Contains("uplink")) return "link";
            if (lower.Contains("power") || lower.Contains("batt")) return "power";
            if (lower.Contains("voice") || lower.Contains("mic") || lower.Contains("asr")) return "voice";
            return "dot";
        }

        private Sprite LoadIconSprite(string iconName)
        {
            if (string.IsNullOrWhiteSpace(iconName))
            {
                iconName = "dot";
            }

            if (iconCache.TryGetValue(iconName, out Sprite cached) && cached != null)
            {
                return cached;
            }

            Texture2D tex = Resources.Load<Texture2D>($"ArescopeIcons/{iconName}");
            if (tex == null && !string.Equals(iconName, "dot", StringComparison.OrdinalIgnoreCase))
            {
                tex = Resources.Load<Texture2D>("ArescopeIcons/dot");
            }

            if (tex == null)
            {
                return null;
            }

            Sprite created = Sprite.Create(
                tex,
                new Rect(0f, 0f, tex.width, tex.height),
                new Vector2(0.5f, 0.5f),
                100f);
            iconCache[iconName] = created;
            return created;
        }

        private static List<Vector2> BuildPreviewContacts()
        {
            return new List<Vector2>
            {
                new Vector2(-2.6f, 3.8f),
                new Vector2(2.4f, 4.9f),
                new Vector2(-4.1f, -1.8f),
                new Vector2(5.2f, -2.7f),
                new Vector2(0.8f, 7.1f)
            };
        }

        private static List<Vector2> BuildPreviewWallPoints()
        {
            var pts = new List<Vector2>(128);
            // Perimeter room outline ~6 x 5 m with door gap on -Z wall.
            for (float x = -3.0f; x <= 3.0f; x += 0.35f)
            {
                pts.Add(new Vector2(x, 2.5f));
                if (Mathf.Abs(x - 0.5f) > 0.55f)
                {
                    pts.Add(new Vector2(x, -2.5f));
                }
            }
            for (float z = -2.5f; z <= 2.5f; z += 0.35f)
            {
                pts.Add(new Vector2(-3.0f, z));
                pts.Add(new Vector2(3.0f, z));
            }
            // Interior obstacle outline kept away from center chevron.
            for (float x = 1.2f; x <= 2.4f; x += 0.3f)
            {
                pts.Add(new Vector2(x, 1.1f));
                pts.Add(new Vector2(x, 1.8f));
            }
            return pts;
        }
    }
}
