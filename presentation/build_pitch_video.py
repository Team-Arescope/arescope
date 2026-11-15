"""Create a strict seven-slide pitch, including the playable demo and closing."""
import base64
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
source = ROOT / 'Arescope — NASA Space Apps Challenge 2026.html'
movie = ROOT / 'demo/Arescope-Fleet-Demo-30s.mp4'
poster = ROOT / 'demo/Arescope-Fleet-Demo-30s.png'
original = source.read_text(encoding='utf-8')
assert len(re.findall(r'<section class="slide', original)) == 7

css = """
/* Full-frame demo uses the same 16:9 canvas as the seven-slide source. */
.demo-slide,.demo-slide.on{background:#0d0907;transform:none!important;filter:none!important;transition:opacity .25s,visibility 0s!important}
.demo-video{display:block;width:1280px;height:720px;object-fit:contain;background:#0d0907}
body.video-slide-active .hud,body.video-slide-active #dots,body.video-slide-active #nav,body.video-slide-active #bar,body.video-slide-active #hint{visibility:hidden!important;pointer-events:none!important}
.demo-action{position:absolute;right:34px;bottom:110px;z-index:3;padding:12px 19px;border:1px solid #ee8a5b;border-radius:6px;background:#160e0bf0;color:#eee2d9;font:500 16px Manrope,sans-serif;cursor:pointer}
.demo-action[hidden],.demo-error[hidden]{display:none!important}
.demo-action:focus-visible{outline:2px solid #f2b28e;outline-offset:4px}
.demo-error{position:absolute;left:48px;right:48px;top:44px;padding:14px 20px;background:#160e0bf0;border:1px solid #ee8a5b;border-radius:6px;font:16px Manrope,sans-serif;color:#eee2d9}
.demo-error a{color:#f2b28e}
.merged-problem .story-grid{grid-template-columns:5fr 5.7fr;gap:34px}
.merged-problem .story-copy h2{font-size:32px;line-height:1.2;margin:8px 0 14px}
.merged-problem .story-lines p{font-size:17px;line-height:1.5;margin:0 0 10px}
.merged-problem .delay-signal{padding:10px 0;margin:4px 0 14px}
.merged-problem .delay-signal strong{font-size:34px}
.merged-risk-list{display:grid;gap:12px;margin:0}
.merged-risk-list div{padding-left:12px;border-left:2px solid var(--copper)}
.merged-risk-list dt{font-size:16px;font-weight:600;color:var(--paper);line-height:1.4}
.merged-risk-list dd{font-size:14px;line-height:1.45;color:var(--muted);margin:3px 0 0}
.merged-problem .bridge{font-size:13px;line-height:1.5;margin:14px 0 10px}
.merged-problem .source-note{font-size:11px;line-height:1.5;margin:0}
"""

slide = """
  <!-- PITCH SLIDE 05: EMBEDDED THIRTY-SECOND DEMONSTRATION -->
  <section class="slide demo-slide" data-p="855,-380,.66,0" data-label="Fleet Recovery Demo" aria-label="Slide 5: Thirty-second simulated fleet recovery demonstration">
    <video id="fleet-demo-video" class="demo-video" controls muted playsinline preload="metadata" poster="__POSTER__" aria-label="Arescope fleet survey, wheel obstruction, neighbour assistance and validated recovery. Thirty seconds.">
      <source src="__MOVIE__" type="video/mp4">
      Your browser cannot play this video. <a href="https://arescope.mrfenek.eu.cc/static/demo/Arescope-Fleet-Demo-30s.mp4">Open the public demo</a>.
    </video>
    <button id="demo-play" class="demo-action" type="button" data-video-ui hidden>Play 30-second demo</button>
    <button id="demo-next" class="demo-action" type="button" data-video-ui hidden>Continue to results →</button>
    <p id="demo-error" class="demo-error" data-video-ui role="status" hidden>The video could not play. <a href="https://arescope.mrfenek.eu.cc/static/demo/Arescope-Fleet-Demo-30s.mp4" target="_blank" rel="noopener">Open the public recording</a>.</p>
    <aside class="speaker-notes" hidden data-seconds="30">Let the thirty-second clip play. Three simulated rovers survey archived HiRISE terrain. A wheel obstruction halts Rover 01, a healthy neighbour performs simulated service, Guardian checks fresh data, and the pair resumes surveying. Time and initial formation are staged for this software demonstration. Physical rover repair has not been validated. Continue to the evidence slide when the clip ends. Space pauses or resumes; leaving the slide stops playback.</aside>
  </section>

"""

