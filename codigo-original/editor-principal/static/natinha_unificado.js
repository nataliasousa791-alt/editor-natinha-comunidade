/* Painel Natinha unificado. Mantém os contratos de APIs de cada motor sem reescrevê-los. */
'use strict';
const NatinhaUI={modo:'classico', arquivo:null, enviando:false, shown:null, tocouModo:false, driveAtual:null};
function uiEsc(t){
  return String(t==null?'':t).replace(/[&<>"']/g,function(ch){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]});
}
function uiSetMsg(msg,erro){
  const x=document.getElementById('ui-feedback');
  if(x){x.textContent=msg||''; x.className='ui-notice'+(erro?' is-error':'');x.setAttribute('role','status');}
}
function uiStep(n,t,small){
  return '<div class="ui-step-head"><div class="step-id">'+n+'</div><h3>'+t+'</h3><small>'+small+'</small></div>';
}
function uiMode(id,ico,titulo,desc){
  const on=NatinhaUI.modo===id;
  return '<button type="button" class="mode-choice'+(on?' selected':'')+'" data-mode="'+id+'" aria-pressed="'+on+'" onclick="uiEscolherModo(\''+id+'\')">'+
    '<span class="mode-ico">'+ico+'</span><span class="tick">'+(on?'✓':'')+'</span><strong>'+titulo+'</strong><span class="desc">'+desc+'</span></button>';
}
function telaInicioUnificada(){
  const root=document.getElementById('app'); if(!root)return;
  root.innerHTML=
   '<div class="ui-hero"><div><div class="eyebrow">Seu estúdio de edição</div><h2>O que vamos criar hoje?</h2>'+
   '<p>Um vídeo de entrada, cinco maneiras de editar. Você escolhe o resultado. O editor cuida do resto.</p></div><div class="hero-mark" aria-hidden="true">🎬</div></div>'+
   '<section class="ui-panel">'+uiStep('1','Escolha seu vídeo','MP4, MOV ou outro vídeo comum')+
   '<div class="file-drop" id="ui-drop" tabindex="0" role="button" aria-label="Selecionar vídeo">'+
   '<div class="big" aria-hidden="true">↥</div><b id="ui-file-name">Clique ou arraste seu vídeo aqui</b>'+
   '<span id="ui-file-sub">Pode selecionar um arquivo do computador ou celular</span></div>'+
   '<input type="file" accept="video/*" id="ui-file" hidden>'+
   '<div class="ui-or"><span>OU</span></div>'+
   '<label for="ui-path">Vídeo que já está no PC do editor</label>'+
   '<input id="ui-path" type="text" autocomplete="off" placeholder="Cole aqui o caminho completo do vídeo no PC">'+
   '<div class="field-note">Para arquivos grandes no PC do editor, usar o caminho é mais rápido que enviar novamente.</div></section>'+
   '<section class="ui-panel">'+uiStep('2','Que resultado você quer?','Escolha uma opção')+
   '<div class="ui-choice-grid" id="ui-choices">'+
    uiMode('hibrido','⚡','Natinha Híbrido (beta)','FFmpeg nos trechos comuns e Remotion apenas nas cenas-chave. Prévia experimental.')+
    uiMode('pacote','🎬','Pacote cinematográfico completo','Um YouTube com Remotion + até três cortes cinematográficos.')+
    uiMode('classico','🎞️','Vídeo completo + cortes','Edição automática tradicional: YouTube, vídeos curtos e legendas.')+
    uiMode('vertical','✨','Cortes cinematográficos','Vídeos verticais com Remotion, legendas e imagens de apoio.')+
    uiMode('youtube','📺','YouTube cinematográfico','Vídeo horizontal com imagens, motion e edição documental.')+
   '</div><div class="mode-options" id="ui-mode-options"></div>'+
   '<div class="ui-drive-bar"><div><strong>📱 Vídeos enviados pelo Drive</strong><p id="ui-drive-status" class="field-note">Carregando o modo automático...</p></div>'+
   '<button type="button" id="ui-drive-save" onclick="uiSalvarModoDrive()">Usar a opção selecionada no Drive</button></div>'+
   '<p id="ui-drive-feedback" class="field-note" aria-live="polite"></p></section>'+
   '<section class="ui-panel">'+uiStep('3','Começar a edição','Tudo pronto?')+
   '<div class="ui-actions"><button class="pri big-start" id="ui-start" type="button" onclick="uiEnviar()">▶ Começar edição</button>'+
   '<span class="ui-status">Acompanhe por aqui e revise antes de publicar.</span></div>'+
   '<div id="ui-feedback" class="ui-notice" aria-live="polite"></div>'+
   '<div class="ui-warning">Os motores ficam separados por segurança. Enquanto outro vídeo estiver renderizando, aguarde para não sobrecarregar o PC.</div></section>'+
   '<section class="ui-panel"><div class="ui-section-row"><h2>Seus vídeos recentes</h2>'+
   '<button onclick="ir(\'historico\')">Ver todos →</button></div><div class="ui-project-list" id="ui-history">'+
   '<div class="ui-empty">Buscando projetos...</div></div></section>'+
   '<section class="ui-panel"><details class="ui-advanced"><summary>Outras versões e funções avançadas</summary>'+
   '<div class="ui-help">As versões antigas V1, V2, V3 e V3.1 continuam no modo “Vídeo completo + cortes”. '+
   'A V4 é um laboratório separado e ainda não foi liberada como opção automática deste painel. '+
   'Você pode <a href="/static/painel_anterior.html">comparar com o visual antigo</a> ou abrir o <a href="/remotion">painel técnico do Remotion</a>, se precisar.</div></details></section>';
  uiConectarArquivo();uiEscolherModo(NatinhaUI.modo, true);uiConsultarModoDrive();carregarHistoricoUI('ui-history',6);
}
function uiConectarArquivo(){
  const d=document.getElementById('ui-drop'),a=document.getElementById('ui-file');
  d.onclick=function(){a.click();};
  d.onkeydown=function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();a.click();}};
  d.ondragover=function(e){e.preventDefault();d.classList.add('dragging');};
  d.ondragleave=function(){d.classList.remove('dragging');};
  d.ondrop=function(e){e.preventDefault();d.classList.remove('dragging');if(e.dataTransfer.files[0])uiDefinirArquivo(e.dataTransfer.files[0]);};
  a.onchange=function(){if(a.files[0])uiDefinirArquivo(a.files[0]);};
  document.getElementById('ui-path').oninput=function(){
    if(this.value.trim()&&NatinhaUI.arquivo){NatinhaUI.arquivo=null;a.value='';
      d.classList.remove('selected');document.getElementById('ui-file-name').textContent='Clique ou arraste seu vídeo aqui';
      document.getElementById('ui-file-sub').textContent='Pode selecionar um arquivo do computador ou celular';}
  };
}
function uiDefinirArquivo(f){
  NatinhaUI.arquivo=f;
  const d=document.getElementById('ui-drop');
  d.classList.add('selected');
  document.getElementById('ui-file-name').textContent='✓ '+f.name;
  document.getElementById('ui-file-sub').textContent=(f.size/1024/1024).toFixed(1)+' MB · arquivo selecionado';
  document.getElementById('ui-path').value='';
  uiSetMsg('');
}
function uiEscolherModo(m, inicial){
  if(!inicial)NatinhaUI.tocouModo=true;
  NatinhaUI.modo=m;
  document.querySelectorAll('#ui-choices .mode-choice').forEach(function(x){
    const active=x.dataset.mode===m;x.classList.toggle('selected',active);
    x.setAttribute('aria-pressed',String(active));x.querySelector('.tick').textContent=active?'✓':'';
  });
  const t=document.getElementById('ui-mode-options');if(!t)return;
  if(m==='classico'){
    t.innerHTML='<h4>Edição completa automática</h4><p class="sub" style="margin:0">Cria uma versão para YouTube, cortes e legendas conforme o editor tradicional.</p>'+
    '<details class="ui-advanced" style="margin-top:10px"><summary>Escolher versão antiga (opcional)</summary>'+
    '<label for="ui-version">Motor do editor clássico</label><select id="ui-version"><option value="">Carregando versões...</option></select></details>';
    api('/api/versoes').then(function(v){
      const sel=document.getElementById('ui-version');if(!sel)return;
      sel.innerHTML=(v.lista||[]).map(function(x){
        return '<option value="'+uiEsc(x.id)+'"'+(x.id===v.padrao?' selected':'')+'>'+uiEsc(x.nome)+'</option>';
      }).join('');
    }).catch(function(){const sel=document.getElementById('ui-version');if(sel)sel.innerHTML='<option value="v3.1">V3.1 (alternativa)</option>';});
  }else if(m==='pacote'||m==='hibrido'){
    t.innerHTML='<h4>'+(m==='hibrido'?'Híbrido experimental: YouTube + até 3 cortes':'Um envio, quatro vídeos cinematográficos')+'</h4>'+ 
      '<p class="sub" style="margin:0">'+(m==='hibrido'?'FFmpeg acelera a maior parte do vídeo; o Remotion aparece só em algumas cenas. Beta ainda sem tempo de produção comprovado.':'O motor monta primeiro o YouTube 16:9 com imagens e animações, depois escolhe até três momentos para cortes 9:16. Tudo com Remotion, em sequência.')+'</p>'+ 
      '<div class="ui-cols"><div><label for="ui-nc">Cortes verticais</label><select id="ui-nc"><option value="3" selected>3 cortes (quando houver conteúdo suficiente)</option><option value="2">2 cortes</option><option value="1">1 corte</option></select></div>'+ 
      '<div><label for="ui-alvo">Duração aproximada de cada corte</label><select id="ui-alvo"><option value="45">Até 1 minuto</option><option value="90" selected>Até 2 minutos</option><option value="120">Até 2 minutos e meio</option></select></div></div>'+uiOnlineHTML();
  }else if(m==='vertical'){
    t.innerHTML='<h4>Cortes verticais com Remotion</h4><p class="sub" style="margin:0">O editor escolhe os momentos e monta até três vídeos verticais.</p>'+
    '<div class="ui-cols"><div><label for="ui-nc">Quantos cortes?</label><select id="ui-nc"><option value="1">1 corte</option>'+
    '<option value="2" selected>2 cortes</option><option value="3">3 cortes</option></select></div>'+
    '<div><label for="ui-alvo">Tempo aproximado de cada um</label>'+
    '<select id="ui-alvo"><option value="30">30 segundos</option><option value="60" selected>1 minuto</option>'+
    '<option value="90">1 minuto e meio</option><option value="120">2 minutos</option></select></div></div>'+
    uiOnlineHTML();
  }else{
    t.innerHTML='<h4>Editar um vídeo horizontal para o YouTube</h4>'+
    '<div><label for="ui-estilo">Como você quer o vídeo?</label>'+
    '<select id="ui-estilo"><option value="completo">Cinematográfico: imagens e animações (Remotion)</option>'+
    '<option value="limpo">Só limpar a fala e organizar o vídeo (mais simples)</option></select></div>'+
    '<p class="field-note">O estilo mais simples usa FFmpeg. O cinematográfico usa Remotion e pode demorar mais.</p>'+uiOnlineHTML();
  }
  const botao=document.getElementById('ui-start');
  if(botao&&!NatinhaUI.enviando)botao.disabled=m==='pacote'||m==='hibrido';
  if(m==='pacote'||m==='hibrido'){
    NatinhaUI.pacoteDisponivel=false;
    uiSetMsg('Verificando se o pacote já está disponível…');
    fetch('/api/remotion/capacidades').then(function(r){if(!r.ok)throw Error('ainda não carregado');return r.json();}).then(function(resp){
      if(NatinhaUI.modo!=='pacote'&&NatinhaUI.modo!=='hibrido')return;
      NatinhaUI.pacoteDisponivel=Boolean(m==='hibrido'?resp.hibrido_beta:resp.pacote_cinematografico);
      if(botao&&!NatinhaUI.enviando)botao.disabled=!NatinhaUI.pacoteDisponivel;
      uiSetMsg(NatinhaUI.pacoteDisponivel?'Pacote completo disponível. Um envio gera o YouTube e os cortes.':'Nova opção ainda não ativada.');
    }).catch(function(){if(NatinhaUI.modo==='pacote'||NatinhaUI.modo==='hibrido')uiSetMsg('Motor indisponível temporariamente. O modo anterior continua funcionando.',true);});
  }else uiSetMsg('');
}
function uiOnlineHTML(){
  return '<label class="ui-toggle" style="margin-top:15px"><input type="checkbox" id="ui-online">'+
  '<span>Usar IA gratuita e buscar vídeos de apoio na internet</span></label>'+
  '<div class="field-note">Desmarcado por padrão: utiliza recursos locais e imagens já disponíveis. Nenhum serviço pago é ativado por este botão.</div>';
}
function uiEnviar(){
  if(NatinhaUI.enviando)return;
  if((NatinhaUI.modo==='pacote'||NatinhaUI.modo==='hibrido')&&!NatinhaUI.pacoteDisponivel){uiSetMsg('O pacote aguarda a ativação segura do motor. A edição anterior continuará protegida.',true);return;}
  const arq=NatinhaUI.arquivo,path=document.getElementById('ui-path').value.trim();
  if(!arq&&!path){uiSetMsg('Escolha um vídeo ou informe o caminho no PC antes de começar.',true);return;}
  const fd=new FormData(),classico=NatinhaUI.modo==='classico';
  if(arq)fd.append('video',arq);else fd.append('caminho',path);
  let url=classico?'/api/enviar':'/api/remotion/jobs';
  if(classico){
    const v=(document.getElementById('ui-version')||{}).value;
    if(!v){uiSetMsg('Carregando as versões do editor. Tente novamente em instantes.',true);return;}
    fd.append('versao',v);
  }else{
    const vertical=NatinhaUI.modo==='vertical', pacote=NatinhaUI.modo==='pacote'||NatinhaUI.modo==='hibrido';
    fd.append('formato',NatinhaUI.modo==='hibrido'?'hibrido':pacote?'pacote':vertical?'9x16':'16x9');
    fd.append('estilo',vertical||pacote?'completo':document.getElementById('ui-estilo').value);
    fd.append('cortes',vertical||pacote?document.getElementById('ui-nc').value:'1');
    fd.append('alvo',vertical||pacote?document.getElementById('ui-alvo').value:'60');
    if(document.getElementById('ui-online').checked)fd.append('permitir_online','sim');
  }
  NatinhaUI.enviando=true;const bt=document.getElementById('ui-start');bt.disabled=true;
  uiSetMsg('Preparando envio…');
  const x=new XMLHttpRequest();x.open('POST',url,true);
  x.upload.onprogress=function(e){
    if(e.lengthComputable&&arq)uiSetMsg('Enviando vídeo… '+Math.round(e.loaded/e.total*100)+'%');
  };
  x.onload=function(){
    NatinhaUI.enviando=false;bt.disabled=false;
    let result={};try{result=JSON.parse(x.responseText);}catch(e){}
    if(x.status>=200&&x.status<300&&(result.nome||result.id)){
      NatinhaUI.arquivo=null;
      ir((classico?'p/':'r/')+encodeURIComponent(result.nome||result.id));
      // A troca de hash atualiza a tela uma única vez.
    }else uiSetMsg(result.erro||'Não foi possível iniciar a edição. Tente novamente.',true);
  };
  x.onerror=function(){NatinhaUI.enviando=false;bt.disabled=false;uiSetMsg('Sem conexão com o editor. Confira se o PC está ligado.',true);};
  x.send(fd);
}
async function uiConsultarModoDrive(){
  const x=document.getElementById('ui-drive-status'), b=document.getElementById('ui-drive-save');
  if(!x)return;
  try{
    const r=await fetch('/api/drive/modo');
    if(!r.ok)throw Error('A integração está aguardando a ativação no servidor');
    const dados=await r.json();
    NatinhaUI.driveAtual=dados;
    x.textContent='Ativo para novos vídeos: '+dados.rotulo+
      (dados.modo==='classico'?' ('+dados.versao+')':'')+
      ' · '+(dados.permitir_online?'IA e busca online autorizadas':'sem IA externa');
    if(!NatinhaUI.tocouModo&&['classico','vertical','youtube','pacote','hibrido'].includes(dados.modo)){
      uiEscolherModo(dados.modo,true);
      if(dados.modo==='classico'){
        const sel=document.getElementById('ui-version');
        if(sel&&sel.querySelector('[value="'+dados.versao+'"]'))sel.value=dados.versao;
      }
      if(dados.modo==='youtube'){
        const estilo=document.getElementById('ui-estilo');
        if(estilo)estilo.value=dados.estilo;
      }
      if(['pacote','vertical','hibrido'].includes(dados.modo)){
        const nc=document.getElementById('ui-nc'), alvo=document.getElementById('ui-alvo');
        if(nc)nc.value=String(dados.cortes);
        if(alvo&&alvo.querySelector('[value="'+dados.alvo+'"]'))alvo.value=String(dados.alvo);
      }
      const online=document.getElementById('ui-online');
      if(online)online.checked=dados.permitir_online;
    }
  }catch(e){
    x.textContent='Modo automático anterior continua ativo (V2). '+e.message+'.';
    if(b)b.disabled=true;
  }
}
async function uiSalvarModoDrive(){
  const b=document.getElementById('ui-drive-save');
  const resp=document.getElementById('ui-drive-feedback');
  if(!b||b.disabled)return;
  const modo=NatinhaUI.modo;
  const versao=(document.getElementById('ui-version')||{}).value;
  const cortes=+(document.getElementById('ui-nc')||{}).value||3;
  const alvo=+(document.getElementById('ui-alvo')||{}).value||90;
  const estilo=(document.getElementById('ui-estilo')||{}).value||'completo';
  const online=document.getElementById('ui-online');
  if(['pacote','hibrido'].includes(modo)&&!NatinhaUI.pacoteDisponivel){
    resp.textContent='O pacote ainda aguarda ativação do motor. Não alterei o Drive.';return;
  }
  if(modo==='classico'&&!versao){
    resp.textContent='Espere carregar a versão tradicional antes de salvar.';return;
  }
  b.disabled=true;resp.textContent='Salvando o padrão do Drive…';
  try{
    const r=await fetch('/api/drive/modo',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({modo:modo,versao:versao||undefined,cortes:cortes,alvo:alvo,
                           estilo:modo==='youtube'?estilo:'completo',
                           permitir_online:online?online.checked:false})
    });
    const dados=await r.json();
    if(!r.ok)throw Error(dados.erro||'Não foi possível alterar o Drive');
    NatinhaUI.driveAtual=dados;
    document.getElementById('ui-drive-status').textContent='Ativo para novos vídeos: '+dados.rotulo+
      ' · '+(dados.permitir_online?'IA e B-roll online autorizados':'sem IA externa');
    resp.textContent='✓ Salvo. O próximo vídeo colocado no Drive/entrada usará esta opção.';
  }catch(e){resp.textContent=e.message;}
  finally{b.disabled=false;}
}
function uiDataLegado(s){
  const m=/^(\d\d)\/(\d\d)\/(\d{4}) (\d\d):(\d\d)/.exec(s||'');
  return m?m[3]+'-'+m[2]+'-'+m[1]+'T'+m[4]+':'+m[5]:'';
}
async function carregarHistoricoUI(id,limite){
  const destino=document.getElementById(id);if(!destino)return;
  try{
    const dados=await Promise.all([api('/api/projetos'),api('/api/remotion/jobs')]);
    const classicos=(dados[0]||[]).map(function(p){
      return {name:p.titulo||p.nome,sub:'Edição tradicional · '+(p.data||''),data:uiDataLegado(p.data),
        href:'#p/'+encodeURIComponent(p.nome),status:p.erro?'erro':p.pronto?'pronto':'em andamento'};
    });
    const cinema=(dados[1]||[]).map(function(p){
      return {name:(p.formato==='hibrido'?'Natinha Híbrido (beta)':p.formato==='pacote'?'Pacote completo: YouTube + cortes':p.formato==='16x9'?'Vídeo YouTube':'Cortes cinematográficos'),sub:'Remotion · '+(p.criado||'').replace('T',' ').slice(0,16),
        data:p.criado||'',href:'#r/'+encodeURIComponent(p.id),status:p.status==='concluido'?'pronto':p.status==='erro'?'erro':p.status==='interrompido'?'interrompido':'em andamento'};
    });
    const hist=classicos.concat(cinema).sort(function(a,b){return (b.data||'').localeCompare(a.data||'');});
    if(!document.getElementById(id))return;
    destino.innerHTML=(hist.slice(0,limite||50).map(function(p){
      const cls=p.status==='pronto'?'done':p.status==='erro'?'error':'';
      return '<a class="ui-job" href="'+p.href+'"><span><span class="ui-job-title">'+uiEsc(p.name)+
        '</span><span class="ui-job-sub">'+uiEsc(p.sub)+'</span></span><span class="ui-job-state '+cls+'">'+
        uiEsc(p.status)+' ›</span></a>';
    }).join(''))||'<div class="ui-empty">Nenhuma edição encontrada.</div>';
  }catch(e){if(document.getElementById(id))destino.textContent='Histórico temporariamente indisponível. Tente atualizar.';}
}
function telaProjetosUnificada(){
  document.getElementById('app').innerHTML='<div class="ui-hero"><div><div class="eyebrow">Biblioteca</div>'+
  '<h2>Seus vídeos e cortes</h2><p>Os resultados dos diferentes modos aparecem juntos aqui.</p></div></div>'+
  '<section class="ui-panel"><div class="ui-section-row"><h2>Histórico de edições</h2>'+
  '<button onclick="ir(\'\')">+ Novo vídeo</button></div><div id="ui-all-jobs" class="ui-project-list">'+
  '<div class="ui-empty">Carregando...</div></div></section>';
  carregarHistoricoUI('ui-all-jobs',50);
}
function telaRemotionUnificada(id){
  const app=document.getElementById('app');
  app.innerHTML='<div class="ui-hero"><div><div class="eyebrow">Edição cinematográfica</div>'+
   '<h2>Seu vídeo está sendo preparado</h2><p>Acompanhe o trabalho e revise o resultado quando estiver pronto.</p></div></div>'+
   '<section class="ui-panel"><div class="ui-section-row"><h2 id="ui-render-head">Projeto</h2>'+
   '<button onclick="ir(\'historico\')">← Meus projetos</button></div>'+
   '<div class="ui-progress-step"><strong id="ui-render-status">Consultando...</strong><span id="ui-render-phase"></span></div>'+
   '<div class="barra"><i id="ui-render-bar" style="width:0"></i></div>'+
   '<p class="sub" id="ui-render-text" style="margin:10px 0"></p>'+
   '<div class="ui-inline" style="margin-top:15px"><button id="ui-open-folder" onclick="uiAbrirResultado(\''+uiEsc(id)+'\')">Abrir pasta no PC</button>'+
   '<button id="ui-resume" onclick="uiRetomar(\''+uiEsc(id)+'\')" hidden>Retomar edição</button></div>'+
   '<details style="margin-top:20px" class="ui-advanced"><summary>Detalhes técnicos (opcional)</summary>'+
   '<pre id="ui-render-log" class="log">Aguardando...</pre></details></section>'+
   '<section class="ui-panel" id="ui-render-results" hidden><h2>Seus vídeos prontos</h2><div id="ui-render-videos" class="ui-result-list"></div>'+
   '<p class="field-note">Veja o vídeo antes de publicar. A aprovação estética é sempre sua.</p></section>';
  NatinhaUI.shown=null;
  uiAtualizarRemotion(id);
  timer=setInterval(function(){if(location.hash==='#r/'+encodeURIComponent(id))uiAtualizarRemotion(id);},3500);
}
async function uiAtualizarRemotion(id){
  try{
    const x=await fetch('/api/remotion/jobs/'+encodeURIComponent(id));const p=await x.json();
    if(!x.ok)throw new Error(p.erro||'Não foi possível abrir o projeto.');
    if(!document.getElementById('ui-render-status'))return;
    const feito=p.status==='concluido',falha=p.status==='erro'||p.status==='interrompido';
    document.getElementById('ui-render-head').textContent=feito?'Prévia pronta para revisar':'Edição '+id.slice(-6);
    document.getElementById('ui-render-status').textContent=feito?'✓ Edição finalizada':falha?'Edição interrompida':'Editando seu vídeo…';
    document.getElementById('ui-render-phase').textContent=feito?'Concluído':falha?'Ver detalhes':'Etapa '+(p.fase||1)+' de '+(p.total_fases||7)+' (indicativo)';
    document.getElementById('ui-render-bar').style.width=(feito?'100':Math.min(95,Math.round(100*(p.fase||1)/(p.total_fases||7))))+'%';
    document.getElementById('ui-render-text').textContent=p.erro||p.etapa||'Analisando o vídeo…';
    document.getElementById('ui-resume').hidden=!falha;
    document.getElementById('ui-render-log').textContent=(p.registro||[]).slice(-28).join('\n');
    if(feito&&NatinhaUI.shown!==id){
      NatinhaUI.shown=id;const pane=document.getElementById('ui-render-results'),list=document.getElementById('ui-render-videos');
      pane.hidden=false;list.replaceChildren();
      (p.arquivos||[]).filter(function(a){return a.nome.toLowerCase().endsWith('.mp4');}).forEach(function(a){
        const box=document.createElement('div');box.className='ui-result-card';
        const title=document.createElement('div');title.className='ui-report-title';title.textContent=a.nome;
        const vid=document.createElement('video');vid.controls=true;vid.preload='metadata';vid.src=a.url;vid.playsInline=true;
        const dl=document.createElement('a');dl.href=a.url;dl.download='';dl.className='btn';dl.textContent='⬇ Baixar vídeo';
        box.append(title,vid,dl);list.append(box);
      });
      (p.arquivos||[]).filter(function(a){return a.nome.toLowerCase().endsWith('.srt');}).forEach(function(a){
        const l=document.createElement('a');l.href=a.url;l.download='';l.className='btn';l.textContent='Baixar legenda .srt';
        list.append(l);
      });
      if(!list.children.length)list.textContent='Arquivo gerado, mas não foi possível mostrar a prévia. Abra a pasta para conferir.';
    }
    if(feito||falha)clearInterval(timer);
  }catch(err){const x=document.getElementById('ui-render-text');if(x)x.textContent=err.message;}
}
async function uiAbrirResultado(id){
  try{const r=await fetch('/api/remotion/jobs/'+encodeURIComponent(id)+'/abrir',{method:'POST'});if(!r.ok)throw new Error();}catch(e){alert('Não foi possível abrir a pasta no PC.');}
}
async function uiRetomar(id){
  try{
    const r=await fetch('/api/remotion/jobs/'+encodeURIComponent(id)+'/retomar',{method:'POST'});
    const p=await r.json();if(!r.ok)throw new Error(p.erro||'Não foi possível retomar');
    telaRemotionUnificada(id);
  }catch(e){alert(e.message);}
}
render();
