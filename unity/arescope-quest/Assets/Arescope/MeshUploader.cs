using System;
using System.Threading.Tasks;
using Genesis.RoomScan;
using UnityEngine;

namespace Arescope
{
    public sealed class MeshUploader : MonoBehaviour
    {
        public static string LastResult { get; private set; }="not uploaded";
        public int maxVertices=400000;
        public float collectDelay=1.2f;
        Vector3[] positions; Color32[] colors; int[] indices;
        ArescopeTexturedMeshData textured;
        string uploadedSession; bool busy; int generation;
        RoomScanSession session;
        void Update()
        {
            if(session==RoomScanSession.Instance) return;
            if(session!=null) session.RoomReady-=OnRoomReady;
            session=RoomScanSession.Instance;
            if(session!=null) session.RoomReady+=OnRoomReady;
        }
        void OnRoomReady() { _=UploadAsync(); }
        public void Capture(Mesh mesh,ArescopeTexturedMeshData texture=null)
        {
            ++generation; uploadedSession=null;
            positions=mesh!=null?mesh.vertices:null; colors=mesh!=null?mesh.colors32:null; indices=mesh!=null?mesh.triangles:null; textured=texture;
        }
        public void ClearCapture() { ++generation; positions=null; colors=null; indices=null; textured=null; uploadedSession=null; }
        public async Task UploadAsync()
        {
            if(busy) return; busy=true; int version=generation;
            try
            {
                await Task.Delay(TimeSpan.FromSeconds(collectDelay));
                if(this==null || version!=generation) return;
                if(!LiveTransport.Config(out _,out _)) { LastResult="endpoint or token missing"; return; }
                string id=LiveFrameSender.LastSessionId;
                if(string.IsNullOrEmpty(id)) { LastResult="no session"; return; }
                if(id==uploadedSession) { LastResult="already uploaded"; return; }
                var texture=textured ?? ArescopeTexturedMesh.Read(maxVertices);
                var p=texture?.Positions ?? positions; var ix=texture?.Indices ?? indices;
                if((p==null || ix==null) && RoomScanner.Instance?.RefinedMesh!=null)
                { var mesh=RoomScanner.Instance.RefinedMesh; p=mesh.vertices; ix=mesh.triangles; colors=mesh.colors32; }
                if(p==null || p.Length==0 || ix==null) { LastResult="empty mesh; capture before stop required"; return; }
                if(p.Length>Math.Min(400000,maxVertices)) { LastResult="vertex cap exceeded"; return; }
                byte[] body;
                try { body=Pack(p,ix,colors,texture); }
                catch(ArgumentException) when(texture!=null && positions!=null)
                { body=Pack(positions,indices,colors,null); }
                if(!ArsmEncoder.TryValidate(body,out string reason)) { LastResult="invalid ARSM: "+reason; return; }
                var response=await LiveTransport.Post("/api/live/mesh?session="+Uri.EscapeDataString(id),body,"application/octet-stream",60);
                LastResult=response.Success?"uploaded "+body.Length+" bytes":"HTTP "+response.Code+": "+response.Error;
                if(response.Success && version==generation) uploadedSession=id;
                ArescopeLog.Info("mesh-upload",LastResult);
            }
            catch(Exception e) { LastResult=e.Message; ArescopeLog.Exception("mesh-upload",e); }
            finally { busy=false; }
        }
        static byte[] Pack(Vector3[] p,int[] ix,Color32[] colors,ArescopeTexturedMeshData texture)
        {
            var fp=new Float3[p.Length]; var rgba=new byte[p.Length*4]; var indices=new uint[ix.Length];
            for(int i=0;i<p.Length;++i)
            {
                fp[i]=ArescopeFrame.ToMath(p[i]); Color32 c=colors!=null && colors.Length==p.Length?colors[i]:new Color32(255,255,255,255);
                rgba[i*4]=c.r; rgba[i*4+1]=c.g; rgba[i*4+2]=c.b; rgba[i*4+3]=c.a;
            }
            for(int i=0;i<ix.Length;++i) indices[i]=unchecked((uint)ix[i]);
            float[] uv=null;
            if(texture!=null) { uv=new float[p.Length*2]; for(int i=0;i<p.Length;++i) { uv[i*2]=texture.UVs[i].x; uv[i*2+1]=texture.UVs[i].y; } }
            return ArsmEncoder.Encode(fp,rgba,indices,uv,texture?.AtlasWidth??0,texture?.AtlasHeight??0,texture?.AtlasPng);
        }
        void OnDestroy() { if(session!=null) session.RoomReady-=OnRoomReady; }
    }
}
