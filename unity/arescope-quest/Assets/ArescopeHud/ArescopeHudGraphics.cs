using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace Arescope.Hud
{
    internal static class HudMeshUtil
    {
        public static void AddQuad(
            VertexHelper vh,
            Vector2 p0,
            Vector2 p1,
            Vector2 p2,
            Vector2 p3,
            Color32 c)
        {
            int idx = vh.currentVertCount;
            vh.AddVert(new Vector3(p0.x, p0.y, 0f), c, Vector2.zero);
            vh.AddVert(new Vector3(p1.x, p1.y, 0f), c, Vector2.zero);
            vh.AddVert(new Vector3(p2.x, p2.y, 0f), c, Vector2.zero);
            vh.AddVert(new Vector3(p3.x, p3.y, 0f), c, Vector2.zero);
            vh.AddTriangle(idx, idx + 1, idx + 2);
            vh.AddTriangle(idx, idx + 2, idx + 3);
        }

        public static void AddAxisRect(VertexHelper vh, float xMin, float yMin, float xMax, float yMax, Color32 c)
        {
            AddQuad(vh,
                new Vector2(xMin, yMin),
                new Vector2(xMin, yMax),
                new Vector2(xMax, yMax),
                new Vector2(xMax, yMin),
                c);
        }
    }

    /// <summary>
    /// Draws a translucent chamfered card fill, an inset 8-segment chamfered border ring,
    /// and an optional 2-unit copper top rule in a single mesh without UI Outline.
    /// </summary>
    [RequireComponent(typeof(CanvasRenderer))]
    public sealed class ArescopeChamferCardGraphic : MaskableGraphic
    {
        [SerializeField] private float chamferSize = 10f;
        [SerializeField] private float borderWidth = 1.25f;
        [SerializeField] private Color borderColor = new Color32(0x51, 0x30, 0x26, 0xE6);
        [SerializeField] private bool showTopRule = true;
        [SerializeField] private float topRuleHeight = 2f;
        [SerializeField] private Color topRuleColor = new Color32(0xEE, 0x8A, 0x5B, 0xFF);

        public float ChamferSize
        {
            get => chamferSize;
            set { chamferSize = Mathf.Max(0f, value); SetVerticesDirty(); }
        }

        public float BorderWidth
        {
            get => borderWidth;
            set { borderWidth = Mathf.Max(0f, value); SetVerticesDirty(); }
        }

        public Color BorderColor
        {
            get => borderColor;
            set { borderColor = value; SetVerticesDirty(); }
        }

        public bool ShowTopRule
        {
            get => showTopRule;
            set { showTopRule = value; SetVerticesDirty(); }
        }

        public float TopRuleHeight
        {
            get => topRuleHeight;
            set { topRuleHeight = Mathf.Max(0f, value); SetVerticesDirty(); }
        }

        public Color TopRuleColor
        {
            get => topRuleColor;
            set { topRuleColor = value; SetVerticesDirty(); }
        }

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            Rect r = GetPixelAdjustedRect();
            if (r.width <= 1f || r.height <= 1f)
            {
                return;
            }

            float ch = Mathf.Min(chamferSize, Mathf.Min(r.width, r.height) * 0.45f);
            float bw = Mathf.Min(borderWidth, Mathf.Min(r.width, r.height) * 0.25f);

            Vector2[] outer = BuildChamferLoop(r.xMin, r.yMin, r.xMax, r.yMax, ch);
            float innerCh = Mathf.Max(0f, ch - bw * 0.41421356f);
            Vector2[] inner = BuildChamferLoop(r.xMin + bw, r.yMin + bw, r.xMax - bw, r.yMax - bw, innerCh);

            // Fill inner chamfered octagon with triangle fan from center.
            Color32 fillC = color;
            Vector2 center = r.center;
            int centerIdx = vh.currentVertCount;
            vh.AddVert(new Vector3(center.x, center.y, 0f), fillC, new Vector2(0.5f, 0.5f));
            for (int i = 0; i < 8; i++)
            {
                vh.AddVert(new Vector3(inner[i].x, inner[i].y, 0f), fillC, Vector2.zero);
            }
            for (int i = 0; i < 8; i++)
            {
                int a = centerIdx + 1 + i;
                int b = centerIdx + 1 + ((i + 1) % 8);
                vh.AddTriangle(centerIdx, a, b);
            }

            // Border ring stitched between outer and inner 8-vertex loops.
            if (bw > 0f && borderColor.a > 0f)
            {
                Color32 borderC = borderColor;
                int ringBase = vh.currentVertCount;
                for (int i = 0; i < 8; i++)
                {
                    vh.AddVert(new Vector3(outer[i].x, outer[i].y, 0f), borderC, Vector2.zero);
                    vh.AddVert(new Vector3(inner[i].x, inner[i].y, 0f), borderC, Vector2.zero);
                }
                for (int i = 0; i < 8; i++)
                {
                    int next = (i + 1) % 8;
                    int o0 = ringBase + i * 2;
                    int i0 = ringBase + i * 2 + 1;
                    int o1 = ringBase + next * 2;
                    int i1 = ringBase + next * 2 + 1;
                    vh.AddTriangle(o0, o1, i1);
                    vh.AddTriangle(o0, i1, i0);
                }
            }

            if (showTopRule && topRuleHeight > 0f && topRuleColor.a > 0f)
            {
                float x0 = r.xMin + Mathf.Max(ch, 6f);
                float x1 = r.xMax - Mathf.Max(ch, 6f);
                if (x1 > x0)
                {
                    float yTop = r.yMax - bw;
                    float yBot = Mathf.Max(r.yMin + bw, yTop - topRuleHeight);
                    HudMeshUtil.AddAxisRect(vh, x0, yBot, x1, yTop, topRuleColor);
                }
            }
        }

        private static Vector2[] BuildChamferLoop(float xMin, float yMin, float xMax, float yMax, float ch)
        {
            return new[]
            {
                new Vector2(xMin + ch, yMax),
                new Vector2(xMax - ch, yMax),
                new Vector2(xMax, yMax - ch),
                new Vector2(xMax, yMin + ch),
                new Vector2(xMax - ch, yMin),
                new Vector2(xMin + ch, yMin),
                new Vector2(xMin, yMin + ch),
                new Vector2(xMin, yMax - ch)
            };
        }
    }

    /// <summary>
    /// 56-segment circular fan + rim annulus in a single mesh. Pair with Mask(showMaskGraphic=true).
    /// Contains no grid and no top copper hairline.
    /// </summary>
    [RequireComponent(typeof(CanvasRenderer))]
    public sealed class ArescopeCircleCardGraphic : MaskableGraphic
    {
        public const int SegmentCount = 56;

        [SerializeField] private float borderWidth = 1.5f;
        [SerializeField] private Color borderColor = new Color32(0x51, 0x30, 0x26, 0xE6);

        public float BorderWidth
        {
            get => borderWidth;
            set { borderWidth = Mathf.Max(0f, value); SetVerticesDirty(); }
        }

        public Color BorderColor
        {
            get => borderColor;
            set { borderColor = value; SetVerticesDirty(); }
        }

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            Rect r = GetPixelAdjustedRect();
            float outerRadius = Mathf.Min(r.width, r.height) * 0.5f;
            if (outerRadius <= 1f)
            {
                return;
            }

            float bw = Mathf.Clamp(borderWidth, 0f, outerRadius * 0.25f);
            float innerRadius = Mathf.Max(0.5f, outerRadius - bw);
            Vector2 center = r.center;

            Color32 fillC = color;
            int centerIdx = vh.currentVertCount;
            vh.AddVert(new Vector3(center.x, center.y, 0f), fillC, new Vector2(0.5f, 0.5f));
            for (int i = 0; i < SegmentCount; i++)
            {
                float a = (i / (float)SegmentCount) * Mathf.PI * 2f;
                Vector2 pt = center + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * innerRadius;
                vh.AddVert(new Vector3(pt.x, pt.y, 0f), fillC, Vector2.zero);
            }
            for (int i = 0; i < SegmentCount; i++)
            {
                int a = centerIdx + 1 + i;
                int b = centerIdx + 1 + ((i + 1) % SegmentCount);
                vh.AddTriangle(centerIdx, b, a);
            }

            if (bw > 0f && borderColor.a > 0f)
            {
                Color32 rimC = borderColor;
                int rimBase = vh.currentVertCount;
                for (int i = 0; i < SegmentCount; i++)
                {
                    float a = (i / (float)SegmentCount) * Mathf.PI * 2f;
                    Vector2 dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
                    Vector2 pOut = center + dir * outerRadius;
                    Vector2 pIn = center + dir * innerRadius;
                    vh.AddVert(new Vector3(pOut.x, pOut.y, 0f), rimC, Vector2.zero);
                    vh.AddVert(new Vector3(pIn.x, pIn.y, 0f), rimC, Vector2.zero);
                }
                for (int i = 0; i < SegmentCount; i++)
                {
                    int next = (i + 1) % SegmentCount;
                    int o0 = rimBase + i * 2;
                    int i0 = rimBase + i * 2 + 1;
                    int o1 = rimBase + next * 2;
                    int i1 = rimBase + next * 2 + 1;
                    vh.AddTriangle(o0, i1, o1);
                    vh.AddTriangle(o0, i0, i1);
                }
            }
        }
    }

    /// <summary>
    /// Single-mesh compass bearing ruler emitting 5/15/45 deg ticks at uniform Rule color and alpha,
    /// differing only in tick geometry, plus a fixed center lubber mark.
    /// </summary>
    [RequireComponent(typeof(CanvasRenderer))]
    public sealed class ArescopeCompassTicksGraphic : MaskableGraphic
    {
        [SerializeField] private float yawDeg;
        [SerializeField] private float stripSpanDeg = 180f;
        [SerializeField] private Color lubberColor = new Color32(0xF5, 0xE8, 0xDF, 0xFF);

        public float YawDeg
        {
            get => yawDeg;
            set { yawDeg = value; SetVerticesDirty(); }
        }

        public float StripSpanDeg
        {
            get => stripSpanDeg;
            set { stripSpanDeg = Mathf.Max(30f, value); SetVerticesDirty(); }
        }

        public Color LubberColor
        {
            get => lubberColor;
            set { lubberColor = value; SetVerticesDirty(); }
        }

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            Rect r = GetPixelAdjustedRect();
            if (r.width <= 4f || r.height <= 4f)
            {
                return;
            }

            float halfWidth = r.width * 0.5f;
            float baseY = r.yMin + 2f;
            Color32 tickC = color;

            for (int deg = 0; deg < 360; deg += 5)
            {
                float delta = Mathf.DeltaAngle(yawDeg, deg);
                float x = r.center.x + (delta / stripSpanDeg) * r.width;
                bool isCardinal = (deg % 45) == 0;
                bool isMedium = !isCardinal && (deg % 15) == 0;

                float tickWidth = isCardinal ? 2.2f : (isMedium ? 1.4f : 1.1f);
                float tickHeight = isCardinal ? 16f : (isMedium ? 11f : 6f);
                float halfT = tickWidth * 0.5f;

                if (x + halfT < r.xMin || x - halfT > r.xMax)
                {
                    continue;
                }

                float x0 = Mathf.Max(r.xMin, x - halfT);
                float x1 = Mathf.Min(r.xMax, x + halfT);
                float y1 = Mathf.Min(r.yMax, baseY + tickHeight);
                if (x1 > x0 && y1 > baseY)
                {
                    HudMeshUtil.AddAxisRect(vh, x0, baseY, x1, y1, tickC);
                }
            }

            // Fixed center lubber marker.
            float lubberHalfW = 1.0f;
            float lubberTop = Mathf.Min(r.yMax, baseY + 19f);
            HudMeshUtil.AddAxisRect(vh, r.center.x - lubberHalfW, baseY - 1f, r.center.x + lubberHalfW, lubberTop, lubberColor);
        }
    }

    /// <summary>
    /// Car-navigation-style chevron position marker at minimap center.
    /// </summary>
    [RequireComponent(typeof(CanvasRenderer))]
    public sealed class ArescopeChevronGraphic : MaskableGraphic
    {
        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            Rect r = GetPixelAdjustedRect();
            Vector2 c = r.center;
            float hw = r.width * 0.45f;
            float hh = r.height * 0.48f;
            Color32 col = color;

            Vector2 tip = new Vector2(c.x, c.y + hh);
            Vector2 leftWing = new Vector2(c.x - hw, c.y - hh);
            Vector2 notch = new Vector2(c.x, c.y - hh * 0.42f);
            Vector2 rightWing = new Vector2(c.x + hw, c.y - hh);

            vh.AddVert(new Vector3(tip.x, tip.y, 0f), col, Vector2.zero);
            vh.AddVert(new Vector3(leftWing.x, leftWing.y, 0f), col, Vector2.zero);
            vh.AddVert(new Vector3(notch.x, notch.y, 0f), col, Vector2.zero);
            vh.AddVert(new Vector3(rightWing.x, rightWing.y, 0f), col, Vector2.zero);

            vh.AddTriangle(0, 2, 1);
            vh.AddTriangle(0, 3, 2);
        }
    }

    /// <summary>
    /// Single-mesh minimap point renderer (192 scanCloud / 64 contacts cap) scaled around map center.
    /// </summary>
    [RequireComponent(typeof(CanvasRenderer))]
    public sealed class ArescopeMapPointsGraphic : MaskableGraphic
    {
        private readonly List<Vector2> points = new List<Vector2>(192);
        private float rangeMeters = 10f;
        private float scaleUnitsPerTenMeters = 74f;
        private float dotRadius = 1.6f;

        public void SetPoints(IReadOnlyList<Vector2> sourcePoints, float range, bool scanCloud, float unitsPer10M)
        {
            points.Clear();
            rangeMeters = Mathf.Max(0.5f, range);
            scaleUnitsPerTenMeters = unitsPer10M;
            int cap = scanCloud ? 192 : 64;
            dotRadius = scanCloud ? 1.6f : 4.0f;

            if (sourcePoints != null && sourcePoints.Count > 0)
            {
                int total = sourcePoints.Count;
                if (total <= cap)
                {
                    for (int i = 0; i < total; i++)
                    {
                        points.Add(sourcePoints[i]);
                    }
                }
                else
                {
                    for (int i = 0; i < cap; i++)
                    {
                        int idx = Mathf.FloorToInt((i / (float)cap) * total);
                        points.Add(sourcePoints[Mathf.Clamp(idx, 0, total - 1)]);
                    }
                }
            }

            SetVerticesDirty();
        }

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            if (points.Count == 0)
            {
                return;
            }

            Rect r = GetPixelAdjustedRect();
            Vector2 center = r.center;
            float scale = scaleUnitsPerTenMeters / rangeMeters;
            float rangeSq = rangeMeters * rangeMeters;
            Color32 col = color;

            for (int i = 0; i < points.Count; i++)
            {
                Vector2 p = points[i];
                if (p.sqrMagnitude > rangeSq)
                {
                    continue;
                }

                Vector2 pos = center + p * scale;
                HudMeshUtil.AddAxisRect(
                    vh,
                    pos.x - dotRadius,
                    pos.y - dotRadius,
                    pos.x + dotRadius,
                    pos.y + dotRadius,
                    col);
            }
        }
    }

    /// <summary>
    /// Single-mesh 5-bar voice amplitude meter.
    /// </summary>
    [RequireComponent(typeof(CanvasRenderer))]
    public sealed class ArescopeVoiceMeterGraphic : MaskableGraphic
    {
        [SerializeField] private float level;
        [SerializeField] private Color inactiveColor = new Color32(0x51, 0x30, 0x26, 0x99);

        public float Level
        {
            get => level;
            set { level = Mathf.Clamp01(value); SetVerticesDirty(); }
        }

        public Color InactiveColor
        {
            get => inactiveColor;
            set { inactiveColor = value; SetVerticesDirty(); }
        }

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            Rect r = GetPixelAdjustedRect();
            const int bars = 5;
            float gap = 3f;
            float barW = Mathf.Max(2f, (r.width - gap * (bars - 1)) / bars);
            int litCount = level <= 0.01f ? 0 : Mathf.Clamp(Mathf.CeilToInt(level * bars), 1, bars);
            Color32 activeC = color;
            Color32 dimC = inactiveColor;

            for (int i = 0; i < bars; i++)
            {
                float frac = (i + 1) / (float)bars;
                float barH = Mathf.Lerp(r.height * 0.35f, r.height, frac);
                float x0 = r.xMin + i * (barW + gap);
                float y0 = r.yMin;
                HudMeshUtil.AddAxisRect(vh, x0, y0, x0 + barW, y0 + barH, i < litCount ? activeC : dimC);
            }
        }
    }
}
