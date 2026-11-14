#if ARESCOPE_STANDALONE
using System;
using System.Reflection;

namespace NUnit.Framework
{
    [AttributeUsage(AttributeTargets.Class)] public sealed class TestFixtureAttribute:Attribute { }
    [AttributeUsage(AttributeTargets.Method)] public sealed class TestAttribute:Attribute { }
}
namespace Arescope.Tests
{
    static class StandaloneRunner
    {
        public static int Main()
        {
            int passed=0,failed=0;
            foreach(var type in Assembly.GetExecutingAssembly().GetTypes())
            foreach(var method in type.GetMethods(BindingFlags.Public|BindingFlags.Instance))
            {
                if(!Attribute.IsDefined(method,typeof(NUnit.Framework.TestAttribute))) continue;
                try { method.Invoke(Activator.CreateInstance(type),null); ++passed; Console.WriteLine("PASS "+type.Name+"."+method.Name); }
                catch(Exception e) { ++failed; Console.WriteLine("FAIL "+type.Name+"."+method.Name+": "+(e.InnerException??e).Message); }
            }
            Console.WriteLine("Tests: "+passed+" passed, "+failed+" failed"); return failed==0?0:1;
        }
    }
}
#endif
