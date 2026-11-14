// Dependency-free kernels. Matrices use row-major storage and column vectors.
using System;
using System.Collections.Generic;
using System.IO;

namespace Arescope
{
    public enum ViewMode { Passthrough, Mixed, Scan }

    public static class ModePolicyMath
    {
        public static bool CanSwitch(ViewMode mode, bool hasScan)
        {
            return mode == ViewMode.Passthrough ||
                (hasScan && (mode == ViewMode.Mixed || mode == ViewMode.Scan));
        }
        public static bool ShowsScan(ViewMode mode) { return mode == ViewMode.Mixed || mode == ViewMode.Scan; }
        public static bool ShowsPassthrough(ViewMode mode) { return mode != ViewMode.Scan; }
        public static ViewMode Next(ViewMode mode) { return (ViewMode)(((int)mode + 1) % 3); }
    }

    public struct Float3
    {
        public float X, Y, Z;
        public Float3(float x, float y, float z) { X = x; Y = y; Z = z; }
        public bool IsFinite { get { return Finite(X) && Finite(Y) && Finite(Z); } }
        public static bool Finite(float value) { return !float.IsNaN(value) && !float.IsInfinity(value); }
    }

    public sealed class TriangleFilterResult
    {
        public int[] Indices;
        public int Raw, Kept, Degenerate, Stretched, OutOfRange, NonFinite;
        public float MedianEdge, Limit;
        public override string ToString()
        {
            return string.Format(System.Globalization.CultureInfo.InvariantCulture,
                "raw={0} kept={1} degenerate={2} stretched={3} outOfRange={4} nonFinite={5} median={6:F4} limit={7:F4}",
                Raw, Kept, Degenerate, Stretched, OutOfRange, NonFinite, MedianEdge, Limit);
        }
    }

    public static class TriangleFilterMath
    {
        static float Distance(Float3 a, Float3 b)
        {
            double x = (double)a.X - b.X, y = (double)a.Y - b.Y, z = (double)a.Z - b.Z;
            return (float)Math.Sqrt(x*x + y*y + z*z);
        }
        static bool Valid(uint a, uint b, uint c, int n) { return a < n && b < n && c < n; }
        static bool ZeroArea(Float3 a, Float3 b, Float3 c)
        {
            double x = b.X-a.X, y = b.Y-a.Y, z = b.Z-a.Z;
            double u = c.X-a.X, v = c.Y-a.Y, w = c.Z-a.Z;
            double cx = y*w-z*v, cy = z*u-x*w, cz = x*v-y*u;
            return cx*cx+cy*cy+cz*cz <= 1e-20;
        }
        public static TriangleFilterResult Filter(Float3[] positions, uint[] indices, float maxEdge = .5f)
        {
            if (positions == null || indices == null) throw new ArgumentNullException();
            if (!Float3.Finite(maxEdge) || maxEdge <= 0) throw new ArgumentOutOfRangeException("maxEdge");
            var result = new TriangleFilterResult { Raw = indices.Length / 3 };
            var edges = new List<float>(60000);
            int step = Math.Max(1, (result.Raw + 19999) / 20000);
            for (int t = 0; t < result.Raw && edges.Count < 60000; t += step)
            {
                uint a = indices[t*3], b = indices[t*3+1], c = indices[t*3+2];
                if (!Valid(a,b,c,positions.Length) || a == b || a == c || b == c) continue;
                if (!positions[a].IsFinite || !positions[b].IsFinite || !positions[c].IsFinite) continue;
                if (ZeroArea(positions[a],positions[b],positions[c])) continue;
                edges.Add(Distance(positions[a],positions[b]));
                edges.Add(Distance(positions[b],positions[c]));
                edges.Add(Distance(positions[c],positions[a]));
            }
            edges.Sort();
            result.MedianEdge = edges.Count == 0 ? .02f : edges[edges.Count/2];
            result.Limit = Math.Min(maxEdge, Math.Max(.06f, Math.Min(.30f, result.MedianEdge*4)));
            var kept = new List<int>(indices.Length);
            for (int t = 0; t < result.Raw; ++t)
            {
                uint a = indices[t*3], b = indices[t*3+1], c = indices[t*3+2];
                if (!Valid(a,b,c,positions.Length)) { ++result.OutOfRange; continue; }
                if (a == b || a == c || b == c) { ++result.Degenerate; continue; }
                if (!positions[a].IsFinite || !positions[b].IsFinite || !positions[c].IsFinite)
                { ++result.NonFinite; continue; }
                if (ZeroArea(positions[a],positions[b],positions[c])) { ++result.Degenerate; continue; }
                if (Distance(positions[a],positions[b]) > result.Limit ||
                    Distance(positions[b],positions[c]) > result.Limit || Distance(positions[c],positions[a]) > result.Limit)
                { ++result.Stretched; continue; }
                kept.Add((int)a); kept.Add((int)b); kept.Add((int)c); ++result.Kept;
            }
            result.Indices = kept.ToArray();
            return result;
        }
    }

