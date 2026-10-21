import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
process.env.RUNTIME_NODE_MODULES ??= await fs.realpath(path.join(ROOT,'node_modules'));
const SKILL=process.env.CEG_PRESENTATION_SKILL || 'C:/Users/User/.codex/plugins/cache/openai-primary-runtime/presentations/26.1015.12040/skills/presentations';
const PYTHON=process.env.CEG_RUNTIME_PYTHON || 'C:/Users/User/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const content=JSON.parse(await fs.readFile(path.join(ROOT,'presentation/deck_content.json'),'utf8'));
const evidence=JSON.parse(await fs.readFile(path.join(ROOT,'results/presentation_data.json'),'utf8'));
const summary=JSON.parse(await fs.readFile(path.join(ROOT,'results/project_summary.json'),'utf8'));
const supplement=summary.supplemental;
const staging=path.join(ROOT,'.build/presentation');
await fs.mkdir(path.join(staging,'previews'),{recursive:true});
const navy='#142C40',teal='#176B78',orange='#ED8A49',muted='#566D7C',light='#EDF3F6';
const deck=Presentation.create({slideSize:{width:1280,height:720}});

function text(slide,value,left,top,width,height,size=28,color=navy,bold=false){
  const s=slide.shapes.add({geometry:'textbox',position:{left,top,width,height},fill:'none',line:{fill:'none',width:0}});
  s.text=value; s.text.style={typeface:'Arial',fontSize:size,color,bold}; return s;
}
function table(slide,values,widths,top=170,height=390,size=24){
  const t=slide.tables.add({rows:values.length,columns:values[0].length,left:72,top,width:1136,height,columnWidths:widths,values});
  t.borders.assign({fill:'#D5E0E5',width:1,style:'solid'});
  for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){
    const cell=t.getCell(r,c); cell.fill=r===0?teal:r%2?light:'#FFFFFF';
    cell.text.style={typeface:'Arial',fontSize:size,color:r===0?'#FFFFFF':navy,bold:r===0};
  }
  return t;
}
function chart(slide,type,categories,series,options={}){
  const c=slide.charts.add(type,{position:{left:72,top:166,width:1136,height:410},titlePlacement:'none',
    categories,series:series.map(s=>({...s,values:s.values.map(v=>Number(v.toFixed(8)))})),hasLegend:false,
    xAxis:{textStyle:{fontSize:19,fill:muted,typeface:'Arial'},majorGridlines:null},
    yAxis:{textStyle:{fontSize:19,fill:muted,typeface:'Arial'},majorGridlines:{fill:'#E0E8ED',width:1,style:'solid'}},
    chartFill:'#FFFFFF',plotAreaFill:'#FFFFFF',...options});
  applyPresentationChartFont(c,{fontFamily:'Arial'}); return c;
}
function readCsv(text){const [head,...rows]=text.trim().split(/\r?\n/).map(l=>l.split(','));return rows.map(row=>Object.fromEntries(head.map((h,i)=>[h,row[i]])));}
const validation=readCsv(await fs.readFile(path.join(ROOT,'results/primary_march/validation_metrics.csv'),'utf8'));
for(let index=0;index<content.length;index++){
  const item=content[index], slide=deck.slides.add(); slide.background.fill='#FFFFFF';
  if(index===0){
    slide.background.fill=navy;
    text(slide,item.title,76,145,1080,230,64,'#FFFFFF',true);
    text(slide,'CEG2003 group project',80,78,1050,45,26,'#96C7CE');
    text(slide,'March 2024 alarms and recorded incident involvement',80,448,1050,58,30,'#FFFFFF');
    text(slide,'Exploratory evidence for preventive human review',80,542,1050,50,26,'#BFD3DE');
  }else{
    text(slide,item.title,72,56,1136,88,44,navy,true);
    if(item.kind==='data_table'){
      const a=evidence.audit;
      table(slide,[['Measure','Audited result'],['Raw alarm records',Number(a.raw.raw_rows).toLocaleString('en-US')],['Exact repeats removed',String(a.exact_duplicate_rows_removed)],['Clean fleet events',Number(a.clean.clean_rows).toLocaleString('en-US')],['Observed captain identifiers',String(a.clean.unique_drivers)],['Populated incident reports','206']],[760,376],176,390,27);
      text(slide,'Incident dates extend beyond the quarter described in the brief.',74,598,1130,45,24,muted);
    }else if(item.kind==='alarm_chart'){
      const rows=[...evidence.alarm_categories].reverse();
      chart(slide,'bar',rows.map(r=>r.alarm_type),[{name:'Events (thousands)',values:rows.map(r=>r.events/1000),fill:teal}],{
        barOptions:{direction:'bar',gapWidth:45},xAxis:{visible:true,textStyle:{fontSize:19,fill:muted,typeface:'Arial'},majorGridlines:null},
        yAxis:{visible:true,numberFormatCode:'#,##0',textStyle:{fontSize:19,fill:muted,typeface:'Arial'},majorGridlines:null},
        dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.0',textStyle:{fontSize:18,fill:navy,typeface:'Arial'}}});
      text(slide,'Clean recorded events, thousands. Counts do not establish severity.',72,608,1136,45,25,muted);
    }else if(item.kind==='daily_chart'){
      chart(slide,'line',evidence.daily_events.map(r=>r.date.slice(8)),[{name:'Daily events',values:evidence.daily_events.map(r=>r.events),smooth:false,line:{fill:teal,width:3,style:'solid'}}],{
        lineOptions:{smooth:false},
        yAxis:{numberFormatCode:'#,##0',textStyle:{fontSize:18,fill:muted,typeface:'Arial'},majorGridlines:{fill:'#E0E8ED',width:1,style:'solid'}},
        xAxis:{title:{text:'March day',textStyle:{fontSize:20,typeface:'Arial',fill:muted}},textStyle:{fontSize:17,fill:muted,typeface:'Arial'}}});
      text(slide,'No complete denominator for driving hours, kilometres or trips.',72,610,1136,45,25,muted);
    }else if(item.kind==='feature_table'){
      table(slide,[['Feature','Definition'],['Harsh rate','Harsh manoeuvre alarms / observed alarm days'],['Fatigue rate','Fatigue Alert + Yawn / observed alarm days'],['Collision rate','Collision and headway warnings / observed alarm days'],['Speeding rate','Speeding category alarms / observed alarm days'],['Night share','Alarms starting during hours 00-05 / all alarms'],['Observed days','Dates with assigned alarms; minimum three']],[290,846],166,430,24);
      text(slide,'Observed alarm days are an exposure proxy.',74,620,1130,38,24,muted);
    }else if(item.kind==='split_table'){
      table(slide,[['Stage','Alarm dates','Outcome dates','Captains','Positives'],
        ['Train','1-7 Mar','8-14 Mar',String(summary.primary.train_rows),String(summary.primary.train_positives)],
        ['Validation','8-14 Mar','15-21 Mar',String(summary.primary.validation_rows),String(summary.primary.validation_positives)],
        ['Test','15-21 Mar','22-28 Mar',String(summary.primary.test_rows),String(summary.primary.test_positives)]],[180,270,270,220,196],190,290,26);
      text(slide,'The initial training cohort has only four positive captains.',74,530,1125,70,30,teal,true);
      text(slide,'Event-time ordering does not verify historical report availability.',74,613,1125,40,24,muted);
    }else if(item.kind==='validation_chart'){
      chart(slide,'bar',validation.map(r=>r.model.replaceAll('_',' ')),[{name:'Validation AP',values:validation.map(r=>Number(r.average_precision)),fill:teal}],{
        barOptions:{direction:'column',gapWidth:95},
        yAxis:{min:0,numberFormatCode:'0.000',textStyle:{fontSize:20,fill:muted,typeface:'Arial'},majorGridlines:{fill:'#E0E8ED',width:1,style:'solid'}},
        dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.0000',textStyle:{fontSize:22,typeface:'Arial',fill:navy}}});
      text(slide,'Selection uses validation AP. Test results never replace this choice.',72,608,1136,45,25,muted);
    }else if(item.kind==='test_chart'){
      chart(slide,'bar',evidence.primary_metrics.map(r=>r.model.replaceAll('_',' ')),[{name:'Test AP',values:evidence.primary_metrics.map(r=>r.average_precision),fill:teal}],{
        barOptions:{direction:'bar',gapWidth:80},xAxis:{visible:true,textStyle:{fontSize:24,typeface:'Arial',fill:muted},majorGridlines:null},
        yAxis:{visible:true,numberFormatCode:'0.000',textStyle:{fontSize:21,typeface:'Arial',fill:muted},majorGridlines:null},
        dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.0000',textStyle:{fontSize:24,typeface:'Arial',fill:navy}}});
      text(slide,`Selected logistic: AP ${summary.primary.test.average_precision.toFixed(4)}. ROC-AUC ${summary.primary.test.roc_auc.toFixed(3)}.`,72,608,1136,45,28,teal,true);
    }else if(item.kind==='confusion_table'){
      const r=summary.primary.test;
      table(slide,[['Observed outcome','Outside review','Selected for review'],['No recorded outcome',String(r.true_negative),String(r.false_positive)],['Recorded involvement',String(r.false_negative),String(r.true_positive)]],[550,293,293],190,255,29);
      text(slide,`${r.true_positive} of ${r.positives} recorded outcomes captured`,74,499,1125,58,38,teal,true);
      text(slide,`Precision ${(100*r.precision_at_k).toFixed(1)}%. Recall ${(100*r.recall_at_k).toFixed(1)}%. Review list: ${r.reviewed} captains.`,74,580,1125,70,28,muted);
    }else if(index===14){
      table(slide,[['Measure','Supplemental April'],['Feature window','Full March'],['Split','60/20/20 stratified captain holdout'],['Held-out positives',String(supplement.test_positives)],['Selected-model AP',supplement.test.average_precision.toFixed(4)]],[480,656],170,345,27);
      text(slide,'April scope and reporting completeness remain unconfirmed.',74,560,1125,65,30,teal,true);
    }else{
      let y=184;
      for(const line of item.lines){
        const height=line.length>89?98:line.length>63?85:76;
        text(slide,line,74,y,1125,height,30,index===13?teal:navy,false);y+=height+16;
      }
    }
  }
  if(index!==0)text(slide,`CEG2003   ${String(index+1).padStart(2,'0')}   Confidential course data`,74,681,1120,22,16,muted);
  slide.speakerNotes.text=item.notes+'\n\nSource: '+item.source+'\nSources for method: https://scikit-learn.org/stable/common_pitfalls.html and https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html';
}
const candidate=path.join(staging,'candidate.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidate);
let finalPath=path.join(ROOT,'presentation/CEG2003_Presentation.pptx');
try{await fs.access(finalPath);await fs.mkdir(path.join(ROOT,'.build/validated'),{recursive:true});finalPath=path.join(ROOT,`.build/validated/CEG2003_Presentation_${Date.now()}.pptx`);}catch{}
const receiptPath=path.join(staging,`validation-${Date.now()}.json`);
const final=await finalizePresentation({workspaceDir:ROOT,candidatePath:candidate,finalPath,
  pythonExecutable:PYTHON,integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...[3,7,8,12,15].flatMap(n=>['--require-native-table-slide',String(n)])],
  explicitTotalSlideCount:16,requiredNativeChartOwnerSlides:[5,6,10,11],requiredNativeTableOwnerSlides:[3,7,8,12,15],
  materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:['Arial']},verifyArtifactToolImport:true,
  receiptPath});
if(finalPath!==path.join(ROOT,'presentation/CEG2003_Presentation.pptx')) await fs.copyFile(finalPath,path.join(ROOT,'presentation/CEG2003_Presentation.pptx'));
await fs.copyFile(receiptPath,path.join(staging,'presentation_validation.json'));
console.log(JSON.stringify({finalPath:path.join(ROOT,'presentation/CEG2003_Presentation.pptx'),passed:true,sha256:final.finalSha256,slides:16,charts:4,tables:5}));
for(let i=0;i<deck.slides.items.length;i++){
  const blob=await deck.export({slide:deck.slides.items[i],format:'png',scale:1});
  await fs.writeFile(path.join(staging,'previews',`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));
}
console.log('Rendered all 16 slide previews.');
