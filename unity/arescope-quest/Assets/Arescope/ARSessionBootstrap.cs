using System.Collections;
using UnityEngine;
using UnityEngine.XR;
using UnityEngine.XR.ARFoundation;

namespace Arescope
{
    public sealed class ARSessionBootstrap : MonoBehaviour
    {
        public ARSession session;
        public AROcclusionManager occlusion;
        public bool Ready { get; private set; }
        IEnumerator Start()
        {
            if(session==null) session=FindFirstObjectByType<ARSession>();
            if(occlusion==null) occlusion=FindFirstObjectByType<AROcclusionManager>();
            float deadline=Time.realtimeSinceStartup+15;
            while(!XRSettings.isDeviceActive && Time.realtimeSinceStartup<deadline) yield return null;
            yield return new WaitForSecondsRealtime(.6f);
            if(XRSettings.isDeviceActive && occlusion!=null && occlusion.subsystem==null && session!=null)
            {
                ArescopeLog.Warn("xr-boot","occlusion=no-subsystem; toggling ARSession");
                session.enabled=false;
                yield return null;
                session.enabled=true;
                yield return new WaitForSecondsRealtime(.6f);
            }
            Ready=XRSettings.isDeviceActive && occlusion!=null && occlusion.subsystem!=null;
            ArescopeLog.Info("xr-boot","xr="+(XRSettings.isDeviceActive?"active":"inactive")+
                " occlusion="+(occlusion?.subsystem==null?"no-subsystem":occlusion.subsystem.GetType().Name)+" ready="+Ready);
        }
    }
}
