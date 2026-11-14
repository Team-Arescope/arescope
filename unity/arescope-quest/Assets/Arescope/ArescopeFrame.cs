using Genesis.RoomScan;
using UnityEngine;

namespace Arescope
{
    public static class ArescopeFrame
    {
        static Matrix4x4 capture=Matrix4x4.identity, previous=Matrix4x4.identity;
        public static bool IsCaptured { get; private set; }
        public static Matrix4x4 CaptureMatrix => capture;
        static Matrix4x4 Current => RoomAnchorManager.Instance!=null ? RoomAnchorManager.Instance.SpatialAnchorMatrix : Matrix4x4.identity;
        public static void Capture()
        {
            capture=previous=Current; IsCaptured=true;
            ArescopeLog.Info("frame","capture anchor="+(RoomAnchorManager.Instance?.HasSpatialAnchor??false)+" matrix="+capture);
        }
        public static Matrix4x4 Relocation() => IsCaptured ? Current*capture.inverse : Matrix4x4.identity;
        public static bool Apply(Transform visualRoot)
        {
            if(visualRoot==null) return false;
            Matrix4x4 now=Current; bool changed=false;
            for(int i=0;i<16;++i) if(Mathf.Abs(now[i]-previous[i])>.0005f) { changed=true; break; }
            Matrix4x4 relocation=IsCaptured?now*capture.inverse:Matrix4x4.identity;
            visualRoot.SetPositionAndRotation(relocation.GetColumn(3),relocation.rotation);
            visualRoot.localScale=Vector3.one;
            if(changed) ArescopeLog.Info("frame","relocated position="+visualRoot.position+" rotation="+visualRoot.eulerAngles);
            previous=now;
            return changed;
        }
        public static Float3 ToMath(Vector3 p) => new Float3(p.x,p.y,p.z);
    }
}
