"""Reversible columnar encoding for repeated JSON records in retrieved evidence."""
import json
TAG='__evidence_records_v1__'
def pack(value):
 if isinstance(value,list):
  if len(value)>=2 and all(isinstance(x,dict) for x in value):
   columns=list(value[0])
   if all(list(x)==columns for x in value):
    return {TAG:True,'columns':columns,'rows':[[pack(x[k]) for k in columns] for x in value]}
  return [pack(x) for x in value]
 if isinstance(value,dict):
  if TAG in value:raise ValueError('Reserved marker in source')
  return {k:pack(v) for k,v in value.items()}
 return value

def unpack(value):
 if isinstance(value,dict):
  if value.get(TAG) is True and set(value)=={TAG,'columns','rows'}:
   columns=value['columns']
   if any(len(row)!=len(columns) for row in value['rows']):raise ValueError('Invalid record width')
   return [dict(zip(columns,[unpack(x) for x in row])) for row in value['rows']]
  return {k:unpack(v) for k,v in value.items()}
 if isinstance(value,list):return [unpack(x) for x in value]
 return value

def compact(text):
 try:original=json.loads(text)
 except (ValueError,TypeError):return text,False
 try:encoded=pack(original)
 except ValueError:return text,False
 if unpack(encoded)!=original:raise ValueError('Lossless evidence round-trip failed')
 candidate=json.dumps(encoded,ensure_ascii=False,separators=(',',':'))
 return (candidate,True) if len(candidate)<len(text) else (text,False)
