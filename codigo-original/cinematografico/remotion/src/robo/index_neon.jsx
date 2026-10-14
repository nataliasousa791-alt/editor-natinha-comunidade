import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {RoboNeon} from './RoboNeon';

const vazio = {fps: 30, frames: 30, formato: '9x16', cenas: [], legendas: [], segs: [],
  fonte: {arquivo: 'natinha.mp4', w: 1080, h: 1920, rosto: {cx: 0.5, cy: 0.4, h: 0.3, w: 0.2}}, audio: 'voz.m4a'};
const DIM = {'9x16': [1080, 1920], '16x9': [1920, 1080]};

registerRoot(() => (
  <Composition id="RoboNeon" component={RoboNeon} width={1080} height={1920} fps={30} durationInFrames={30} defaultProps={vazio}
    calculateMetadata={({props}) => {
      const [width, height] = DIM[props.formato || '9x16'];
      return {durationInFrames: Math.max(1, props.frames), fps: props.fps, width, height};
    }} />
));
