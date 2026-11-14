using System;
using NUnit.Framework;

namespace Arescope.Tests
{
    [TestFixture] public sealed class ArsmPackingTest
    {
        static Float3[] Positions() { return new[]{new Float3(1,2,3),new Float3(4,5,6),new Float3(7,8,9)}; }
        static byte[] Colors() { return new byte[]{1,2,3,4,5,6,7,8,9,10,11,12}; }
        static readonly uint[] Indices={0,1,2};
        static byte[] V1() { return ArsmEncoder.Encode(Positions(),Colors(),Indices); }
        static byte[] V2()
        {
            byte[] png=Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nWQAAAAASUVORK5CYII=");
            return ArsmEncoder.Encode(Positions(),Colors(),Indices,new float[]{0,0,1,0,0,1},1,1,png);
        }
        [Test] public void UT04_V1UsesExactLittleEndianOffsets()
        {
            byte[] body=V1(); string reason;
            Check.Equal(76,body.Length); Check.Equal((byte)65,body[0]); Check.Equal((byte)1,body[4]);
            Check.Equal((byte)3,body[8]); Check.Equal((byte)3,body[12]);
            Check.Equal((byte)0x80,body[18]); Check.Equal((byte)0x3f,body[19]); // float32 1.0
            Check.Equal((byte)1,body[52]); Check.Equal((byte)12,body[63]);
            Check.Equal((byte)2,body[72]); Check.True(ArsmEncoder.TryValidate(body,out reason),reason);
        }
        [Test] public void V2ContainsUvsAndLengthDelimitedPng()
        {
            var body=V2(); string reason;
            Check.Equal((byte)2,body[4]); Check.Equal((byte)1,body[100]); Check.Equal((byte)1,body[104]);
            Check.True(ArsmEncoder.TryValidate(body,out reason),reason);
        }
        [Test] public void CorruptHeadersAndTopologyAreRejected()
        {
            foreach(int offset in new[]{0,4,8,12,64})
            { var body=V1(); body[offset]=255; string reason; Check.False(ArsmEncoder.TryValidate(body,out reason)); }
            var v2=V2(); v2[108]=255; string why; Check.False(ArsmEncoder.TryValidate(v2,out why));
            var trailing=new byte[77]; Array.Copy(V1(),trailing,76); Check.False(ArsmEncoder.TryValidate(trailing,out why));
        }
        [Test] public void EveryTruncationIsRejected()
        {
            foreach(var body in new[]{V1(),V2()}) for(int length=0;length<body.Length;++length)
            { var truncated=new byte[length]; Array.Copy(body,truncated,length); string reason; Check.False(ArsmEncoder.TryValidate(truncated,out reason)); }
        }
        [Test] public void EncoderRejectsBadIndicesColorsAndNonFiniteData()
        {
            Check.Throws<ArgumentException>(()=>ArsmEncoder.Encode(Positions(),Colors(),new uint[]{0,1,99}));
            Check.Throws<ArgumentException>(()=>ArsmEncoder.Encode(Positions(),Colors(),new uint[]{0,1}));
            Check.Throws<ArgumentException>(()=>ArsmEncoder.Encode(Positions(),new byte[4],Indices));
            var p=Positions(); p[1].Y=float.PositiveInfinity;
            Check.Throws<ArgumentException>(()=>ArsmEncoder.Encode(p,Colors(),Indices));
        }
        [Test] public void MaximumBodyLimitIsEnforcedBeforeAllocation()
        {
            // Valid count and in-range indices: rejection must come from body size.
            int count=(ArsmEncoder.MaxBytes/4+2)/3*3;
            Check.Throws<ArgumentException>(()=>ArsmEncoder.Encode(Positions(),Colors(),new uint[count]));
            string reason; Check.False(ArsmEncoder.TryValidate(new byte[16],out reason));
        }
    }
}
