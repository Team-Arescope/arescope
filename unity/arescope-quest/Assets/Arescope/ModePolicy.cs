namespace Arescope
{
    public static class ModePolicy
    {
        public static bool CanSwitch(ViewMode mode, bool hasScan) => ModePolicyMath.CanSwitch(mode,hasScan);
        public static ViewMode Next(ViewMode mode) => ModePolicyMath.Next(mode);
    }
}
