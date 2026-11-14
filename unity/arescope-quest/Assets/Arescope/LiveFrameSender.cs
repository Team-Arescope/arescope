using System;
using System.Globalization;
using System.Text;
using System.Threading.Tasks;
using Genesis.RoomScan;
using UnityEngine;

namespace Arescope
{
    public sealed class LiveFrameSender : MonoBehaviour
    {
        public Transform headsetTransform;
        public string room="default";
        public float interval=3, rangeMeters=10, heightBand=1.4f;
        public static long LastStatusCode { get; private set; }
        public static DateTime LastSuccessAt { get; private set; }
        public static bool LastStored { get; private set; }
        public static bool LastThrottled { get; private set; }
        public static bool LastSuccess { get; private set; }
        public static string LastSessionId { get; private set; }
        static int sessionEpoch;
        public static void ResetSession()
        {
            ++sessionEpoch; LastSessionId=null; LastSuccess=false; LastStored=false; LastThrottled=false; LastStatusCode=0;
            LastSuccessAt=default(DateTime);
        }
        readonly Vector3[] sample=new Vector3[6000]; float next; bool busy;
        [Serializable] sealed class IngestResponse { public bool ok,stored,throttled; public long sessionId; }
        async void Update()
        {
            if(busy || headsetTransform==null || RoomScanner.Instance==null || !RoomScanner.Instance.IsScanning || Time.unscaledTime<next) return;
            next=Time.unscaledTime+interval; await SendAsync();
        }
        public async Task SendAsync()
        {
            if(busy || headsetTransform==null) return; busy=true; int epoch=sessionEpoch;
            try
            {
                if(!LiveTransport.Config(out _,out _)) { LastSuccess=false; return; }
                int count=await ArescopeLiveCloud.SampleAsync(sample,sample.Length);
                if(this==null || headsetTransform==null || epoch!=sessionEpoch) return;
                var head=headsetTransform.position; var forward=Vector3.ProjectOnPlane(headsetTransform.forward,Vector3.up).normalized;
                if(forward.sqrMagnitude<.001f) forward=Vector3.forward;
                var right=Vector3.Cross(Vector3.up,forward); var relocation=ArescopeFrame.Relocation();
                // JSON points are head-relative, horizontal right/ahead axes, in metres.
                var json=new StringBuilder("{\"room\":"); json.Append(JsonString(room));
                json.Append(",\"yawDeg\":").Append(headsetTransform.eulerAngles.y.ToString("R",CultureInfo.InvariantCulture)).Append(",\"points\":[");
                int written=0;
                for(int i=0;i<count && written<384;++i)
                {
                    Vector3 delta=relocation.MultiplyPoint3x4(sample[i])-head;
                    if(Mathf.Abs(delta.y)>heightBand || delta.x*delta.x+delta.z*delta.z>rangeMeters*rangeMeters) continue;
                    if(written++>0) json.Append(',');
                    json.Append('[').Append(Vector3.Dot(delta,right).ToString("R",CultureInfo.InvariantCulture)).Append(',')
                        .Append(delta.y.ToString("R",CultureInfo.InvariantCulture)).Append(',')
                        .Append(Vector3.Dot(delta,forward).ToString("R",CultureInfo.InvariantCulture)).Append(']');
                }
                if(written==0) { LastSuccess=false; return; }
                json.Append("]}"); var response=await LiveTransport.Post("/api/live/frame",LiveTransport.Utf8(json.ToString()),"application/json",8);
                if(epoch!=sessionEpoch) return;
                LastStatusCode=response.Code; LastSuccess=false; LastStored=false; LastThrottled=false;
                if(response.Success)
                {
                    var result=JsonUtility.FromJson<IngestResponse>(response.Text);
                    LastSuccess=result!=null && result.ok;
                    if(LastSuccess) { LastSuccessAt=DateTime.UtcNow; LastStored=result.stored; LastThrottled=result.throttled; LastSessionId=result.sessionId>0?result.sessionId.ToString(CultureInfo.InvariantCulture):null; }
                }
                if(!LastSuccess) ArescopeLog.Warn("live","HTTP "+response.Code+" "+response.Error);
            }
            catch(Exception e) { LastSuccess=false; ArescopeLog.Exception("live",e); }
            finally { busy=false; }
        }
        static string JsonString(string value)
        {
            var b=new StringBuilder("\"");
            foreach(char c in value??"default")
            {
                if(c=='"' || c=='\\') b.Append('\\').Append(c);
                else if(c<32) b.Append("\\u").Append(((int)c).ToString("x4")); else b.Append(c);
            }
            return b.Append('"').ToString();
        }
    }
}
