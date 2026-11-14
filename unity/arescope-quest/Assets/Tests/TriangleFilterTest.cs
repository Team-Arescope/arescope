using NUnit.Framework;

namespace Arescope.Tests
{
    [TestFixture] public sealed class TriangleFilterTest
    {
        static Float3[] Points()
        {
            return new[]{new Float3(0,0,0),new Float3(.02f,0,0),new Float3(0,.02f,0),
                new Float3(2,1,0),new Float3(0,float.NaN,0),new Float3(0,0,float.PositiveInfinity),new Float3(.01f,0,0)};
        }
        [Test] public void UT02_RejectionsAreCountedAndLocalTriangleSurvives()
        {
            var r=TriangleFilterMath.Filter(Points(),new uint[]{0,1,2, 0,0,1, 0,1,99, 0,1,4, 0,1,5, 0,1,3, 0,1,6});
            Check.Equal(7,r.Raw); Check.Equal(1,r.Kept); Check.Equal(2,r.Degenerate);
            Check.Equal(1,r.OutOfRange); Check.Equal(2,r.NonFinite); Check.Equal(1,r.Stretched);
            Check.Equal(3,r.Indices.Length); Check.Equal(2,r.Indices[2]);
            Check.Near(r.MedianEdge*4,r.Limit);
        }
        [Test] public void EmptyAndPartialTailDoNotReadPastBounds()
        {
            Check.Equal(0,TriangleFilterMath.Filter(new Float3[0],new uint[]{0,1}).Raw);
            Check.Equal(1,TriangleFilterMath.Filter(Points(),new uint[]{0,1,2,uint.MaxValue}).Kept);
            Check.Equal(1,TriangleFilterMath.Filter(Points(),new uint[]{0,1,uint.MaxValue}).OutOfRange);
        }
        [Test] public void CallerMaxEdgeIsEffective()
        {
            Check.Equal(0,TriangleFilterMath.Filter(Points(),new uint[]{0,1,2},.01f).Kept);
            Check.Throws<System.ArgumentOutOfRangeException>(()=>TriangleFilterMath.Filter(Points(),new uint[0],float.NaN));
        }
        [Test] public void MedianIsBoundedAtThirtyCentimetres()
        {
            var p=new[]{new Float3(0,0,0),new Float3(.2f,0,0),new Float3(0,.2f,0)};
            Check.Near(.30f,TriangleFilterMath.Filter(p,new uint[]{0,1,2}).Limit);
        }
        [Test] public void TinyTrianglesUseSixCentimetreFloor()
        {
            var p=new[]{new Float3(),new Float3(.001f,0,0),new Float3(0,.001f,0)};
            Check.Near(.06f,TriangleFilterMath.Filter(p,new uint[]{0,1,2}).Limit);
        }
        [Test] public void HostileIndicesAlwaysProduceValidTopology()
        {
            var random=new System.Random(412); var p=Points();
            for(int run=0;run<100;++run)
            {
                var ix=new uint[303]; for(int i=0;i<ix.Length;++i) ix[i]=(uint)random.Next(0,15);
                var r=TriangleFilterMath.Filter(p,ix);
                Check.Equal(r.Raw,r.Kept+r.Degenerate+r.OutOfRange+r.NonFinite+r.Stretched);
                foreach(int i in r.Indices) { Check.True(i>=0 && i<p.Length); Check.True(p[i].IsFinite); }
            }
        }
    }
}
