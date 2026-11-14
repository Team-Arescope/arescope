using System;
using System.IO;
using System.Threading.Tasks;
using Arescope.Hud;
using UnityEngine;
using UnityEngine.XR;

namespace Arescope
{
    public sealed class LogUploader : MonoBehaviour
    {
        public ArescopeHudController hud;
        public static string LastResult { get; private set; }="not uploaded";
        string marker; bool busy, comboFired; float held;
        async void Start()
        {
            marker=Path.Combine(Application.persistentDataPath,"arescope.running");
            bool crashed=File.Exists(marker);
            try { Directory.CreateDirectory(Application.persistentDataPath); File.WriteAllText(marker,DateTime.UtcNow.ToString("O")); }
            catch(Exception e) { ArescopeLog.Warn("logs","marker: "+e.Message); }
            if(crashed) await UploadAsync("crash-recovery");
        }
        void Update()
        {
            var device=InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);
            device.TryGetFeatureValue(CommonUsages.primaryButton,out bool x); device.TryGetFeatureValue(CommonUsages.secondaryButton,out bool y);
            if(x && y)
            {
                held+=Time.unscaledDeltaTime;
                if(held>=2 && !comboFired) { comboFired=true; _=UploadAsync("combo"); }
            }
            else { held=0; comboFired=false; }
        }
        public async Task UploadAsync(string source)
        {
            if(busy) return; busy=true;
            try
            {
                if(!LiveTransport.Config(out _,out _)) { LastResult="endpoint or token missing"; return; }
                ArescopeLog.Info("logs","upload source="+source);
                byte[] body=LiveTransport.Utf8(ArescopeLog.Snapshot());
                if(body.Length==0 || body.Length>8*1024*1024) { LastResult="snapshot size invalid"; return; }
                var response=await LiveTransport.Post("/api/live/log?source="+Uri.EscapeDataString(source??"device"),body,"text/plain; charset=utf-8",25);
                LastResult=response.Success?"Log uploaded":"Log HTTP "+response.Code+": "+response.Error;
                ArescopeLog.Info("logs",LastResult); if(this!=null) hud?.ShowEvent(LastResult);
            }
            catch(Exception e) { LastResult=e.Message; ArescopeLog.Exception("logs",e); }
            finally { busy=false; }
        }
        void OnApplicationPause(bool paused) { if(paused) _=UploadAsync("pause"); }
        void OnApplicationQuit()
        {
            // Never start a request here: quit only marks a clean shutdown.
            try { if(!string.IsNullOrEmpty(marker) && File.Exists(marker)) File.Delete(marker); }
            catch(IOException) { } catch(UnauthorizedAccessException) { }
        }
    }
}
