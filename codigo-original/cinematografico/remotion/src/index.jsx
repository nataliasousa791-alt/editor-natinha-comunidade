import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Piloto} from './Piloto';
import tl from './timeline.json';

const Root = () => (
  <Composition id="Piloto" component={Piloto} durationInFrames={tl.frames} fps={tl.fps} width={1080} height={1920} />
);
registerRoot(Root);