media_js = """
// Native video stays on the presentation clock and never plays on hidden slides.
const demoVideo=document.getElementById('fleet-demo-video'),
      demoPlay=document.getElementById('demo-play'),
      demoNext=document.getElementById('demo-next');
let demoWasActive=false;
function startDemo(){
  if(!S[i].classList.contains('demo-slide'))return;
  if(demoVideo.ended)demoVideo.currentTime=0;
  demoNext.hidden=true;
  const attempt=demoVideo.play();
  attempt?.then(()=>{demoPlay.hidden=true}).catch(()=>{demoPlay.hidden=false});
}
function syncDemo(){
  const active=S[i].classList.contains('demo-slide');
  document.body.classList.toggle('video-slide-active',active);
  if(active&&!demoWasActive){
    demoVideo.currentTime=0;demoNext.hidden=true;demoPlay.hidden=true;
    document.getElementById('demo-error').hidden=true;
    startDemo();
  }else if(!active){
    demoVideo.pause();demoNext.hidden=true;demoPlay.hidden=true;
  }
  demoWasActive=active;
}
demoPlay.onclick=e=>{e.stopPropagation();startDemo()};
demoNext.onclick=e=>{e.stopPropagation();go(i+1)};
demoVideo.addEventListener('ended',()=>{
  if(S[i].classList.contains('demo-slide')){demoNext.hidden=false;demoNext.focus({preventScroll:true})}
});
demoVideo.addEventListener('error',()=>{document.getElementById('demo-error').hidden=false;demoPlay.hidden=true});
"""

def replace_once(text, before, after):
    assert text.count(before) == 1, f'Expected one source anchor: {before[:75]}'
    return text.replace(before, after, 1)

pitch = original
merged_copy = """<div class="story-copy">
          <div class="r kick">The problem · Mars rover operations</div>
          <h2 class="r">Rover risks and delayed help</h2>
          <div class="story-lines"><p class="r">In 2009, Spirit broke through a thin crust into soft sand at Troy.</p></div>
          <div class="r delay-signal"><strong>3–22 min</strong><span class="mono">Earth signal delay · one way</span></div>
          <dl class="merged-risk-list">
            <div class="r"><dt>Dust, glare &amp; low texture</dt><dd>Cameras lose reliable visual landmarks.</dd></div>
            <div class="r"><dt>Wheel slip &amp; obstruction</dt><dd>Motion can stall in soft terrain.</dd></div>
            <div class="r"><dt>Sensor &amp; link dropout</dt><dd>Missing data interrupts the mission view.</dd></div>
          </dl>
          <p class="r bridge">Arescope connects risk warnings, coordinated help and operator review.</p>
          <p class="r source-note"><a href="https://science.nasa.gov/photojournal/spirits-view-from-troy/" target="_blank" rel="noopener">NASA/JPL · Spirit at Troy</a><br><a href="https://science.nasa.gov/blog/speaking-percys-language-how-to-talk-so-perseverance-will-listen/" target="_blank" rel="noopener">NASA · Mars communication delay</a></p>
        </div>
        """
start=pitch.index('<div class="story-copy">')
end=pitch.index('<div class="r c troy-card"',start)
pitch=pitch[:start]+merged_copy+pitch[end:]
pitch=replace_once(pitch,'class="slide" data-p="940,390,.88,12" data-label="Backstory · 2009"',
                   'class="slide merged-problem" data-p="940,390,.88,12" data-label="Rover Risks"')
start=pitch.index('  <!-- SLIDE 03: THE PROBLEM -->')
end=pitch.index('<!-- SLIDE 04: MISSION CONTROL AND SENSOR TESTBED -->',start)
pitch=pitch[:start]+pitch[end:]
pitch=re.sub(r'<aside class="speaker-notes" hidden data-seconds="25">0:15–0:40\..*?</aside>',
    '<aside class="speaker-notes" hidden data-seconds="35">Spirit broke through a thin crust at Troy in 2009. A signal takes 3–22 minutes one way between Earth and Mars. Dust, glare, low texture, wheel slip, obstructions, and sensor or link dropout can degrade mission awareness. Arescope joins risk warnings, coordinated assistance and reviewed learning. The Troy drawing is illustrative and does not claim hidden-soil detection or that Arescope would have saved Spirit. Sources: NASA/JPL Spirit’s View from Troy; NASA Speaking Percy’s Language; NASA Self-Driving Perseverance Takes the Wheel.</aside>',pitch,count=1)
