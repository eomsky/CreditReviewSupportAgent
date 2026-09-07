"""Read-only audit of a saved prompt; tokenizer calls do not generate text."""
import argparse
import json
from pathlib import Path
import httpx
from credit_review.llm import ColabClient
from credit_review.prompt_budget import compact_group_context
from credit_review.store import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    files = sorted((args.run/'artifacts').glob('group_input_*.json'), key=lambda p:p.stat().st_mtime_ns)
    context = json.loads(files[0].read_text())['payload']
    compact = compact_group_context(context)
    dump = lambda obj: json.dumps(obj,ensure_ascii=False,separators=(',',':'))
    output = {'input_file':str(files[0]), 'factor_ids':list(context['factors']),
        'before_chars':len(dump(context)), 'after_chars':len(dump(compact)),
        'field_chars':{key:len(dump(value)) for key,value in context.items()},
        'source_field_chars':{key:sum(len(dump(s.get(key))) for s in context['sources'].values())
                              for key in next(iter(context['sources'].values()))}}
    c = ColabClient()
    headers = {'Authorization':'Bearer '+c.key} if c.key else {}
    prompt = Path('src/credit_review/prompts/group.md').read_text(encoding='utf-8')
    with httpx.Client(timeout=15) as client:
        r=client.get(c.base_url+'/models',headers=headers)
        r.raise_for_status()
        output['server_context_tokens'] = next(m for m in r.json()['data'] if m['id']==c.model).get('max_model_len')
        for label,value in (('before',context),('after',compact)):
            r=client.post(c.base_url.removesuffix('/v1')+'/tokenize',headers=headers,
                json={'model':c.model,'messages':[{'role':'system','content':prompt},
                {'role':'user','content':dump(value)}], 'add_generation_prompt':True,
                'chat_template_kwargs':{'enable_thinking':False}})
            output[label+'_tokenize_status']=r.status_code
            if r.is_success:
                output[label+'_tokens']=r.json().get('count')
    atomic_json(args.run/'prompt_audit.json', output)
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
