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
        public string carrierId="";
        public string carrierType="mast-testbed";
        public float interval=3, rangeMeters=10, heightBand=1.4f;
        public static long LastStatusCode { get; private set; }
        public static DateTime LastSuccessAt { get; private set; }
        public static bool LastStored { get; private set; }
        public static bool LastThrottled { get; private set; }
        public static bool LastSuccess { get; private set; }
        public static string LastSessionId { get; private set; }
        public static string LastGuardianRisk { get; private set; }
        public static float LastGuardianRiskScore { get; private set; }
        public static string LastGuardianCause { get; private set; }
        public static string LastRecoveryAction { get; private set; }
        public static bool LastLowConfidence { get; private set; }
        public static int LastSampleCount { get; private set; }
        public static float LastEffectiveFps { get; private set; }
        public static float LastPoseJumpM { get; private set; }
        public static float LastLumaContrast { get; private set; }
        static int sessionEpoch;
        public static void ResetSession()
        {
            ++sessionEpoch; LastSessionId=null; LastSuccess=false; LastStored=false; LastThrottled=false; LastStatusCode=0;
            LastSuccessAt=default(DateTime);
            ClearGuardian();
            LastSampleCount=0; LastEffectiveFps=0f; LastPoseJumpM=0f; LastLumaContrast=0f;
        }
        readonly Vector3[] sample=new Vector3[6000];
        readonly Color32[] sampleColors=new Color32[6000];
        readonly StringBuilder json=new StringBuilder(16384);
        float next; bool busy;
        int trackedEpoch=-1;
        bool hasPreviousHead;
        Vector3 previousHeadPos;
        float maxPoseJumpInWindow;
        float smoothedFps;
        bool hasSentFrameInSession;
        [Serializable] sealed class GuardianResponse
        {
            public float riskScore;
            public string riskLevel;
            public string predictedCause;
            public string recoveryAction;
            public bool lowConfidence;
            public float risk_score;
            public string risk_level;
            public string predicted_cause;
            public string recovery_action;
            public bool low_confidence;
        }
        [Serializable] sealed class IngestResponse { public bool ok,stored,throttled; public long sessionId; public GuardianResponse guardian; }
        void SyncEpoch()
        {
            if(trackedEpoch==sessionEpoch) return;
            trackedEpoch=sessionEpoch;
            hasPreviousHead=false;
            previousHeadPos=Vector3.zero;
            maxPoseJumpInWindow=0f;
            smoothedFps=0f;
            hasSentFrameInSession=false;
            next=0f;
        }
        void Update()
        {
            SyncEpoch();
            float dt=Time.unscaledDeltaTime;
            if(dt>0.0001f)
            {
                float instFps=1f/dt;
                if(IsFinite(instFps) && instFps<1000f)
                    smoothedFps=smoothedFps<=0f?instFps:Mathf.Lerp(smoothedFps,instFps,0.2f);
            }
            if(headsetTransform!=null)
            {
                Vector3 currentPos=headsetTransform.position;
                if(IsFinite(currentPos))
                {
                    if(hasPreviousHead)
                    {
                        float delta=Vector3.Distance(currentPos,previousHeadPos);
                        if(IsFinite(delta) && delta>maxPoseJumpInWindow) maxPoseJumpInWindow=delta;
                    }
                    previousHeadPos=currentPos;
                    hasPreviousHead=true;
                }
            }
            if(busy || headsetTransform==null || RoomScanner.Instance==null || !RoomScanner.Instance.IsScanning || Time.unscaledTime<next) return;
            next=Time.unscaledTime+interval; _=SendAsync();
        }
        public async Task SendAsync()
        {
            if(busy || headsetTransform==null) return; busy=true; int epoch=sessionEpoch;
            try
            {
                SyncEpoch();
                if(!LiveTransport.Config(out _,out _)) { LastSuccess=false; return; }
                int count=await ArescopeLiveCloud.SampleAsync(sample,sampleColors,sample.Length);
                if(this==null || headsetTransform==null || epoch!=sessionEpoch) return;
                var head=headsetTransform.position;
                var forward=Vector3.ProjectOnPlane(headsetTransform.forward,Vector3.up).normalized;
                if(!IsFinite(head) || !IsFinite(forward)) { LastSuccess=false; return; }
                if(forward.sqrMagnitude<.001f) forward=Vector3.forward;
                var right=Vector3.Cross(Vector3.up,forward); var relocation=ArescopeFrame.Relocation();
                float poseJumpM=maxPoseJumpInWindow>0f?maxPoseJumpInWindow:(hasPreviousHead && IsFinite(head)?Vector3.Distance(head,previousHeadPos):0f);
                poseJumpM=FiniteOrZero(poseJumpM);
                maxPoseJumpInWindow=0f;
                if(IsFinite(head)) { previousHeadPos=head; hasPreviousHead=true; }
                float dt=Time.unscaledDeltaTime;
                float effectiveFps=FiniteOrZero(smoothedFps>0f?smoothedFps:(dt>0.0001f?1f/dt:0f));
                float sumLuma=0f, sumLumaSq=0f;
                for(int i=0;i<count;++i)
                {
                    Color32 c=sampleColors[i];
                    float luma=(0.2126f*c.r+0.7152f*c.g+0.0722f*c.b)*(1f/255f);
                    sumLuma+=luma;
                    sumLumaSq+=luma*luma;
                }
                float lumaContrast=0f;
                if(count>1)
                {
                    float inv=1f/count;
                    float mean=sumLuma*inv;
                    float variance=Mathf.Max(0f,sumLumaSq*inv-mean*mean);
                    lumaContrast=FiniteOrZero(Mathf.Clamp01(Mathf.Sqrt(variance)*2f));
                }
                bool linkOk=Application.internetReachability!=NetworkReachability.NotReachable && (LastStatusCode==0 || LastSuccess);
                string effectiveRoom=string.IsNullOrWhiteSpace(room)?"default":room.Trim();
                if(effectiveRoom.Length>64) effectiveRoom=effectiveRoom.Substring(0,64);
                string effectiveCarrierId=!string.IsNullOrWhiteSpace(carrierId)?carrierId.Trim():(!string.Equals(effectiveRoom,"default",StringComparison.OrdinalIgnoreCase)?effectiveRoom:"quest-mast-01");
                if(effectiveCarrierId.Length>64) effectiveCarrierId=effectiveCarrierId.Substring(0,64);
                string effectiveCarrierType=string.IsNullOrWhiteSpace(carrierType)?"mast-testbed":carrierType.Trim().ToLowerInvariant();
                if(effectiveCarrierType!="rover" && effectiveCarrierType!="mast-testbed" && effectiveCarrierType!="helmet")
                    effectiveCarrierType="mast-testbed";
                LastSampleCount=count; LastEffectiveFps=effectiveFps; LastPoseJumpM=poseJumpM; LastLumaContrast=lumaContrast;

                // JSON points are head-relative, horizontal right/ahead axes, in metres.
                json.Clear();
                json.Append("{\"room\":"); AppendJsonString(json,effectiveRoom,"default");
                json.Append(",\"yawDeg\":").Append(FiniteOrZero(headsetTransform.eulerAngles.y).ToString("R",CultureInfo.InvariantCulture));
                json.Append(",\"carrierId\":"); AppendJsonString(json,effectiveCarrierId,"quest-mast-01");
                json.Append(",\"carrierType\":"); AppendJsonString(json,effectiveCarrierType,"mast-testbed");
                json.Append(",\"telemetry\":{\"pointCount\":").Append(count)
                    .Append(",\"fps\":").Append(effectiveFps.ToString("R",CultureInfo.InvariantCulture))
                    .Append(",\"poseJumpM\":").Append(poseJumpM.ToString("R",CultureInfo.InvariantCulture))
                    .Append(",\"lumaContrast\":").Append(lumaContrast.ToString("R",CultureInfo.InvariantCulture))
                    .Append(",\"linkOk\":").Append(linkOk?"true":"false")
                    .Append(",\"position\":[").Append(FiniteOrZero(head.x).ToString("R",CultureInfo.InvariantCulture)).Append(',')
                    .Append(FiniteOrZero(head.y).ToString("R",CultureInfo.InvariantCulture)).Append(',')
                    .Append(FiniteOrZero(head.z).ToString("R",CultureInfo.InvariantCulture)).Append("]}");
                json.Append(",\"points\":[");
                int written=0;
                for(int i=0;i<count && written<384;++i)
                {
                    Vector3 delta=relocation.MultiplyPoint3x4(sample[i])-head;
                    if(!IsFinite(delta) || Mathf.Abs(delta.y)>heightBand || delta.x*delta.x+delta.z*delta.z>rangeMeters*rangeMeters) continue;
                    float horizontal=Vector3.Dot(delta,right), ahead=Vector3.Dot(delta,forward);
                    if(!IsFinite(horizontal) || !IsFinite(ahead)) continue;
                    if(written++>0) json.Append(',');
                    json.Append('[').Append(horizontal.ToString("R",CultureInfo.InvariantCulture)).Append(',')
                        .Append(delta.y.ToString("R",CultureInfo.InvariantCulture)).Append(',')
                        .Append(ahead.ToString("R",CultureInfo.InvariantCulture)).Append(']');
                }
                if(written==0 && !hasSentFrameInSession) { LastSuccess=false; return; }
                hasSentFrameInSession=true;
                json.Append("]}"); var response=await LiveTransport.Post("/api/live/frame",LiveTransport.Utf8(json.ToString()),"application/json",8);
                if(epoch!=sessionEpoch) return;
                LastStatusCode=response.Code; LastSuccess=false; LastStored=false; LastThrottled=false;
                if(response.Success)
                {
                    var result=JsonUtility.FromJson<IngestResponse>(response.Text);
                    LastSuccess=result!=null && result.ok;
                    if(LastSuccess)
                    {
                        LastSuccessAt=DateTime.UtcNow; LastStored=result.stored; LastThrottled=result.throttled;
                        LastSessionId=result.sessionId>0?result.sessionId.ToString(CultureInfo.InvariantCulture):null;
                        ParseGuardian(result.guardian);
                    }
                }
                if(!LastSuccess) ArescopeLog.Warn("live","HTTP "+response.Code+" "+response.Error);
            }
            catch(Exception e)
            {
                if(epoch==sessionEpoch) { LastSuccess=false; ArescopeLog.Exception("live",e); }
            }
            finally { busy=false; }
        }
        static void ClearGuardian()
        {
            LastGuardianRisk=null; LastGuardianRiskScore=0f; LastGuardianCause=null; LastRecoveryAction=null; LastLowConfidence=false;
        }
        static void ParseGuardian(GuardianResponse g)
        {
            if(g==null) { ClearGuardian(); return; }
            string level=!string.IsNullOrEmpty(g.riskLevel)?g.riskLevel:g.risk_level;
            string cause=!string.IsNullOrEmpty(g.predictedCause)?g.predictedCause:g.predicted_cause;
            string action=!string.IsNullOrEmpty(g.recoveryAction)?g.recoveryAction:g.recovery_action;
            float score=Mathf.Clamp01(FiniteOrZero(g.riskScore>0f?g.riskScore:g.risk_score));
            bool lowConf=g.lowConfidence || g.low_confidence;
            bool hasGuardian=!string.IsNullOrEmpty(level) || !string.IsNullOrEmpty(cause) ||
                             !string.IsNullOrEmpty(action) || score>0f || lowConf;
            if(!hasGuardian) { ClearGuardian(); return; }
            if(string.IsNullOrWhiteSpace(level))
                level=score>=0.78f?"critical":(score>=0.45f?"warning":"nominal");
            LastGuardianRisk=level.Trim().ToLowerInvariant();
            LastGuardianRiskScore=score;
            LastGuardianCause=string.IsNullOrEmpty(cause)?null:cause;
            LastRecoveryAction=string.IsNullOrEmpty(action)?null:action;
            LastLowConfidence=lowConf;
        }
        static bool IsFinite(float v) => !float.IsNaN(v) && !float.IsInfinity(v);
        static bool IsFinite(Vector3 v) => IsFinite(v.x) && IsFinite(v.y) && IsFinite(v.z);
        static float FiniteOrZero(float v) => IsFinite(v)?v:0f;
        static void AppendJsonString(StringBuilder b,string value,string fallback)
        {
            b.Append('"');
            foreach(char c in value??fallback)
            {
                if(c=='"' || c=='\\') b.Append('\\').Append(c);
                else if(c<32) b.Append("\\u").Append(((int)c).ToString("x4")); else b.Append(c);
            }
            b.Append('"');
        }
    }
}
