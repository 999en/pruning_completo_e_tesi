import sys, struct
def parse(path, filt=None):
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
    print("#### constant pool of %s"%path)
    for idx in range(1,cpc):
        e=cp[idx]
        if e is None: continue
        if e[0]==8:
            print("  cp#%d String -> %r"%(idx, cp[e[1]][1]))
        elif e[0]=="Utf8":
            s=e[1]
            if filt is None or (len(s)<=4 and s.isprintable()):
                print("  cp#%d Utf8 %r"%(idx,s))
        elif e[0]==3:
            v=e[1]
            sv=struct.unpack('>i',struct.pack('>I',v))[0]
            print("  cp#%d Integer %d"%(idx,sv))
        elif e[0]==4:
            print("  cp#%d Float %r"%(idx,struct.unpack('>f',struct.pack('>I',e[1]))[0]))
        elif e[0]==6:
            print("  cp#%d Double %r"%(idx,struct.unpack('>d',struct.pack('>II',e[1],e[2]))[0]))
for p in sys.argv[1:]:
    parse(p, filt=True)
