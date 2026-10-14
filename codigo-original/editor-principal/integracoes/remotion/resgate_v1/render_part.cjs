const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {createRequire}=require('node:module'),{execFileSync}=require('node:child_process');
const config=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const localRequire=createRequire(path.join(config.remotionRoot,'package.json'));
const {bundle}=localRequire('@remotion/bundler');
const {selectComposition,renderFrames,renderStill}=localRequire('@remotion/renderer');
try{os.networkInterfaces();}catch{os.networkInterfaces=()=>({lo:[{address:'127.0.0.1',netmask:'255.0.0.0',family:'IPv4',mac:'00:00:00:00:00:00',internal:true,cidr:'127.0.0.1/8'}]});}
(async()=>{
 const started=Date.now();
 const props={...config.plan,semLegendas:true,semAudio:true};
 const motion=props.captionMode==='motion_orange_v1';
 const marker=path.join(config.bundleDir,'resgate_bundle_ok.json');
 if(!fs.existsSync(marker)){
  await bundle({entryPoint:path.join(__dirname,'src/robo/index.jsx'),publicDir:config.publicDir,outDir:config.bundleDir,
   webpackOverride:x=>({...x,resolve:{...x.resolve,modules:[path.join(config.remotionRoot,'node_modules'),...(x.resolve.modules||['node_modules'])]}})});
  fs.writeFileSync(marker,JSON.stringify({version:1}));
 }
 const common={serveUrl:config.bundleDir,inputProps:props,browserExecutable:process.env.NATINHA_BROWSER||undefined,
  logLevel:'warn',offthreadVideoCacheSizeInBytes:128*1024*1024,mediaCacheSizeInBytes:256*1024*1024};
 const composition=await selectComposition({...common,id:'Robo'});
 if(config.still!==undefined){await renderStill({...common,composition,frame:config.still,output:config.output,imageFormat:'png'});return;}
 const partOutput=config.output+'.partial.mp4';
 const temp=fs.mkdtempSync(path.join(config.cacheDir,'quadros_temporarios_'));
 try{
  fs.mkdirSync(path.join(temp,'frames'));
  if(!motion)fs.copyFileSync(config.assPath,path.join(temp,'legendas.ass'));
  fs.cpSync(path.join(config.publicDir,'fonts'),path.join(temp,'fonts'),{recursive:true});
  await renderFrames({...common,composition,frameRange:[config.start,config.end-1],outputDir:path.join(temp,'frames'),
   concurrency:1,offthreadVideoThreads:1,imageFormat:'jpeg',jpegQuality:95,muted:true});
  const names=fs.readdirSync(path.join(temp,'frames')).filter(x=>/\.(jpg|jpeg)$/.test(x)).sort();
  if(names.length!==config.end-config.start)throw Error('Número de quadros divergente');
  const match=names[0].match(/(\d+)\.(jpeg|jpg)$/);
  const pattern=names[0].replace(match[0],`%0${match[1].length}d.${match[2]}`);
  execFileSync('ffmpeg',['-nostdin','-v','error','-y','-framerate',String(props.fps),'-start_number',String(Number(match[1])),
   '-i',path.join('frames',pattern),...(motion?[]:['-vf','ass=legendas.ass:fontsdir=fonts']),'-frames:v',String(names.length),'-an',
   '-c:v','libx264','-preset','fast','-crf','18','-profile:v','high','-g',String(props.fps),'-bf','0','-pix_fmt','yuv420p','-threads','2',partOutput],
   {cwd:temp,stdio:'inherit'});
  const fd=fs.openSync(partOutput,'r+');fs.fsyncSync(fd);fs.closeSync(fd);
  fs.renameSync(partOutput,config.output);
 }finally{
  // Limpeza exclusiva do temporário criado nesta chamada. Nenhum MP4 anterior é removido.
  fs.rmSync(temp,{recursive:true,force:true});
 }
 console.log(JSON.stringify({start:config.start,end:config.end,seconds:(Date.now()-started)/1000,nodeRSSMiB:process.memoryUsage().rss/1048576}));
})().catch(e=>{console.error(e);process.exit(1)});

