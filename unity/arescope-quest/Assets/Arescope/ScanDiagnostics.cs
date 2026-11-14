using Genesis.RoomScan;
using UnityEngine;
using UnityEngine.XR;
using UnityEngine.XR.ARFoundation;

namespace Arescope
{
    public sealed class ScanDiagnostics : MonoBehaviour
    {
        public float interval=5;
        float next;
        void Update()
        {
            if(Time.unscaledTime<next) return; next=Time.unscaledTime+interval;
            var scanner=RoomScanner.Instance; var extractor=MeshExtractor.Instance;
            var occlusion=FindFirstObjectByType<AROcclusionManager>();
            ArescopeLog.Info("depth","xr="+(XRSettings.isDeviceActive?"active":"inactive")+
                " sub="+(occlusion?.subsystem?.GetType().Name??"null")+" running="+(occlusion?.subsystem?.running??false));
            ArescopeLog.Info("scan","scanning="+(scanner?.IsScanning??false)+" extracts="+(extractor?.ExtractCount??0)+
                " verts="+(extractor?.LastVertexCount??0)+" indices="+(extractor?.LastIndexCount??0)+" sample="+ArescopeLiveCloud.LastReason);
        }
    }
}
