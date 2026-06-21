from __future__ import annotations
import json,re,hashlib,sys
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.base import clone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score,f1_score,classification_report,confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.dummy import DummyClassifier
ROOT=Path('/mnt/data/mp3_extracted/monetary_policy_project');sys.path.insert(0,str(ROOT))
from src.monetary_policy.text.lexicon import Lexicon,read_jiang_lexicon,read_du_lexicon,base_negations,base_degree_words,EXTERNAL_DIR,LEXICON_VERSION_DIR
from src.monetary_policy.text.sentiment import score_text

df=pd.read_excel(ROOT/'data/validation/manual_sentence_annotation_filled.xlsx')
# intended final patches not persisted in supplied xlsx
patches={'2022Q2_guidance_01':{'manual_policy_stance_label':'dovish'},'2011Q3_macro_01':{'manual_sentiment_label':'negative'},'2019Q3_macro_01':{'manual_sentiment_label':'positive','manual_policy_stance_label':'irrelevant'},'2020Q3_macro_01':{'manual_sentiment_label':'positive'},'2022Q4_macro_01':{'manual_sentiment_label':'neutral'}}
for aid,pp in patches.items():
 for c,v in pp.items():df.loc[df.annotation_id==aid,c]=v
df['manual_topic_eval']=df.manual_topic_label.replace({'real_estate':'other'})
def norm(s):return re.sub(r'\s+','',str(s))
df['text_norm']=df.sentence.map(norm);df['text_with_section']=df.apply(lambda r:('政策指引：' if r.section=='guidance' else '宏观形势：')+norm(r.sentence),axis=1);df['group_text']=df.text_norm.map(lambda s:hashlib.sha1(s.encode()).hexdigest())
# lexicons
jp,jn=read_jiang_lexicon(EXTERNAL_DIR/'jiang_financial_sentiment.xlsx');dp,dn=read_du_lexicon(EXTERNAL_DIR/'du_financial_sentiment.xlsx')
pos=jp|dp|{'稳健','改善','恢复','支持','增强','合理充裕'};neg=jn|dn|{'下行压力','不确定性','冲击','压力','风险暴露'}
def lex(v):
 d=json.loads((LEXICON_VERSION_DIR/f'pbc_domain_v{v}.json').read_text(encoding='utf8'))
 return Lexicon(pos,neg,set(d['dovish']),set(d['hawkish']),set(d.get('negations',base_negations())),d.get('degree',base_degree_words()),{k:set(x) for k,x in d['topics'].items()},v,'')
def sent_label(x):return 'neutral' if x==0 else ('positive' if x>0 else 'negative')
def stance_label(x):return 'neutral' if x==0 else ('dovish' if x>0 else 'hawkish')
def topic_label(s):
 ts=['growth','inflation','risk','exchange_rate','financial_stability'];b=max(ts,key=lambda t:s.get('attention_'+t,0));return b if s.get('attention_'+b,0)>0 else 'other'
for v in [1,2]:
 sc=[score_text(t,lex(v)) for t in df.sentence]
 df[f'v{v}_sent_score']=[x['normalized_sentiment'] for x in sc];df[f'v{v}_stance_score']=[x['normalized_policy_stance'] for x in sc]
 df[f'v{v}_sent']=df[f'v{v}_sent_score'].map(sent_label);df[f'v{v}_stance']=df[f'v{v}_stance_score'].map(stance_label);df[f'v{v}_topic']=[topic_label(x) for x in sc]
# simple gates
markers=['货币政策','流动性','货币信贷','社会融资','公开市场操作','存款准备金率','准备金率','政策利率','利率','M2','货币供应量','融资成本','货币条件','信贷','逆周期调节','跨周期调节','适度宽松','从紧','支持实体经济','稳增长','六稳','六保']
pos_state=['企稳回升','恢复向好','回升向好','趋好','复苏态势','稳定恢复','稳中向好','开局良好','积极变化','改善','好转','正增长','表现良好','温和复苏','持续恢复']
neg_state=['增速放缓','增长放缓','下行压力','衰退','复苏缓慢','不确定性进一步增加','风险加大','危机','动荡加剧','疲弱','动力不足','失业率居高不下']
goal=['支持','促进','推动','提高','完善','加大','加强','保持','引导','实现','创造','服务']
def gate_st(r,score):
 t=norm(r.sentence)
 if r.section=='macro':return 'irrelevant'
 if not any(m in t for m in markers):return 'irrelevant'
 return stance_label(score)
def gate_sent(r,score,thr=6):
 t=norm(r.sentence);p=any(x in t for x in pos_state);n=any(x in t for x in neg_state)
 if p and not n:return 'positive'
 if n and not p:return 'negative'
 if p and n:return 'neutral'
 if r.section=='guidance' and any(x in t for x in goal):return 'neutral'
 return 'neutral' if abs(score)<=thr else ('positive' if score>0 else 'negative')
