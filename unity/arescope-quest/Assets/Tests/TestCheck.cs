using System;

namespace Arescope.Tests
{
    internal static class Check
    {
        public static void True(bool value,string message="Expected true") { if(!value) throw new Exception(message); }
        public static void False(bool value,string message="Expected false") { True(!value,message); }
        public static void Equal<T>(T expected,T actual) { True(object.Equals(expected,actual),"Expected "+expected+", got "+actual); }
        public static void Near(float expected,float actual,float epsilon=.00001f)
        { True(Float3.Finite(actual) && Math.Abs(expected-actual)<=epsilon,"Expected "+expected+", got "+actual); }
        public static void Throws<T>(Action action) where T:Exception
        {
            try { action(); } catch(T) { return; }
            throw new Exception("Expected "+typeof(T).Name);
        }
    }
}
