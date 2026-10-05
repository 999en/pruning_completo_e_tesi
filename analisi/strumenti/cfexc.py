import sys, struct
def parse(path):
    d=open(path,'rb').read(); pos=[0]
    def u1():
        v=d[pos[0]]; pos[0]+=1; return v
    def u2():
        v=struct.unpack_from('>H',d,pos[0])[0]; pos[0]+=2; return v
    def u4():
        v=struct.unpack_from('>I',d,pos[0])[0]; pos[0]+=4; return v
    assert u4()==0xCAFEBABE
    u2(); u2(); cpc=u2(); cp=[None]*cpc; i=1
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
        e=cp[idx]
        if e is None: return 'null(cp0)'
        if e[0]=='Utf8': return e[1]
        if e[0]==7: return utf(e[1]).replace('/','.')
        if e[0]==8: return '"%s"'%utf(e[1])
        if e[0]==3: return str(struct.unpack('>i',struct.pack('>I',e[1]))[0]) if e[1]<2**31 else str(e[1]-2**32)
        return str(e)
    u2(); u2(); u2(); ic=u2()
    for _ in range(ic): u2()
    def attrs():
        n=u2(); res=[]
        for _ in range(n):
            ni=u2(); ln=u4(); body=d[pos[0]:pos[0]+ln]; pos[0]+=ln; res.append((utf(ni),body))
        return res
    fc=u2()
    for _ in range(fc):
        u2(); u2(); u2(); attrs()
    mc=u2()
    print("#### %s"%path)
    for _ in range(mc):
        ma=u2(); ni=u2(); di=u2(); ats=attrs()
        for an,body in ats:
            if an=='Code':
                # max_stack,max_locals,code_len,code, exc_table, attrs
                cl=struct.unpack_from('>I',body,4)[0]
                p=8+cl
                etn=struct.unpack_from('>H',body,p)[0]
                if etn:
                    print("  METHOD %s%s"%(utf(ni),utf(di)))
                    for k in range(etn):
                        s,e,h,ct=struct.unpack_from('>HHHH',body,p+2+8*k)
                        print("    [%d,%d) handler=%d catch=%s"%(s,e,h,utf(ct) if ct else 'any'))
for p in sys.argv[1:]: parse(p)
