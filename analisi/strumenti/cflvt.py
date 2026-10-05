import sys, struct
class R:
    def __init__(s,d,p): s.d=d; s.p=p
    def u1(s):
        v=s.d[s.p]; s.p+=1; return v
    def u2(s):
        v=struct.unpack_from('>H',s.d,s.p)[0]; s.p+=2; return v
    def u4(s):
        v=struct.unpack_from('>I',s.d,s.p)[0]; s.p+=4; return v
    def bytes(s,n):
        v=s.d[s.p:s.p+n]; s.p+=n; return v

def parse(path, want=None):
    d=open(path,'rb').read(); r=R(d,0)
    assert r.u4()==0xCAFEBABE
    r.u2(); r.u2(); cpc=r.u2(); cp=[None]*cpc; i=1
    while i<cpc:
        tag=r.u1()
        if tag==1:
            l=r.u2(); cp[i]=('Utf8',r.bytes(l).decode('utf-8','replace'))
        elif tag in (7,8,16,19,20): cp[i]=(tag,r.u2())
        elif tag==15: cp[i]=(tag,r.u1(),r.u2())
        elif tag in (3,4,9,10,11,12,17,18): cp[i]=(tag,r.u4())
        elif tag in (5,6): cp[i]=(tag,r.u4(),r.u4()); i+=1
        else: raise Exception('tag %d'%tag)
        i+=1
    def utf(idx):
        e=cp[idx]
        if e is None: return '?'
        if e[0]=='Utf8': return e[1]
        if e[0]==7: return utf(e[1]).replace('/','.')
        return str(e)
    r.u2(); r.u2(); r.u2()
    for _ in range(r.u2()): r.u2()
    def attrs():
        n=r.u2(); res=[]
        for _ in range(n):
            ni=r.u2(); ln=r.u4(); start=r.p; r.p=start+ln; res.append((utf(ni),start,ln))
        return res
    for _ in range(r.u2()):
        r.u2(); r.u2(); r.u2(); attrs()
    print("#### %s"%path)
    for _ in range(r.u2()):
        ma=r.u2(); ni=r.u2(); di=r.u2(); ats=attrs()
        name=utf(ni); desc=utf(di)
        if want and want not in name: continue
        for an,start,ln in ats:
            if an!='Code': continue
            q=R(d,start)
            q.u2(); q.u2(); q.u4()  # max_stack, max_locals, code_len
            cl=struct.unpack_from('>I',d,start+4)[0]
            q.p=start+8+cl
            etn=q.u2(); q.p+=8*etn
            print("  METHOD %s%s  (code [0,%d))"%(name,desc,cl))
            for _ in range(q.u2()):
                ni2=q.u2(); ln2=q.u4(); s2=q.p; q.p=s2+ln2
                nm=utf(ni2)
                if nm=='LocalVariableTable':
                    z=R(d,s2); n2=z.u2()
                    for _ in range(n2):
                        sp=z.u2(); l=z.u2(); nn=utf(z.u2()); dd=utf(z.u2()); idx=z.u2()
                        print("      slot %-3d %-16s %-24s start=%-4d len=%d"%(idx,nn,dd,sp,l))
for p in sys.argv[1:]:
    if '::' in p:
        f,w=p.split('::'); parse(f,w)
    else: parse(p)
