using NUnit.Framework;

namespace Arescope.Tests
{
    [TestFixture] public sealed class MinimapProjectionTest
    {
        [Test] public void UT03_HeightBandIsInclusiveAtThreeCentimetres()
        {
            float[] heights={-.031f,-.030f,0,.030f,.031f}; bool[] expected={false,true,true,true,false};
            for(int i=0;i<heights.Length;++i)
            {
                float x,z;
                Check.Equal(expected[i],MinimapProjectionMath.TryProject(new Float3(1,heights[i],2),new Float3(),new Float3(0,-8,1),out x,out z));
            }
        }
        [Test] public void PitchDoesNotTiltTheMapAndYawRotatesAxes()
        {
            float x,z;
            Check.True(MinimapProjectionMath.TryProject(new Float3(3,0,2),new Float3(),new Float3(0,-100,1),out x,out z));
            Check.Near(3,x); Check.Near(2,z);
            Check.True(MinimapProjectionMath.TryProject(new Float3(3,0,2),new Float3(),new Float3(1,100,0),out x,out z));
            Check.Near(-2,x); Check.Near(3,z);
        }
        [Test] public void RangeIsACircleAndInvalidPointsAreRejected()
        {
            float x,z;
            Check.True(MinimapProjectionMath.TryProject(new Float3(10,0,0),new Float3(),new Float3(0,1,0),out x,out z));
            Check.False(MinimapProjectionMath.TryProject(new Float3(8,0,8),new Float3(),new Float3(0,0,1),out x,out z));
            Check.False(MinimapProjectionMath.TryProject(new Float3(float.NaN,0,0),new Float3(),new Float3(),out x,out z));
        }
        [Test] public void VoxelKeyHandlesNegativeSpaceWithoutAxisCollisions()
        {
            Check.Equal(MinimapProjectionMath.VoxelKey(new Float3(.001f,0,0)),MinimapProjectionMath.VoxelKey(new Float3(.034f,0,0)));
            Check.True(MinimapProjectionMath.VoxelKey(new Float3(-.001f,0,0))!=MinimapProjectionMath.VoxelKey(new Float3(.001f,0,0)));
            Check.True(MinimapProjectionMath.VoxelKey(new Float3(1,0,0))!=MinimapProjectionMath.VoxelKey(new Float3(0,1,0)));
            Check.Throws<System.ArgumentOutOfRangeException>(()=>MinimapProjectionMath.VoxelKey(new Float3(1000000,0,0)));
        }
    }
}