df['v2_stance_gated']=[gate_st(r,s) for (_,r),s in zip(df.iterrows(),df.v2_stance_score)]
df['v2_sent_gated']=[gate_sent(r,s) for (_,r),s in zip(df.iterrows(),df.v2_sent_score)]
def metrics(y,p):return {'accuracy':accuracy_score(y,p),'macro_f1':f1_score(y,p,average='macro',zero_division=0),'weighted_f1':f1_score(y,p,average='weighted',zero_division=0)}
rule=[]
for task,yc,pcs in [('sentiment','manual_sentiment_label',['v1_sent','v2_sent','v2_sent_gated']),('policy','manual_policy_stance_label',['v1_stance','v2_stance','v2_stance_gated']),('topic','manual_topic_eval',['v1_topic','v2_topic'])]:
 for pc in pcs:rule.append({'task':task,'model':pc,**metrics(df[yc],df[pc])})
rel=df[df.manual_policy_stance_label!='irrelevant']
for pc in ['v1_stance','v2_stance','v2_stance_gated']:rule.append({'task':'policy_relevant_only','model':pc,**metrics(rel.manual_policy_stance_label,rel[pc])})
print('RULE');print(pd.DataFrame(rule).to_string(index=False,float_format=lambda z:f'{z:.3f}'),flush=True)
# one 3-fold grouped CV per grouping, SVM and majority baseline
cvrows=[];pred_store=[]
for task,yc in [('sentiment','manual_sentiment_label'),('policy','manual_policy_stance_label'),('topic','manual_topic_eval')]:
 X=df.text_with_section.to_numpy();y=df[yc].to_numpy()
 for groupcol in ['report_id','group_text']:
  groups=df[groupcol].to_numpy();cv=StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=2026)
  for modelname,model in [
   ('majority',DummyClassifier(strategy='most_frequent')),
   ('char_svm',Pipeline([('tfidf',TfidfVectorizer(analyzer='char',ngram_range=(2,4),min_df=1,max_features=6000,sublinear_tf=True)),('clf',LinearSVC(class_weight='balanced',C=1.0))]))]:
   pred=np.empty(len(y),object)
   for tr,te in cv.split(X,y,groups):
    m=clone(model);m.fit(X[tr],y[tr]);pred[te]=m.predict(X[te])
   q=metrics(y,pred);cvrows.append({'task':task,'grouping':groupcol,'model':modelname,**q})
   for i,pr in enumerate(pred):pred_store.append({'task':task,'grouping':groupcol,'model':modelname,'annotation_id':df.annotation_id.iloc[i],'true':y[i],'pred':pr})
print('\nCV');print(pd.DataFrame(cvrows).to_string(index=False,float_format=lambda z:f'{z:.3f}'),flush=True)
# sanity cases
san=[('实行从紧的货币政策','guidance','hawkish'),('把好流动性总闸门','guidance','hawkish'),('防止货币信贷过快增长','guidance','hawkish'),('保持流动性合理充裕','guidance','dovish'),('加大对实体经济的支持力度','guidance','dovish'),('世界经济增长明显放缓','macro','negative'),('经济持续恢复向好','macro','positive'),('减税让利、放松市场管制','guidance','irrelevant')]
print('\nSANITY')
sanity=[]
L2=lex(2)
for text,sec,exp in san:
 s=score_text(text,L2);r=type('R',(object,),{'sentence':text,'section':sec})();raw=stance_label(s['normalized_policy_stance']);g=gate_st(r,s['normalized_policy_stance']);print(text,round(s['normalized_sentiment'],2),round(s['normalized_policy_stance'],2),raw,g,exp);sanity.append({'text':text,'section':sec,'expected':exp,'sentiment_score':s['normalized_sentiment'],'stance_score':s['normalized_policy_stance'],'raw_stance':raw,'gated_stance':g})
out=ROOT/'output/experiments/text_pipeline_probe';out.mkdir(parents=True,exist_ok=True)
pd.DataFrame(rule).to_csv(out/'rule_metrics.csv',index=False,encoding='utf-8-sig');pd.DataFrame(cvrows).to_csv(out/'supervised_cv_summary.csv',index=False,encoding='utf-8-sig');pd.DataFrame(pred_store).to_csv(out/'supervised_oof_predictions.csv',index=False,encoding='utf-8-sig');pd.DataFrame(sanity).to_csv(out/'sanity_cases.csv',index=False,encoding='utf-8-sig')
df.to_csv(out/'probe_dataset_with_predictions.csv',index=False,encoding='utf-8-sig')
(ROOT/'experiments/text_pipeline_probe.py').write_text(Path('/tmp/fast_probe.py').read_text(encoding='utf8'),encoding='utf8')
