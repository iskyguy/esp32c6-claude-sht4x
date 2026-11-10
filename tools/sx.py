import re
class Sym(str): pass
def parse(s):
    tok=re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')
    st=[[]]
    for m in tok.finditer(s):
        t=m.group(0)
        if t=='(': st.append([])
        elif t==')':
            x=st.pop(); st[-1].append(x)
        elif t[0]=='"': st[-1].append(t[1:-1].replace('\\n','\n').replace('\\"','"').replace('\\\\','\\'))
        else: st[-1].append(Sym(t))
    return st[0][0]
def q(s): return '"'+s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
def dump(x,ind=0):
    if isinstance(x,list):
        simple=all(not isinstance(i,list) for i in x)
        if simple: return '('+' '.join(dump(i) for i in x)+')'
        out='('+dump(x[0])
        i=1
        while i<len(x) and not isinstance(x[i],list):
            out+=' '+dump(x[i]); i+=1
        for y in x[i:]:
            out+='\n'+'\t'*(ind+1)+dump(y,ind+1)
        out+='\n'+'\t'*ind+')'
        return out
    if isinstance(x,Sym): return str(x)
    if isinstance(x,str): return q(x)
    if isinstance(x,float): return ('%.4f'%x).rstrip('0').rstrip('.')
    return str(x)
_cache={}
def lib(path):
    if path not in _cache:
        t=parse(open(path).read())
        _cache[path]={e[1]:e for e in t[1:] if isinstance(e,list) and e[0]=='symbol'}
    return _cache[path]
import copy
def get_symbol(path,name):
    L=lib(path); s=copy.deepcopy(L[name])
    ext=[e for e in s if isinstance(e,list) and e[0]=='extends']
    if ext:
        p=get_symbol(path,ext[0][1])
        pn=p[1]
        props={e[1]:e for e in s if isinstance(e,list) and e[0]=='property'}
        out=[]
        for e in p:
            if isinstance(e,list) and e[0]=='property':
                if e[1] in props: out.append(props.pop(e[1]))
                else: out.append(e)
            elif isinstance(e,list) and e[0]=='symbol':
                e[1]=name+e[1][len(pn):]; 
                # insert remaining props before first sub-symbol
                for v in props.values(): out.append(v)
                props={}
                out.append(e)
            else: out.append(e)
        out[1]=name
        return out
    return s
def pins(sym):
    r=[]
    for e in sym:
        if isinstance(e,list) and e[0]=='symbol':
            unit=int(e[1].rsplit('_',2)[1])
            for p in e:
                if isinstance(p,list) and p[0]=='pin':
                    d={c[0]:c for c in p if isinstance(c,list)}
                    r.append(dict(unit=unit,type=str(p[1]),x=float(d['at'][1]),y=float(d['at'][2]),rot=int(float(d['at'][3])),len=float(d['length'][1]),name=d['name'][1],num=d['number'][1],hide=('hide' in d)))
    return r
