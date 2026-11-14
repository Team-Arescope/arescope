using System;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Rendering;

namespace Genesis.RoomScan
{
    // Installed into Runtime/Utils: GPUSurfaceNets is internal to this assembly.
    public static class ArescopeLiveCloud
    {
        public const int MaxReadbackBytes = 12 * 1024 * 1024;
        public const int VertexStride = 48, VertexPosOffset = 0, VertexNormalOffset = 24, VertexPackedColorOffset = 36;
        internal static readonly SemaphoreSlim Gate = new SemaphoreSlim(1, 1);
        public static string LastReason { get; internal set; } = "not sampled";
        public static bool Ready => MeshExtractor.Instance != null && MeshExtractor.Instance.GpuSurfaceNets?.VertexBuffer != null;

        [StructLayout(LayoutKind.Sequential, Pack = 4, Size = VertexStride)]
        internal struct VertexRecord
        {
            public Vector3 Position;      // byte 0
            public Vector3 Previous;      // byte 12
            public Vector3 Normal;        // byte 24
            public uint PackedColor;      // byte 36 (0xAABBGGRR)
            public float Birth, Reserved; // byte 40,44
        }
        internal static Color32 Color(uint c) => new Color32((byte)c, (byte)(c>>8), (byte)(c>>16), (byte)(c>>24));
        internal static bool Finite(Vector3 p) => Arescope.Float3.Finite(p.x) && Arescope.Float3.Finite(p.y) && Arescope.Float3.Finite(p.z);
        internal static int Clamp(uint used, GraphicsBuffer buffer, int requested, int stride)
        {
            if (buffer == null || !buffer.IsValid() || requested <= 0) return 0;
            return (int)Math.Min((long)used, Math.Min(buffer.count, Math.Min((long)requested, MaxReadbackBytes / stride)));
        }
        internal static async Task<T[]> ReadAsync<T>(GraphicsBuffer buffer, int count, int stride) where T : struct
        {
            if (buffer == null || !buffer.IsValid() || count < 0 || count > buffer.count || (long)count*stride > MaxReadbackBytes)
                throw new InvalidOperationException("invalid readback range");
            if (count == 0) return new T[0];
            string fallback = "async unsupported";
            if (SystemInfo.supportsAsyncGPUReadback)
            {
                try
                {
                    var request = await AsyncGPUReadback.RequestAsync(buffer, checked(count*stride), 0);
                    if (!request.hasError)
                    {
                        var data = request.GetData<T>();
                        if (data.Length >= count)
                        {
                            var copy = new T[count];
                            // NativeArray belongs to this request: copy before the next await.
                            for (int i=0; i<count; ++i) copy[i]=data[i];
                            return copy;
                        }
                        fallback = "short async read";
                    }
                    else fallback = "async hasError";
                }
                catch (Exception e) { fallback = e.GetType().Name; }
            }
            if (!buffer.IsValid()) throw new InvalidOperationException("buffer released before fallback");
            var result = new T[count];
            // Element type matches the structured buffer stride, including 48-byte vertices.
            buffer.GetData(result, 0, 0, count);
            Debug.LogWarning("[ARS] readback | GetData fallback: " + fallback);
            return result;
        }
        public static Task<int> SampleAsync(Vector3[] destination, int maxPoints) => SampleAsync(destination, null, maxPoints);
        public static async Task<int> SampleAsync(Vector3[] destination, Color32[] colors, int maxPoints)
        {
            if (destination == null || maxPoints <= 0) { LastReason = "empty destination"; return 0; }
            if (!Gate.Wait(0)) { LastReason = "readback busy"; return 0; }
            try
            {
                var extractor = MeshExtractor.Instance;
                var surface = extractor?.GpuSurfaceNets;
                if (surface == null) { LastReason = "surface unavailable"; return 0; }
                var counters = await ReadAsync<uint>(surface.CountersBuffer, 4, 4);
                int count = Clamp(counters[0], surface.VertexBuffer, int.MaxValue, VertexStride);
                if (count == 0) { LastReason = "zero vertex counter"; return 0; }
                var vertices = await ReadAsync<VertexRecord>(surface.VertexBuffer, count, VertexStride);
                int wanted = Math.Min(maxPoints, destination.Length);
                if (colors != null) wanted = Math.Min(wanted, colors.Length);
                if (wanted <= 0) { LastReason = "empty colors destination"; return 0; }
                int step = Math.Max(1, (count+wanted-1)/wanted), written = 0;
                for (int i=0; i<count && written<wanted; i+=step)
                {
                    if (!Finite(vertices[i].Position)) continue;
                    destination[written] = vertices[i].Position;
                    if (colors != null) colors[written] = Color(vertices[i].PackedColor);
                    ++written;
                }
                LastReason = written > 0 ? "ok" : "no finite points";
                return written;
            }
            catch (Exception e) { LastReason = "sample: " + e.Message; return 0; }
            finally { Gate.Release(); }
        }
    }
}
