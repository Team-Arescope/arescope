using System;
using NUnit.Framework;

namespace Arescope.Tests
{
    [TestFixture] public sealed class ArescopeFrameTest
    {
        [Test] public void CaptureRelativeTranslation()
        {
            var capture=ArescopeFrameMath.Identity(); capture[3]=10; capture[7]=2;
            var now=ArescopeFrameMath.Identity(); now[3]=12; now[7]=3;
            var p=ArescopeFrameMath.Transform(ArescopeFrameMath.Relocation(now,capture),new Float3(10,2,5));
            Check.Near(12,p.X); Check.Near(3,p.Y); Check.Near(5,p.Z);
        }
        [Test] public void YawAndTranslationUseNowTimesInverseCapture()
        {
            var capture=new float[]{0,0,1,10, 0,1,0,2, -1,0,0,3, 0,0,0,1};
            var now=new float[]{-1,0,0,12, 0,1,0,4, 0,0,-1,8, 0,0,0,1};
            var local=new Float3(1,2,3);
            var captured=ArescopeFrameMath.Transform(capture,local);
            var actual=ArescopeFrameMath.Transform(ArescopeFrameMath.Relocation(now,capture),captured);
            var expected=ArescopeFrameMath.Transform(now,local);
            Check.Near(expected.X,actual.X); Check.Near(expected.Y,actual.Y); Check.Near(expected.Z,actual.Z);
        }
        [Test] public void ChangeThresholdUsesStrictlyGreaterThan()
        {
            var a=ArescopeFrameMath.Identity(); var b=ArescopeFrameMath.Identity(); b[3]=.0005f;
            Check.False(ArescopeFrameMath.Changed(a,b)); b[3]=.000501f; Check.True(ArescopeFrameMath.Changed(a,b));
        }
        [Test] public void InversePivotingAndInvalidMatrices()
        {
            var a=new float[]{0,1,0,0, 1,0,0,0, 0,0,1,0, 0,0,0,1};
            var product=ArescopeFrameMath.Multiply(a,ArescopeFrameMath.Inverse(a)); var identity=ArescopeFrameMath.Identity();
            for(int i=0;i<16;++i) Check.Near(identity[i],product[i]);
            Check.Throws<ArgumentException>(()=>ArescopeFrameMath.Inverse(new float[16]));
            a[1]=float.NaN; Check.Throws<ArgumentException>(()=>ArescopeFrameMath.Inverse(a));
        }
    }
}