    public static class MinimapProjectionMath
    {
        public static bool TryProject(Float3 point, Float3 head, Float3 forward,
            out float right, out float ahead, float range = 10, float heightBand = .03f)
        {
            right = ahead = 0;
            if (!point.IsFinite || !head.IsFinite || !forward.IsFinite || range <= 0 || heightBand < 0) return false;
            float dx=point.X-head.X, dy=point.Y-head.Y, dz=point.Z-head.Z;
            if (Math.Abs(dy) > heightBand) return false;
            double length = Math.Sqrt((double)forward.X*forward.X+(double)forward.Z*forward.Z);
            float fx = length < 1e-6 ? 0 : (float)(forward.X/length);
            float fz = length < 1e-6 ? 1 : (float)(forward.Z/length);
            right = dx*fz-dz*fx; ahead = dx*fx+dz*fz;
            return (double)right*right+(double)ahead*ahead <= (double)range*range;
        }
        public static long VoxelKey(Float3 p, float voxel = .035f)
        {
            if (!p.IsFinite || !Float3.Finite(voxel) || voxel <= 0) throw new ArgumentOutOfRangeException("p");
            const long mask = (1L<<21)-1;
            long x=(long)Math.Floor(p.X/voxel), y=(long)Math.Floor(p.Y/voxel), z=(long)Math.Floor(p.Z/voxel);
            if (x < -(1L<<20) || x >= (1L<<20) || y < -(1L<<20) || y >= (1L<<20) || z < -(1L<<20) || z >= (1L<<20))
                throw new ArgumentOutOfRangeException("p", "Voxel exceeds signed 21-bit range");
            return (x&mask)<<42 | (y&mask)<<21 | (z&mask);
        }
    }

    public static class ArsmEncoder
    {
        public const int MaxBytes = 32*1024*1024;
        static readonly byte[] PngMagic = {137,80,78,71,13,10,26,10};
        static void Require(bool test, string reason) { if (!test) throw new ArgumentException(reason); }
        static bool Png(byte[] png, int width, int height)
        {
            if (png == null || png.Length < 33) return false;
            for (int i=0;i<8;++i) if (png[i] != PngMagic[i]) return false;
            return png[12]==73 && png[13]==72 && png[14]==68 && png[15]==82 &&
                Big32(png,16)==width && Big32(png,20)==height;
        }
        static long Big32(byte[] a, int p) { return ((long)a[p]<<24)|((long)a[p+1]<<16)|((long)a[p+2]<<8)|a[p+3]; }
        public static byte[] Encode(Float3[] positions, byte[] rgba, uint[] indices,
            float[] uv = null, int atlasWidth = 0, int atlasHeight = 0, byte[] png = null)
        {
            Require(positions != null && positions.Length > 0 && positions.Length <= 400000, "vertex count");
            Require(rgba != null && (long)rgba.Length == (long)positions.Length*4, "RGBA length");
            Require(indices != null && indices.Length > 0 && indices.Length%3 == 0, "triangle indices");
            for(int i=0;i<positions.Length;++i) Require(positions[i].IsFinite, "non-finite position");
            for(int i=0;i<indices.Length;++i) Require(indices[i] < positions.Length, "index out of range");
            bool v2 = uv != null;
            long length = 16L+positions.Length*16L+indices.Length*4L;
            if(v2)
            {
                Require(uv.Length == positions.Length*2 && atlasWidth > 0 && atlasHeight > 0 && atlasWidth<=16384 && atlasHeight<=16384, "atlas/UV shape");
                for(int i=0;i<uv.Length;++i) Require(Float3.Finite(uv[i]), "non-finite UV");
                Require(Png(png,atlasWidth,atlasHeight) && png.Length<=24*1024*1024, "PNG header/dimensions or 24 MiB cap");
                length += positions.Length*8L+12+png.Length;
            }
            Require(length <= MaxBytes, "ARSM exceeds 32 MiB");
            using(var stream=new MemoryStream((int)length))
            using(var w=new BinaryWriter(stream))
            {
                w.Write(new byte[]{65,82,83,77}); w.Write(v2 ? 2u : 1u);
                w.Write((uint)positions.Length); w.Write((uint)indices.Length);
                foreach(var p in positions) { w.Write(p.X); w.Write(p.Y); w.Write(p.Z); }
                w.Write(rgba); foreach(uint i in indices) w.Write(i);
                if(v2) { foreach(float f in uv) w.Write(f); w.Write((uint)atlasWidth); w.Write((uint)atlasHeight); w.Write((uint)png.Length); w.Write(png); }
                return stream.ToArray();
            }
        }
        public static bool TryValidate(byte[] bytes, out string reason)
        {
            reason = null;
            try
            {
                Require(bytes != null && bytes.Length >= 16 && bytes.Length <= MaxBytes, "body size");
                using(var r=new BinaryReader(new MemoryStream(bytes,false)))
                {
                    Require(r.ReadUInt32()==0x4D535241, "magic");
                    uint version=r.ReadUInt32(), n=r.ReadUInt32(), count=r.ReadUInt32();
                    Require((version==1 || version==2) && n>0 && n<=400000 && count>0 && count%3==0, "header");
                    long end=16L+n*16L+count*4L;
                    Require(end<=bytes.Length, "truncated geometry");
                    for(long j=0;j<n*3L;++j) Require(Float3.Finite(r.ReadSingle()), "position");
                    r.BaseStream.Position += n*4L;
                    for(long j=0;j<count;++j) Require(r.ReadUInt32()<n, "index");
                    if(version==2)
                    {
                        Require(end+n*8L+12<=bytes.Length, "truncated UV");
                        for(long j=0;j<n*2L;++j) Require(Float3.Finite(r.ReadSingle()), "UV");
                        uint width=r.ReadUInt32(), height=r.ReadUInt32(), size=r.ReadUInt32();
                        Require(width>0 && width<=16384 && height>0 && height<=16384 && size<=24*1024*1024, "atlas");
                        Require(r.BaseStream.Position+size==bytes.Length, "atlas length");
                        Require(Png(r.ReadBytes((int)size),(int)width,(int)height), "PNG");
                    }
                    Require(r.BaseStream.Position==bytes.Length, "trailing data");
                }
                return true;
            }
            catch(Exception e) { reason=e.Message; return false; }
        }
    }

