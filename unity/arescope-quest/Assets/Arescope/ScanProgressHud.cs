using Arescope.Hud;
using Genesis.RoomScan;
using UnityEngine;

namespace Arescope
{
    public sealed class ScanProgressHud : MonoBehaviour
    {
        public ArescopeHudController hud;
        public float interval=.5f;
        float next;
        void Update()
        {
            if(hud==null || Time.unscaledTime<next) return; next=Time.unscaledTime+interval;
            var scanner=RoomScanner.Instance;
            if(scanner==null) { hud.SetStatus("SCAN","Unavailable"); return; }
            var progress=scanner.CurrentProgress;
            hud.SetStatus("SCAN",scanner.IsScanning?"Scanning "+Mathf.RoundToInt(progress.OverallProgress*100)+"%":"Ready");
            hud.SetStatusRows(new[]{"DEPTH "+progress.Coverage.IntegrationCount,"VERTICES "+progress.Coverage.MeshVertexCount,
                "UPLINK "+LiveFrameSender.LastStatusCode,"MESH "+MeshUploader.LastResult});
        }
    }
}
