/** Scene-neutral loader for a future MotionStudio / Game v8 host.
 * Supply the host's own THREE namespace and GLTFLoader constructor.
 * Creates no renderer, input listeners, game loop, or global state.
 */
export async function loadGeneratedCharacter({THREE, GLTFLoader, baseURL, expectedSha256, materialMode = 'texture'}) {
  const base = new URL(baseURL, globalThis.location?.href || 'http://localhost/');
  const response = await fetch(new URL('character.json', base));
  if (!response.ok) throw Error('Character metadata could not be loaded');
  const info = await response.json();
  const modelResponse = await fetch(new URL('character.glb', base));
  if (!modelResponse.ok) throw Error('Character GLB could not be loaded');
  const data = await modelResponse.arrayBuffer();
  const expected = expectedSha256 || info.output_sha256;
  if (expected) {
    const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', data));
    const actual = Array.from(bytes, x => x.toString(16).padStart(2, '0')).join('');
    if (actual !== expected) throw Error('Character model SHA-256 mismatch');
  }
  const gltf = await new GLTFLoader().parseAsync(data, base.href);
  if (materialMode === 'texture') gltf.scene.traverse(o => {
    if (!o.isMesh) return;
    const originals = Array.isArray(o.material) ? o.material : [o.material];
    const materials = originals.map(m => new THREE.MeshBasicMaterial({map:m.map,
      color:m.map?0xffffff:m.color,side:THREE.DoubleSide,transparent:m.transparent,
      opacity:m.opacity,alphaTest:m.alphaTest}));
    o.material=Array.isArray(o.material)?materials:materials[0];
    for(const m of originals)m.dispose();
  });
  const group = new THREE.Group(); group.add(gltf.scene);
  const mixer = new THREE.AnimationMixer(gltf.scene);
  const mapping = {idle:'Idle_preview',walk:'Walk_preview',jog:'Jog_preview',run:'Run_preview',jump:'Jump_preview'};
  const actions = {};
  for (const [mode, name] of Object.entries(mapping)) {
    const clip = gltf.animations.find(c => c.name === name);
    if (!clip) throw Error('Missing Taka clip: ' + name);
    actions[mode] = mixer.clipAction(clip);
  }
  let active;
  function play(mode, {rate = info.modes?.[mode]?.game_rate || 1} = {}) {
    if (!(rate > 0 && Number.isFinite(rate))) throw Error('Invalid playback rate');
    if (!actions[mode]) throw Error('Unknown mode: ' + mode);
    if (active === mode) { actions[mode].setEffectiveTimeScale(rate); return; }
    for (const action of Object.values(actions)) action.stop();
    const action = actions[mode]; action.reset().setEffectiveTimeScale(rate);
    action.setLoop(mode === 'jump' ? THREE.LoopOnce : THREE.LoopRepeat, mode === 'jump' ? 1 : Infinity);
    action.clampWhenFinished = mode === 'jump'; action.play(); active = mode;
  }
  play('idle');
  return {
    group, model:gltf.scene, info, mixer, actions, clips:gltf.animations,
    jumpTranslationBaked:true, coordinateSystem:'Y-up,+Z-forward',
    play,
    update(dt) { if(Number.isFinite(dt)) mixer.update(Math.max(0, Math.min(dt, .1))); },
    dispose() {
      mixer.stopAllAction(); mixer.uncacheRoot(gltf.scene); group.removeFromParent();
      const geometries=new Set(),materials=new Set(),textures=new Set();
      gltf.scene.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of (Array.isArray(o.material)?o.material:o.material?[o.material]:[])){materials.add(m);for(const value of Object.values(m))if(value?.isTexture)textures.add(value);}});
      for(const t of textures)t.dispose();for(const m of materials)m.dispose();for(const g of geometries)g.dispose();
    }
  };
}