    public static class ArescopeFrameMath
    {
        public static float[] Identity() { return new float[]{1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1}; }
        static void Check(float[] m)
        {
            if(m==null || m.Length!=16) throw new ArgumentException("4x4 matrix required");
            foreach(float f in m) if(!Float3.Finite(f)) throw new ArgumentException("non-finite matrix");
        }
        public static bool Changed(float[] a, float[] b, float threshold = .0005f)
        {
            Check(a); Check(b);
            for(int i=0;i<16;++i) if(Math.Abs(a[i]-b[i])>threshold) return true;
            return false;
        }
        public static float[] Multiply(float[] a, float[] b)
        {
            Check(a); Check(b); var c=new float[16];
            for(int i=0;i<4;++i) for(int j=0;j<4;++j) for(int k=0;k<4;++k) c[i*4+j]+=a[i*4+k]*b[k*4+j];
            return c;
        }
        public static float[] Inverse(float[] matrix)
        {
            Check(matrix); var a=new double[4,8];
            for(int i=0;i<4;++i) for(int j=0;j<4;++j) { a[i,j]=matrix[i*4+j]; a[i,j+4]=i==j?1:0; }
            for(int k=0;k<4;++k)
            {
                int pivot=k; for(int i=k+1;i<4;++i) if(Math.Abs(a[i,k])>Math.Abs(a[pivot,k])) pivot=i;
                if(Math.Abs(a[pivot,k])<1e-12) throw new ArgumentException("singular matrix");
                for(int j=0;j<8;++j) { double tmp=a[k,j]; a[k,j]=a[pivot,j]; a[pivot,j]=tmp; }
                double scale=a[k,k]; for(int j=0;j<8;++j) a[k,j]/=scale;
                for(int i=0;i<4;++i) if(i!=k) { double v=a[i,k]; for(int j=0;j<8;++j) a[i,j]-=v*a[k,j]; }
            }
            var result=new float[16]; for(int i=0;i<4;++i) for(int j=0;j<4;++j) result[i*4+j]=(float)a[i,j+4];
            return result;
        }
        public static float[] Relocation(float[] now, float[] capture) { return Multiply(now,Inverse(capture)); }
        public static Float3 Transform(float[] m, Float3 p)
        {
            Check(m);
            return new Float3(m[0]*p.X+m[1]*p.Y+m[2]*p.Z+m[3],m[4]*p.X+m[5]*p.Y+m[6]*p.Z+m[7],m[8]*p.X+m[9]*p.Y+m[10]*p.Z+m[11]);
        }
    }
}
