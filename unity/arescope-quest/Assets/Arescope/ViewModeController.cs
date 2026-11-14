using UnityEngine;

namespace Arescope
{
    public sealed class ViewModeController : MonoBehaviour
    {
        public Camera headsetCamera;
        public OVRPassthroughLayer passthroughLayer;
        public Renderer scanRenderer;
        public GameObject scanVisualRoot;
        public ViewMode CurrentMode { get; private set; } = ViewMode.Passthrough;
        public void Configure(Camera camera, OVRPassthroughLayer passthrough, Renderer renderer, GameObject visualRoot = null)
        {
            headsetCamera=camera; passthroughLayer=passthrough; scanRenderer=renderer; scanVisualRoot=visualRoot;
        }
        public bool Switch(ViewMode mode)
        {
            bool hasScan=scanRenderer!=null || scanVisualRoot!=null;
            if(headsetCamera==null || passthroughLayer==null || !ModePolicy.CanSwitch(mode,hasScan))
            { ArescopeLog.Warn("view","missing references for "+mode); return false; }
            bool scan=ModePolicyMath.ShowsScan(mode), passthrough=ModePolicyMath.ShowsPassthrough(mode);
            if(scanRenderer!=null) scanRenderer.enabled=scan;
            if(scanVisualRoot!=null) scanVisualRoot.SetActive(scan);
            passthroughLayer.enabled=passthrough;
            headsetCamera.clearFlags=CameraClearFlags.SolidColor;
            headsetCamera.backgroundColor=new Color(0,0,0,passthrough?0:1);
            CurrentMode=mode;
            ArescopeLog.Info("view","mode="+CurrentMode);
            return true;
        }
    }
}
