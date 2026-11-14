using System;
using UnityEngine;

namespace Genesis.RoomScan
{
    public sealed class ArescopeTexturedMeshData
    {
        public Vector3[] Positions, Normals;
        public Vector2[] UVs;
        public int[] Indices;
        public byte[] AtlasPng;
        public int AtlasWidth, AtlasHeight;
    }
    public static class ArescopeTexturedMesh
    {
        public static string LastReason { get; private set; } = "not read";
        // CPU snapshots stay valid after StopScanning/UnloadActiveScan.
        public static ArescopeTexturedMeshData Read(int maxVertices = 400000)
        {
            try
            {
                var scanner=RoomScanner.Instance;
                var result=scanner?.LastSimplifiedResult ?? scanner?.LastRefinedResult;
                if(!result.HasValue) { LastReason="no refined result"; return null; }
                var r=result.Value;
                if(r.Positions==null || r.Positions.Length==0 || r.Positions.Length>maxVertices ||
                    r.UVs==null || r.UVs.Length!=r.Positions.Length || r.Indices==null || r.Indices.Length==0 || r.Indices.Length%3!=0)
                { LastReason="invalid refined geometry"; return null; }
                if(r.AtlasWidth<=0 || r.AtlasHeight<=0 || r.AtlasWidth>8192 || r.AtlasHeight>8192 ||
                    r.AtlasPixels==null || (long)r.AtlasWidth*r.AtlasHeight*4!=r.AtlasPixels.Length)
                { LastReason="invalid atlas"; return null; }
                foreach(var p in r.Positions) if(!ArescopeLiveCloud.Finite(p)) { LastReason="non-finite vertex"; return null; }
                foreach(var i in r.Indices) if(i<0 || i>=r.Positions.Length) { LastReason="index out of range"; return null; }
                foreach(var uv in r.UVs) if(!Arescope.Float3.Finite(uv.x) || !Arescope.Float3.Finite(uv.y)) { LastReason="non-finite UV"; return null; }
                var atlas=new Texture2D(r.AtlasWidth,r.AtlasHeight,TextureFormat.RGBA32,false);
                byte[] png;
                try { atlas.LoadRawTextureData(r.AtlasPixels); atlas.Apply(false,false); png=atlas.EncodeToPNG(); }
                finally { UnityEngine.Object.Destroy(atlas); }
                if(png==null || png.Length>Arescope.ArsmEncoder.MaxBytes) { LastReason="atlas PNG exceeds cap"; return null; }
                LastReason="ok";
                return new ArescopeTexturedMeshData {
                    Positions=(Vector3[])r.Positions.Clone(), Normals=r.Normals==null?null:(Vector3[])r.Normals.Clone(),
                    UVs=(Vector2[])r.UVs.Clone(), Indices=(int[])r.Indices.Clone(), AtlasPng=png,
                    AtlasWidth=r.AtlasWidth, AtlasHeight=r.AtlasHeight };
            }
            catch(Exception e) { LastReason="textured: "+e.Message; return null; }
        }
    }
}
