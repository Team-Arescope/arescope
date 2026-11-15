"""Create the staged, synthetic 900-frame demo story with the actual LAB simulator."""
import argparse
import asyncio
from collections import defaultdict, deque
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]/'services/arescope-lab')
parser.add_argument('--output',type=Path,required=True)
options=parser.parse_args()
root=options.root.resolve()
sys.path.insert(0,str(root))
from fleet_sim import FleetSimManager
from guardian import GuardianEngine

def dist(a,b):
    return math.dist(a,b)

def interpolate_position(a,b,alpha):
    # Resample acknowledged trail corners rather than shortcutting the route.
    trail=b.get('trail',[])
    close=lambda p,q: math.hypot(p[0]-q[0],p[2]-q[2])<1e-5
    junction=next((i for i in range(len(trail)-1,-1,-1) if close(trail[i],a['position'])),None)
    path=[a['position']]
    if junction is not None:
        path+=trail[junction+1:]
    if not close(path[-1],b['position']):path.append(b['position'])
    lengths=[dist(p,q) for p,q in zip(path,path[1:])]
    remaining=sum(lengths)*alpha
    for p,q,length in zip(path,path[1:],lengths):
        if length>1e-9 and remaining<=length:
            f=remaining/length
            return [x+(y-x)*f for x,y in zip(p,q)], math.degrees(math.atan2(q[0]-p[0],q[2]-p[2]))
        remaining-=length
    return b['position'][:], b['headingDeg']

async def run():
    for row,col in [(64,20),(50,20),(80,20),(40,25),(90,18)]:
        engine=GuardianEngine();windows=defaultdict(lambda:deque(maxlen=5));now=[1_800_000_000.0]
        async def ingest(frame):
            window=windows[frame['carrierId']]
            window.append({'telemetry':frame['telemetry'],'receivedAt':now[0]})
            return {**frame,'guardian':engine.predict(window)}
        fleet=FleetSimManager(ingest,clock=lambda:now[0]);fleet.speed_multiplier=24
        for i,rover in enumerate(fleet.rovers):
            r,c=row+(i%2)*2,col+i*2
            rover.survey=[(rr,c) for rr in range(r,min(r+35,fleet.rows-2))]
            rover.position=fleet._position(*rover.survey[0]);rover.cursor=1;rover.columns=(c-1,c+2)
            rover.trail.clear();rover.trail.append(rover.position[:]);rover.heading=0
        for _ in range(5):
            for rover in fleet.rovers:await fleet._observe(rover)
        if not all(r.guardian['riskLevel']=='nominal' for r in fleet.rovers):continue
        frames=[]
        def snap():
            state=fleet.state();state['running']=True;frames.append(state)
        snap()
        for _ in range(4):now[0]+=1;await fleet.step();snap()
        fault=len(frames)
        await fleet.control({'action':'fault','roverId':'fleet-rover-01','fault':'wheel_jam'});snap()
        fleet.speed_multiplier=120
        repair=validating=recovered=None
        for _ in range(90):
            now[0]+=1;await fleet.step();snap()
            phase=frames[-1]['rovers'][0]['recovery']['phase']
            if phase=='repairing' and repair is None:repair=len(frames)-1
            if phase=='validating' and validating is None:validating=len(frames)-1
            if phase=='recovered':recovered=len(frames)-1;break
        if recovered is None or repair is None or validating is None:continue
        fleet.speed_multiplier=24
        for _ in range(8):now[0]+=1;await fleet.step();snap()
        assert all(r['fault']=='nominal' and r['status']=='surveying' for r in frames[-1]['rovers'])
        # The last nominal pre-fault snapshot and the fault snapshot share a pose.
        # Keep the fleet moving while the caption calls out the stopped rover.
        knots=[(0,0),(4,fault),(6,fault+1),(14,repair),(21,validating),(24,recovered),(30,len(frames)-1)]
        dense=[]
        for n in range(900):
            t=n/30
            ta,ia,tb,ib=next((ta,ia,tb,ib) for (ta,ia),(tb,ib) in zip(knots,knots[1:]) if ta<=t<tb)
            index=ia+(ib-ia)*(t-ta)/(tb-ta)
            left=min(int(index),len(frames)-1);right=min(left+1,len(frames)-1);alpha=index-left
            a,b=frames[left],frames[right]
            state=deepcopy(a)
            state['elapsedS']=a['elapsedS']+(b['elapsedS']-a['elapsedS'])*alpha
            state['coverage']['percent']=a['coverage']['percent']+(b['coverage']['percent']-a['coverage']['percent'])*alpha
            for rover,ra,rb in zip(state['rovers'],a['rovers'],b['rovers']):
                p,h=interpolate_position(ra,rb,alpha)
                p[1]=fleet._surface((p[2]-fleet.points[0][2])/fleet.spacing_south,(p[0]-fleet.points[0][0])/fleet.spacing_east)[1]
                rover['position']=p;rover['headingDeg']=h
                if ra['recovery']['phase']==rb['recovery']['phase']:
                    rover['recovery']['progress']=ra['recovery']['progress']+(rb['recovery']['progress']-ra['recovery']['progress'])*alpha
                # Add the current acknowledged subsegment to the visible tail.
                rover['trail']=(ra.get('trail',[])+[p])[-100:]
            dense.append(state)
        # Verify continuity and physical service separation before any rendering.
        maximum=max(dist(a['position'],b['position']) for s1,s2 in zip(dense,dense[1:]) for a,b in zip(s1['rovers'],s2['rovers']))
        assert maximum<12, maximum
        assert all(dist(s['rovers'][0]['position'],dense[120]['rovers'][0]['position'])<1e-7 for s in dense[120:720])
        assert all(dist(s['rovers'][1]['position'],dense[420]['rovers'][1]['position'])<1e-7 for s in dense[420:630])
        repair_state=dense[16*30]
        target=repair_state['rovers'][0]
        helper=next(r for r in repair_state['rovers'] if r.get('targetId')==target['carrierId'])
        separation=math.hypot(target['position'][0]-helper['position'][0],target['position'][2]-helper['position'][2])
        assert 22<=separation<=26,separation
        data={'frames':dense,'timeline':{'fault':4,'approach':6,'repair':14,'validate':21,'recovered':24},
              'duration':30,'fps':30,'synthetic':True,'sourceSnapshotCount':len(frames),
              'backend':'unmodified FleetSimManager + GuardianEngine',
              'initialFormation':'staged adjacent survey lanes on archived HiRISE',
              'presentation':'authoritative route interpolation and phase-based editorial timing',
              'maximumStepM':maximum,'serviceDistanceM':separation,
              'sourceTimeline':{'fault':fault,'repair':repair,'validate':validating,'recovered':recovered}}
        output=options.output.resolve();output.parent.mkdir(exist_ok=True,parents=True)
        output.write_text(json.dumps(data),encoding='utf-8')
        print('SMOOTH_STORY_READY',len(dense),'frames','source',len(frames),'maximumStepM',round(maximum,3),'serviceDistanceM',round(separation,3),flush=True)
        return
    raise RuntimeError('No valid recovery scenario')
asyncio.run(run())
