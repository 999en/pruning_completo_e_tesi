import sys, struct
def parse(path):
    d=open(path,'rb').read()
    pos=[0]
    def u1():
        v=d[pos[0]]; pos[0]+=1; return v
    def u2():
        v=struct.unpack_from('>H',d,pos[0])[0]; pos[0]+=2; return v
    def u4():
        v=struct.unpack_from('>I',d,pos[0])[0]; pos[0]+=4; return v
    assert u4()==0xCAFEBABE
    minor=u2(); major=u2()
    cpc=u2()
    cp=[None]*cpc
    i=1
    while i<cpc:
        tag=u1()
        if tag==1:
            l=u2(); cp[i]=('Utf8',d[pos[0]:pos[0]+l].decode('utf-8','replace')); pos[0]+=l
        elif tag in (7,8,16,19,20): cp[i]=(tag,u2())
        elif tag==15: cp[i]=(tag,u1(),u2())
        elif tag in (3,4,9,10,11,12,17,18): cp[i]=(tag,u4())
        elif tag in (5,6): cp[i]=(tag,u4(),u4()); i+=1
        else: raise Exception('tag %d'%tag)
        i+=1
    def utf(idx):
        e=cp[idx]; return e[1] if e and e[0]=='Utf8' else str(e)
    access=u2(); this=u2(); sup=u2()
    ic=u2(); ifaces=[utf(u2()) for _ in range(ic)]
    def attrs():
        n=u2(); res=[]
        for _ in range(n):
            ni=u2(); ln=u4(); body=d[pos[0]:pos[0]+ln]; pos[0]+=ln
            res.append((utf(ni),body))
        return res
    print("FILE",path)
    print("  major",major,"access 0x%04x"%access,"this",utf(cp[this][1]),"super",utf(cp[sup][1]),"interfaces",ifaces)
    fc=u2()
    print("  FIELDS (%d):"%fc)
    for _ in range(fc):
        fa=u2(); ni=u2(); di=u2(); ats=attrs()
        const=None
        for an,body in ats:
            if an=='ConstantValue':
                ci=struct.unpack_from('>H',body,0)[0]
                const=cp[ci]
        print("    %-20s %-28s access 0x%04x const=%s attrs=%s"%(utf(ni),utf(di),fa,const,[a[0] for a in ats]))
    mc=u2()
    print("  METHODS (%d):"%mc)
    for _ in range(mc):
        ma=u2(); ni=u2(); di=u2(); ats=attrs()
        ex=[]
        for an,body in ats:
            if an=='Exceptions':
                n=struct.unpack_from('>H',body,0)[0]
                ex=[utf(struct.unpack_from('>H',body,2+2*k)[0]) for k in range(n)]
        print("    %s%s access 0x%04x throws=%s attrs=%s"%(utf(ni),utf(di),ma,ex,[a[0] for a in ats]))
for p in sys.argv[1:]: parse(p)
