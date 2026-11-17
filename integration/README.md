# MotionStudio v8 integration

`motionstudio-adapter.js` is a scene-neutral ES module. It uses the host application's
Three.js instance; it does not create a renderer, attach keyboard handlers or modify a game.

```js
import {loadGeneratedCharacter} from './motionstudio-adapter.js';
const character = await loadGeneratedCharacter({
  THREE, GLTFLoader, baseURL: './generated/my-character/'
});
scene.add(character.group);
character.play('walk');
// In the host's animation loop:
character.update(deltaSeconds);
// On removal:
character.dispose();
```

The directory must contain `character.glb` and `character.json` from feature 10.
The loader checks the model hash and the five named clips. Translation of the outer
group is controlled by the host. The jump's vertical displacement is already baked;
do not add another physics jump on top. Host physics integration must explicitly
choose one source of vertical motion.

This prepares a stable loading boundary for v8. It does not install itself into an
existing game, replace its player, or automatically retarget arbitrary new Kimodo /
MotionBricks motion onto this generated rig. Those connections belong in the v8 host.

The default display uses the baked color texture to avoid a dark metallic appearance
without an environment map. Pass `materialMode: 'original'` to retain original PBR
materials and provide suitable lighting in the host. Playback uses the recorded
game rates unless an explicit rate is supplied.