pitch = replace_once(pitch, '</head>', '<style>\n' + css + '\n</style>\n</head>')
pitch = replace_once(pitch, '  <!-- SLIDE 06: WHAT WORKS TODAY -->', slide + '  <!-- PITCH SLIDE 06: WHAT WORKS TODAY -->')
pitch = pitch.replace('Survey about 40 km² with 1–6 simulated rovers and coordinate inspection assistance.',
                      'Survey about 40 km² with 1–6 simulated rovers and coordinate simulated recovery.')
pitch = pitch.replace('Simulated rovers share coverage. Guardian flags risk and a coordinator dispatches an inspection rover.',
                      'Simulated rovers share coverage. Neighbours handle minor faults; serious failures need operator approval.')
pitch = pitch.replace('Fleet survey, inspection assistance and reviewed model updates.',
                      'Fleet survey, simulated recovery and reviewed model updates.')
pitch = pitch.replace('Simulated assistance is inspection at a standoff distance, not automatic repair.',
                      'Minor-fault service is simulated. Serious failures require operator approval. Physical repair remains unvalidated.')
old_notes = re.search(r'(<aside class="speaker-notes" hidden data-seconds=")40(">2:05–2:45\..*?</aside>)',pitch)
assert old_notes
pitch = pitch[:old_notes.start()] + '<aside class="speaker-notes" hidden data-seconds="25">The previous slide shows the simulated recovery workflow. These metrics describe an adapted Guardian model on a separate frozen synthetic hold-out, not a physical rover trial or the active production model. The baseline caught 26 of 30 faults; after reviewed synthetic adaptation, the model caught 30 of 30. Mean lead time is 14.8 seconds and false alarms cover 11 of 492 nominal windows. Model activation requires operator review.</aside>' + pitch[old_notes.end():]
pitch = replace_once(pitch, 'const dotBtns=[...dotsEl.querySelectorAll(\'button\')];',
                     'const dotBtns=[...dotsEl.querySelectorAll(\'button\')];\n' + media_js)
pitch = replace_once(pitch, "function upd(){", "function upd(){\n  syncDemo();")
pitch = replace_once(pitch, "#nav,#dots,#troyCard,#linkBar,button,a", "#nav,#dots,#troyCard,#linkBar,button,a,video,[data-video-ui]")
key_anchor = "document.addEventListener('keydown',e=>{\n  if(e.defaultPrevented"
key_patch = """document.addEventListener('keydown',e=>{
  if(S[i].classList.contains('demo-slide')&&!e.ctrlKey&&!e.metaKey&&!e.altKey){
    if(e.key===' '&&!e.target.closest?.('button,a')){
      e.preventDefault();demoVideo.paused?startDemo():demoVideo.pause();return;
    }
    if(e.target.closest?.('video')&&!['PageDown','PageUp','Home','End','f','F'].includes(e.key))return;
  }
  if(e.defaultPrevented"""
pitch = replace_once(pitch, key_anchor, key_patch)
pitch = replace_once(pitch, "button,a,[role=\"button\"],#linkBar", "button,a,video,[data-video-ui],[role=\"button\"],#linkBar")
pitch = replace_once(pitch, "(function f(t){\n  cx.clearRect", "(function f(t){\n  if(document.body.classList.contains('video-slide-active')){requestAnimationFrame(f);return;}\n  cx.clearRect")
assert len(re.findall(r'<section class="slide', pitch)) == 7
slide_number=iter(range(1,8))
pitch=re.sub(r'(<section class="slide[^>]*aria-label=")Slide \d+:',
             lambda match:match[1]+f'Slide {next(slide_number)}:',pitch)
assert len(re.findall(r'aria-label="Slide [1-7]:',pitch))==7

for standalone in (False, True):
    html = pitch
    if standalone:
        movie_src = 'data:video/mp4;base64,' + base64.b64encode(movie.read_bytes()).decode()
        poster_src = 'data:image/png;base64,' + base64.b64encode(poster.read_bytes()).decode()
    else:
        movie_src, poster_src = 'demo/' + movie.name, 'demo/' + poster.name
    html = html.replace('__MOVIE__', movie_src).replace('__POSTER__', poster_src)
    name = 'Arescope-V2-Pitch-With-Demo' + ('-Standalone' if standalone else '') + '.html'
    output = ROOT/name
    output.write_text(html, encoding='utf-8')
    print(name, output.stat().st_size, 'bytes')

assert source.read_text(encoding='utf-8') == original
