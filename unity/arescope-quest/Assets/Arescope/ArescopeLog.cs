using System;
using System.IO;
using System.Text;
using UnityEngine;

namespace Arescope
{
    public static class ArescopeLog
    {
        const int RotateBytes=512*1024, SnapshotChars=2000000;
        static readonly object Gate=new object();
        static string path;
        public static string FilePath => path ?? (path=Path.Combine(Application.persistentDataPath,"arescope-debug.log"));
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Boot()
        {
            path=Path.Combine(Application.persistentDataPath,"arescope-debug.log");
            Application.SetStackTraceLogType(LogType.Log,StackTraceLogType.None);
            Application.SetStackTraceLogType(LogType.Warning,StackTraceLogType.None);
            Application.SetStackTraceLogType(LogType.Error,StackTraceLogType.ScriptOnly);
            Info("boot","app="+Application.version+" unity="+Application.unityVersion+" device="+SystemInfo.deviceModel);
        }
        public static void Info(string area,string message) => Write(LogType.Log,area,message);
        public static void Warn(string area,string message) => Write(LogType.Warning,area,message);
        public static void Error(string area,string message) => Write(LogType.Error,area,message);
        public static void Exception(string area,Exception error) => Error(area,error.GetType().Name+": "+error.Message+"\n"+error.StackTrace);
        static void Write(LogType type,string area,string message)
        {
            // Keep one event bounded so a single exception cannot defeat rotation.
            message=message??""; if(message.Length>16000) message=message.Substring(0,16000);
            string line="[ARS] "+area+" | "+message;
            if(type==LogType.Error) Debug.LogError(line); else if(type==LogType.Warning) Debug.LogWarning(line); else Debug.Log(line);
            try
            {
                lock(Gate)
                {
                    string entry=DateTime.UtcNow.ToString("O")+" "+line+Environment.NewLine;
                    int size=Encoding.UTF8.GetByteCount(entry);
                    var file=new FileInfo(FilePath);
                    if(file.Exists && file.Length+size>RotateBytes)
                    { if(File.Exists(FilePath+".1")) File.Delete(FilePath+".1"); File.Move(FilePath,FilePath+".1"); }
                    Directory.CreateDirectory(Path.GetDirectoryName(FilePath));
                    File.AppendAllText(FilePath,entry,new UTF8Encoding(false));
                }
            }
            catch(IOException) { }
            catch(UnauthorizedAccessException) { }
        }
        public static string Snapshot()
        {
            lock(Gate)
            {
                var text=new StringBuilder();
                foreach(string file in new[]{FilePath+".1",FilePath})
                {
                    try { if(File.Exists(file)) text.Append(File.ReadAllText(file,Encoding.UTF8)); }
                    catch(IOException) { } catch(UnauthorizedAccessException) { }
                }
                int start=Math.Max(0,text.Length-SnapshotChars);
                if(start>0 && char.IsLowSurrogate(text[start])) ++start;
                return text.ToString(start,text.Length-start);
            }
        }
    }
}
