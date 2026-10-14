import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {PilotoV6} from './PilotoV6';
import tl from './timeline.json';

const Root = () => (
  <Composition id="PilotoV6" component={PilotoV6} durationInFrames={tl.frames} fps={tl.fps} width={1080} height={1920} />
);
registerRoot(Root);
