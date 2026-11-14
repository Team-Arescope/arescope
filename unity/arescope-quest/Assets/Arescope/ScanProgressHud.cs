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
        readonly string[] statusRows=new string[5];
        void Update()
        {
            if(hud==null || Time.unscaledTime<next) return; next=Time.unscaledTime+interval;
            var scanner=RoomScanner.Instance;
            if(scanner==null) { hud.SetStatus("SCAN","Unavailable"); return; }
            var progress=scanner.CurrentProgress;
            statusRows[0]=(scanner.IsScanning?"SCAN "+Mathf.RoundToInt(progress.OverallProgress*100)+"% · ":"SCAN READY · ")+"DEPTH "+progress.Coverage.IntegrationCount;
            statusRows[1]="VERTICES "+progress.Coverage.MeshVertexCount;
            statusRows[2]="UPLINK "+LiveFrameSender.LastStatusCode;
            statusRows[3]=FormatGuardianRow();
            statusRows[4]="MESH "+MeshUploader.LastResult;
            hud.SetStatusRows(statusRows);
        }
        static string FormatGuardianRow()
        {
            string risk=LiveFrameSender.LastGuardianRisk;
            if(string.IsNullOrEmpty(risk)) return "GUARDIAN --";
            string label=risk.Trim().ToUpperInvariant();
            string action=LiveFrameSender.LastRecoveryAction;
            if(!string.IsNullOrEmpty(action))
            {
                string clean=action.Trim();
                if(clean.Length>28) clean=clean.Substring(0,25)+"...";
                return "GUARDIAN "+label+" · "+clean;
            }
            return "GUARDIAN "+label;
        }
    }
}
