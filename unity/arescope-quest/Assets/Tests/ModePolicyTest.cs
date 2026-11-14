using NUnit.Framework;

namespace Arescope.Tests
{
    [TestFixture] public sealed class ModePolicyTest
    {
        [Test] public void UT01_AllAvailabilityStates()
        {
            foreach(bool hasScan in new[]{false,true})
            {
                Check.True(ModePolicyMath.CanSwitch(ViewMode.Passthrough,hasScan));
                Check.Equal(hasScan,ModePolicyMath.CanSwitch(ViewMode.Mixed,hasScan));
                Check.Equal(hasScan,ModePolicyMath.CanSwitch(ViewMode.Scan,hasScan));
                Check.False(ModePolicyMath.CanSwitch((ViewMode)999,hasScan));
            }
        }
        [Test] public void CycleAndVisibilityAreSynchronized()
        {
            Check.Equal(ViewMode.Passthrough,ModePolicyMath.Next(ViewMode.Scan));
            Check.Equal(ViewMode.Mixed,ModePolicyMath.Next(ViewMode.Passthrough));
            Check.Equal(ViewMode.Scan,ModePolicyMath.Next(ViewMode.Mixed));
            Check.True(ModePolicyMath.ShowsPassthrough(ViewMode.Mixed));
            Check.True(ModePolicyMath.ShowsScan(ViewMode.Mixed));
            Check.False(ModePolicyMath.ShowsScan(ViewMode.Passthrough));
            Check.False(ModePolicyMath.ShowsPassthrough(ViewMode.Scan));
        }
    }
}
