import React,{useMemo} from 'react';

// Padrão Natinha aprovado: legenda branca e motion laranja integrado.
const ORANGE='#F59B43';
const clamp=x=>Math.max(0,Math.min(1,x));
const ease=x=>{x=clamp(x);return 1-Math.pow(1-x,3);};
const normalize=x=>String(x||'').toLocaleLowerCase('pt-BR').replace(/[.,;:?!]/g,'');
const GEOMETRY={
 '9x16':{left:66,top:350,width:948,height:420,normal:74,long:64,large:112,icon:94,maxRows:4,space:18},
 '16x9':{left:110,top:320,width:800,height:460,normal:56,long:48,large:82,icon:68,maxRows:5,space:12},
};

const Icon=({kind,t,start,size})=>{
 const q=ease((t-start)/.8),enter=ease((t-start)/.32);
 const props={fill:'none',stroke:ORANGE,strokeWidth:4.5,strokeLinecap:'round',strokeLinejoin:'round',pathLength:1,strokeDasharray:1,strokeDashoffset:1-q};
 return <svg width={size} height={size} viewBox="0 0 100 100" style={{overflow:'visible',opacity:enter,transform:'translateY('+((1-enter)*7)+'px)',flexShrink:0}} aria-hidden="true">
  {kind==='moon'&&<><path {...props} d="M70 13 A36 36 0 1 0 88 66 A38 38 0 0 1 70 13"/><path {...props} d="M86 11v14m-7-7h14" style={{opacity:ease((t-start-.5)/.4)}}/></>}
  {kind==='battery'&&<><rect {...props} x="7" y="29" width="79" height="43" rx="6"/><path {...props} d="M87 43h7v15h-7"/>{[0,1,2].map(i=><rect key={i} x={16+i*22} y="38" width="16" height="25" rx="2" fill={ORANGE} opacity={ease((t-start-.38-i*.27)/.35)}/>)}</>}
  {kind==='shield'&&<><path {...props} d="M50 10 C65 22 78 26 85 26 V45 C85 66 69 82 50 92 C31 82 15 66 15 45 V26 C25 25 39 17 50 10 Z"/><path {...props} d="M32 49l12 12 24-26" strokeDashoffset={1-ease((t-start-.52)/.42)}/></>}
 </svg>;
};

const STOP=new Set(['a','o','as','os','de','da','do','das','dos','e','que','se','pra','para','com','em','no','na','sua','seu']);
function fitRows(words,width,normal,large,focusIndex,iconWidth,space) {
 const wordWidth=(w,i)=>Math.max(normal*.9,(w.w||'').length*(i===focusIndex?large:normal)*.54)+(i===focusIndex?iconWidth+12:0);
 const rows=[];let row=[],sum=0;
 words.forEach((word,i)=>{
  const wd=wordWidth(word,i);
  if(row.length && sum+wd+space>width){rows.push(row);row=[];sum=0;}
  row.push({...word,index:i});sum+=wd+space;
 });
 if(row.length)rows.push(row);
 for(let i=0;i<rows.length-1;i++){
  while(rows[i].length>1&&STOP.has(normalize(rows[i][rows[i].length-1].w))){
   const w=rows[i][rows[i].length-1],next=rows[i+1];
   const currentNext=next.reduce((a,x)=>a+wordWidth(x,x.index)+space,0);
   if(currentNext+wordWidth(w,w.index)+space>width)break;
   next.unshift(rows[i].pop());
  }
 }
 return rows;
}

export const MotionCaption=({t,cues=[],formato='9x16'})=>{
 const cfg=GEOMETRY[formato]||GEOMETRY['9x16'];
 const activeCue=cues.find(c=>t>=c.ini&&t<c.fim)||null;
 const layout=useMemo(()=>{
  if(!activeCue)return null;
  const words=activeCue.palavras||[],focusIndex=Number.isInteger(activeCue.focusIndex)?activeCue.focusIndex:-1;
  const characters=words.reduce((a,w)=>a+(w.w||'').length,0);
  let normal=characters>55?cfg.long:cfg.normal;
  let large=cfg.large;
  const focused=focusIndex>=0?words[focusIndex]:null;
  if(focused)large=Math.min(large,(cfg.width-cfg.icon-36)/Math.max(1,focused.w.length*.56));
  large=Math.max(normal,Math.floor(large));
  let rows=fitRows(words,cfg.width-26,normal,large,focusIndex,focused&&activeCue.icon?cfg.icon:0,cfg.space);
  let attempts=0;
  while(rows.length>cfg.maxRows&&attempts<5){
   normal=Math.max(36,normal*.91);large=Math.max(normal,large*.93);
   rows=fitRows(words,cfg.width-26,normal,large,focusIndex,focused&&activeCue.icon?cfg.icon:0,cfg.space);
   attempts++;
  }
  return {rows,normal,large,focusIndex};
 },[activeCue,formato]);
 if(!activeCue||!layout)return null;
 const trigger=activeCue.trigger??activeCue.ini;
 const progress=ease((t-trigger)/.36);
 const appeared=t>=trigger-.05;
 return <div data-caption="continuous" style={{position:'absolute',left:cfg.left,top:cfg.top,width:cfg.width,height:cfg.height,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',textAlign:'center',color:'#FFFFFF',fontFamily:'Poppins',fontWeight:700,textShadow:'0 3px 15px rgba(0,0,0,.82)',WebkitTextStroke:'.6px rgba(0,0,0,.45)',paintOrder:'stroke fill',pointerEvents:'none'}}>
  {layout.rows.map((row,i)=><div key={i} style={{display:'flex',justifyContent:'center',alignItems:'baseline',gap:cfg.space,lineHeight:1.18,minHeight:layout.focusIndex>=0?layout.large*1.16:layout.normal*1.22}}>
   {row.map(w=>{
    const focus=w.index===layout.focusIndex;
    return <span key={w.index} data-word={w.w} style={{display:'inline-flex',alignItems:'center',position:'relative',gap:focus?8:0,fontSize:focus?layout.large:layout.normal,lineHeight:1.18,whiteSpace:'nowrap'}}>
     <span style={{display:'inline-block',transform:focus?'scale('+(appeared?(.92+.08*progress):.92)+')':undefined,transformOrigin:'50% 75%'}}>{w.w}</span>
     {focus&&<svg width="100%" height="24" viewBox="0 0 300 24" preserveAspectRatio="none" style={{position:'absolute',left:0,bottom:-10,opacity:appeared?1:0,pointerEvents:'none'}}><path d="M4 17 Q150 1 296 12" fill="none" stroke={ORANGE} strokeWidth="4" strokeLinecap="round" pathLength="1" strokeDasharray="1" strokeDashoffset={1-progress}/></svg>}
     {focus&&activeCue.icon&&<Icon kind={activeCue.icon} t={t} start={trigger} size={cfg.icon}/>}
    </span>;
   })}
  </div>)}
 </div>;
};
