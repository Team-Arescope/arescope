using Arescope.Hud;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace Arescope
{
    public sealed class HudOverlay : MonoBehaviour
    {
        public Camera headCamera;
        public ArescopeHudController hud;
        public int hudLayer=5;
        Camera overlay;
        bool configured;
        void LateUpdate()
        {
            if(headCamera==null) headCamera=Camera.main;
            if(hud==null) hud=GetComponent<ArescopeHudController>();
            if(headCamera==null || hud?.worldCanvas==null) return;
            if(!configured)
            {
                var go=new GameObject("Arescope HUD Overlay",typeof(Camera)); go.transform.SetParent(headCamera.transform,false);
                overlay=go.GetComponent<Camera>(); overlay.CopyFrom(headCamera); overlay.cullingMask=1<<hudLayer;
                overlay.clearFlags=CameraClearFlags.Depth;
                var data=overlay.GetUniversalAdditionalCameraData(); data.renderType=CameraRenderType.Overlay; data.clearDepth=true;
                var baseData=headCamera.GetUniversalAdditionalCameraData();
                if(baseData.cameraStack==null) { ArescopeLog.Warn("hud","active URP renderer does not support camera stacking"); Destroy(go); enabled=false; return; }
                baseData.cameraStack.Add(overlay); headCamera.cullingMask &= ~(1<<hudLayer); configured=true;
            }
            // Reproject with the current head camera, including runtime FOV changes.
            overlay.projectionMatrix=headCamera.projectionMatrix;
            hud.worldCanvas.worldCamera=overlay; SetLayer(hud.worldCanvas.transform,hudLayer);
        }
        static void SetLayer(Transform node,int layer)
        { node.gameObject.layer=layer; foreach(Transform child in node) SetLayer(child,layer); }
        void OnDestroy()
        {
            if(configured && headCamera!=null)
            {
                headCamera.GetUniversalAdditionalCameraData().cameraStack?.Remove(overlay);
                headCamera.cullingMask |= 1<<hudLayer;
            }
            if(overlay!=null) Destroy(overlay.gameObject);
        }
    }
}
