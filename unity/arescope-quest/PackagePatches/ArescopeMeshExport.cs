using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;
using Arescope;

namespace Genesis.RoomScan
{
    public sealed class ArescopeMeshData
    {
        public Vector3[] Positions, Normals;
        public Color32[] Colors;
        public int[] Indices;
        public int VertexCount => Positions?.Length ?? 0;
        public int IndexCount => Indices?.Length ?? 0;
    }

    public static class ArescopeMeshExport
    {
        public static string LastReason { get; private set; } = "not read";
        public static async Task<ArescopeMeshData> ReadAsync(int maxVertices = 200000, int maxIndices = 600000, float maxEdge = .5f)
        {
            await ArescopeLiveCloud.Gate.WaitAsync();
            try
            {
                var extractor = MeshExtractor.Instance;
                if (extractor?.GpuSurfaceNets == null) { LastReason = "surface unavailable"; return null; }
                uint[] counters = null;
                for (int attempt=0; attempt<3; ++attempt)
                {
                    extractor.ExtractForAuthoring();
                    await Task.Yield();
                    var current = extractor.GpuSurfaceNets;
                    if (current == null) { LastReason = "surface released during extraction"; return null; }
                    counters = await ArescopeLiveCloud.ReadAsync<uint>(current.CountersBuffer,4,4);
                    if (counters[0]>0 && counters[1]>=3) break;
                }
                var surface = extractor.GpuSurfaceNets;
                if (surface == null) { LastReason = "surface released"; return null; }
                int n = ArescopeLiveCloud.Clamp(counters[0],surface.VertexBuffer,maxVertices,48);
                int ni = ArescopeLiveCloud.Clamp(counters[1],surface.IndexBuffer,maxIndices,4)/3*3;
                if (n==0 || ni==0) { LastReason = "zero counters: vertices="+n+" indices="+ni; return null; }
                var vertices = await ArescopeLiveCloud.ReadAsync<ArescopeLiveCloud.VertexRecord>(surface.VertexBuffer,n,48);
                var indices = await ArescopeLiveCloud.ReadAsync<uint>(surface.IndexBuffer,ni,4);
                var p = new Vector3[n]; var normals = new Vector3[n]; var colors = new Color32[n]; var math = new Float3[n];
                for (int i=0;i<n;++i)
                {
                    p[i]=vertices[i].Position; normals[i]=vertices[i].Normal;
                    colors[i]=ArescopeLiveCloud.Color(vertices[i].PackedColor);
                    math[i]=new Float3(p[i].x,p[i].y,p[i].z);
                }
                var filtered = TriangleFilterMath.Filter(math,indices,maxEdge);
                Debug.Log("[ARS] mesh-filter | "+filtered);
                LastReason = filtered.Kept>0 ? "ok: "+filtered : "no valid triangles: "+filtered;
                if(filtered.Kept==0) return null;
                // Unreferenced corrupt vertices must not poison bounds or ARSM validation.
                var remap=new Dictionary<int,int>(); var compactP=new List<Vector3>();
                var compactN=new List<Vector3>(); var compactC=new List<Color32>();
                for(int i=0;i<filtered.Indices.Length;++i)
                {
                    int old=filtered.Indices[i];
                    if(!remap.TryGetValue(old,out int mapped))
                    { mapped=compactP.Count; remap.Add(old,mapped); compactP.Add(p[old]); compactN.Add(normals[old]); compactC.Add(colors[old]); }
                    filtered.Indices[i]=mapped;
                }
                return new ArescopeMeshData { Positions=compactP.ToArray(), Normals=compactN.ToArray(), Colors=compactC.ToArray(), Indices=filtered.Indices };
            }
            catch(Exception e) { LastReason="mesh: "+e.Message; return null; }
            finally { ArescopeLiveCloud.Gate.Release(); }
        }
    }
}
