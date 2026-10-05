#!/usr/bin/env python3
"""Minimal JVM class-file disassembler: dumps Code attributes of a method.
Usage: jvmdis.py <classfile> [methodName]
"""
import struct, sys

# opcode -> (mnemonic, operand bytes, kind)
OPS = {
    0x00:("nop",0,""),0x01:("aconst_null",0,""),0x02:("iconst_m1",0,""),0x03:("iconst_0",0,""),
    0x04:("iconst_1",0,""),0x05:("iconst_2",0,""),0x06:("iconst_3",0,""),0x07:("iconst_4",0,""),
    0x08:("iconst_5",0,""),0x09:("lconst_0",0,""),0x0a:("lconst_1",0,""),0x0b:("fconst_0",0,""),
    0x0c:("fconst_1",0,""),0x0d:("fconst_2",0,""),0x0e:("dconst_0",0,""),0x0f:("dconst_1",0,""),
    0x10:("bipush",1,"i8"),0x11:("sipush",2,"i16"),0x12:("ldc",1,"cp1"),0x13:("ldc_w",2,"cp2"),
    0x14:("ldc2_w",2,"cp2"),
    0x15:("iload",1,"lv"),0x16:("lload",1,"lv"),0x17:("fload",1,"lv"),0x18:("dload",1,"lv"),
    0x19:("aload",1,"lv"),0x1a:("iload_0",0,""),0x1b:("iload_1",0,""),0x1c:("iload_2",0,""),
    0x1d:("iload_3",0,""),0x1e:("lload_0",0,""),0x1f:("lload_1",0,""),0x20:("lload_2",0,""),
    0x21:("lload_3",0,""),0x22:("fload_0",0,""),0x23:("fload_1",0,""),0x24:("fload_2",0,""),
    0x25:("fload_3",0,""),0x26:("dload_0",0,""),0x27:("dload_1",0,""),0x28:("dload_2",0,""),
    0x29:("dload_3",0,""),0x2a:("aload_0",0,""),0x2b:("aload_1",0,""),0x2c:("aload_2",0,""),
    0x2d:("aload_3",0,""),0x2e:("iaload",0,""),0x2f:("laload",0,""),0x30:("faload",0,""),
    0x31:("daload",0,""),0x32:("aaload",0,""),0x33:("baload",0,""),0x34:("caload",0,""),
    0x35:("saload",0,""),
    0x36:("istore",1,"lv"),0x37:("lstore",1,"lv"),0x38:("fstore",1,"lv"),0x39:("dstore",1,"lv"),
    0x3a:("astore",1,"lv"),0x3b:("istore_0",0,""),0x3c:("istore_1",0,""),0x3d:("istore_2",0,""),
    0x3e:("istore_3",0,""),0x3f:("lstore_0",0,""),0x40:("lstore_1",0,""),0x41:("lstore_2",0,""),
    0x42:("lstore_3",0,""),0x43:("fstore_0",0,""),0x44:("fstore_1",0,""),0x45:("fstore_2",0,""),
    0x46:("fstore_3",0,""),0x47:("dstore_0",0,""),0x48:("dstore_1",0,""),0x49:("dstore_2",0,""),
    0x4a:("dstore_3",0,""),0x4b:("astore_0",0,""),0x4c:("astore_1",0,""),0x4d:("astore_2",0,""),
    0x4e:("astore_3",0,""),0x4f:("iastore",0,""),0x50:("lastore",0,""),0x51:("fastore",0,""),
    0x52:("dastore",0,""),0x53:("aastore",0,""),0x54:("bastore",0,""),0x55:("castore",0,""),
    0x56:("sastore",0,""),0x57:("pop",0,""),0x58:("pop2",0,""),0x59:("dup",0,""),0x5a:("dup_x1",0,""),
    0x5b:("dup_x2",0,""),0x5c:("dup2",0,""),0x5d:("dup2_x1",0,""),0x5e:("dup2_x2",0,""),
    0x5f:("swap",0,""),
    0x60:("iadd",0,""),0x61:("ladd",0,""),0x62:("fadd",0,""),0x63:("dadd",0,""),0x64:("isub",0,""),
    0x65:("lsub",0,""),0x66:("fsub",0,""),0x67:("dsub",0,""),0x68:("imul",0,""),0x69:("lmul",0,""),
    0x6a:("fmul",0,""),0x6b:("dmul",0,""),0x6c:("idiv",0,""),0x6d:("ldiv",0,""),0x6e:("fdiv",0,""),
    0x6f:("ddiv",0,""),0x70:("irem",0,""),0x71:("lrem",0,""),0x72:("frem",0,""),0x73:("drem",0,""),
    0x74:("ineg",0,""),0x75:("lneg",0,""),0x76:("fneg",0,""),0x77:("dneg",0,""),0x78:("ishl",0,""),
    0x79:("lshl",0,""),0x7a:("ishr",0,""),0x7b:("lshr",0,""),0x7c:("iushr",0,""),0x7d:("lushr",0,""),
    0x7e:("iand",0,""),0x7f:("land",0,""),0x80:("ior",0,""),0x81:("lor",0,""),0x82:("ixor",0,""),
    0x83:("lxor",0,""),0x84:("iinc",2,"iinc"),
    0x85:("i2l",0,""),0x86:("i2f",0,""),0x87:("i2d",0,""),0x88:("l2i",0,""),0x89:("l2f",0,""),
    0x8a:("l2d",0,""),0x8b:("f2i",0,""),0x8c:("f2l",0,""),0x8d:("f2d",0,""),0x8e:("d2i",0,""),
    0x8f:("d2l",0,""),0x90:("d2f",0,""),0x91:("i2b",0,""),0x92:("i2c",0,""),0x93:("i2s",0,""),
    0x94:("lcmp",0,""),0x95:("fcmpl",0,""),0x96:("fcmpg",0,""),0x97:("dcmpl",0,""),0x98:("dcmpg",0,""),
    0x99:("ifeq",2,"br"),0x9a:("ifne",2,"br"),0x9b:("iflt",2,"br"),0x9c:("ifge",2,"br"),
    0x9d:("ifgt",2,"br"),0x9e:("ifle",2,"br"),0x9f:("if_icmpeq",2,"br"),0xa0:("if_icmpne",2,"br"),
    0xa1:("if_icmplt",2,"br"),0xa2:("if_icmpge",2,"br"),0xa3:("if_icmpgt",2,"br"),0xa4:("if_icmple",2,"br"),
    0xa5:("if_acmpeq",2,"br"),0xa6:("if_acmpne",2,"br"),0xa7:("goto",2,"br"),0xa8:("jsr",2,"br"),
    0xa9:("ret",1,"lv"),
    0xaa:("tableswitch",-1,"tswitch"),0xab:("lookupswitch",-1,"lswitch"),
    0xac:("ireturn",0,""),0xad:("lreturn",0,""),0xae:("freturn",0,""),0xaf:("dreturn",0,""),
    0xb0:("areturn",0,""),0xb1:("return",0,""),
    0xb2:("getstatic",2,"cp2"),0xb3:("putstatic",2,"cp2"),0xb4:("getfield",2,"cp2"),
    0xb5:("putfield",2,"cp2"),0xb6:("invokevirtual",2,"cp2"),0xb7:("invokespecial",2,"cp2"),
    0xb8:("invokestatic",2,"cp2"),0xb9:("invokeinterface",4,"cp4"),0xba:("invokedynamic",4,"cp4"),
    0xbb:("new",2,"cp2"),0xbc:("newarray",1,"i8"),0xbd:("anewarray",2,"cp2"),0xbe:("arraylength",0,""),
    0xbf:("athrow",0,""),0xc0:("checkcast",2,"cp2"),0xc1:("instanceof",2,"cp2"),
    0xc2:("monitorenter",0,""),0xc3:("monitorexit",0,""),0xc4:("wide",-1,"wide"),
    0xc5:("multianewarray",3,"multi"),0xc6:("ifnull",2,"br"),0xc7:("ifnonnull",2,"br"),
    0xc8:("goto_w",4,"br4"),0xc9:("jsr_w",4,"br4"),
}

class Reader:
    def __init__(s, b): s.b=b; s.p=0
    def u1(s):
        v=s.b[s.p]; s.p+=1; return v
    def u2(s):
        v=struct.unpack_from(">H",s.b,s.p)[0]; s.p+=2; return v
    def u4(s):
        v=struct.unpack_from(">I",s.b,s.p)[0]; s.p+=4; return v
    def take(s,n):
        v=s.b[s.p:s.p+n]; s.p+=n; return v

def parse_cp(r):
    n=r.u2(); cp={}; i=1
    while i<n:
        tag=r.u1()
        if tag==1:
            l=r.u2(); cp[i]=("Utf8", r.take(l).decode("utf-8","replace"))
        elif tag in (3,4): cp[i]=("Num", r.u4())
        elif tag in (5,6): cp[i]=("Long", struct.unpack(">q",r.take(8))[0]); i+=1
        elif tag in (7,8,16,19,20): cp[i]=("Ref", r.u2())
        elif tag in (9,10,11,12,17,18): cp[i]=("Ref2", r.u2(), r.u2())
        elif tag==15: cp[i]=("Ref3", r.u1(), r.u2())
        else: raise ValueError(f"cp tag {tag} at {i}")
        i+=1
    return cp

def cpstr(cp,i):
    e=cp.get(i)
    if not e: return f"#{i}"
    if e[0]=="Utf8": return e[1]
    if e[0]=="Num":
        f=struct.unpack(">f",struct.pack(">I",e[1]))[0]
        return f"{e[1]} (int {struct.unpack('>i',struct.pack('>I',e[1]))[0]}) / {f} (float)"
    if e[0]=="Long": return str(e[1])
    if e[0]=="Ref": return cpstr(cp,e[1])
    if e[0]=="Ref2": return f"{cpstr(cp,e[1])}.{cpstr(cp,e[2])}"
    if e[0]=="Ref3": return f"{cpstr(cp,e[1])}.{cpstr(cp,e[2])}:{e[1]}"
    return str(e)

def disasm(code, cp, base=0):
    out=[]; p=0; n=len(code)
    while p<n:
        pc=p
        op=code[p]; p+=1
        if op not in OPS:
            out.append((pc,"<unknown 0x%02x>"%op,"")); break
        name,ln,kind=OPS[op]
        if kind=="tswitch":
            while (p%4)!=0: p+=1
            default=struct.unpack_from(">i",code,p)[0]; p+=4
            lo=struct.unpack_from(">i",code,p)[0]; p+=4
            hi=struct.unpack_from(">i",code,p)[0]; p+=4
            tgts=[]
            for k in range(hi-lo+1):
                tgts.append((lo+k,struct.unpack_from(">i",code,p)[0]+base)); p+=4
            out.append((pc,name,f"default->{default+base} {{"+", ".join(f"{k}->{t}" for k,t in tgts)+"}"))
            continue
        if kind=="lswitch":
            while (p%4)!=0: p+=1
            default=struct.unpack_from(">i",code,p)[0]; p+=4
            npairs=struct.unpack_from(">i",code,p)[0]; p+=4
            prs=[]
            for _ in range(npairs):
                k=struct.unpack_from(">i",code,p)[0]; p+=4
                t=struct.unpack_from(">i",code,p)[0]; p+=4
                prs.append(f"{k}->{t+base}")
            out.append((pc,name,f"default->{default+base} {{"+", ".join(prs)+"}"))
            continue
        if kind=="wide":
            op2=code[p]; p+=1
            if op2==0x84:
                idx=struct.unpack_from(">H",code,p)[0]; p+=2
                c=struct.unpack_from(">h",code,p)[0]; p+=2
                out.append((pc,"wide iinc",f"#{idx} {c}"))
            else:
                idx=struct.unpack_from(">H",code,p)[0]; p+=2
                out.append((pc,"wide "+OPS.get(op2,("?",0,""))[0],f"#{idx}"))
            continue
        raw=code[p:p+ln]; p+=ln
        arg=""
        if kind=="i8": arg=str(struct.unpack(">b",raw)[0])
        elif kind=="i16": arg=str(struct.unpack(">h",raw)[0])
        elif kind=="cp1": arg=f"#{raw[0]} // {cpstr(cp,raw[0])}"
        elif kind=="cp2": arg=f"#{struct.unpack('>H',raw)[0]} // {cpstr(cp,struct.unpack('>H',raw)[0])}"
        elif kind=="cp4": arg=f"#{struct.unpack('>H',raw[:2])[0]} // {cpstr(cp,struct.unpack('>H',raw[:2])[0])}"
        elif kind=="lv": arg=f"slot {raw[0]}"
        elif kind in ("br",): arg=f"-> {struct.unpack('>h',raw)[0]+base}"
        elif kind=="br4": arg=f"-> {struct.unpack('>i',raw)[0]+base}"
        elif kind=="iinc": arg=f"slot {raw[0]} by {struct.unpack('>b',raw[1:2])[0]}"
        elif kind=="multi": arg=f"#{struct.unpack('>H',raw[:2])[0]} dims={raw[2]}"
        out.append((pc,name,arg))
    return out

def main():
    path=sys.argv[1]; want=sys.argv[2] if len(sys.argv)>2 else None
    b=open(path,"rb").read(); r=Reader(b)
    assert r.u4()==0xCAFEBABE
    r.u2(); r.u2()
    cp=parse_cp(r)
    r.u2()  # access
    this=r.u2(); r.u2()
    print(f"### CLASS {cpstr(cp,this)} (file {path})")
    for _ in range(r.u2()): r.u2()
    # fields
    for _ in range(r.u2()):
        r.u2(); r.u2(); r.u2()
        for _ in range(r.u2()):
            r.u2(); l=r.u4(); r.take(l)
    for _ in range(r.u2()):
        acc=r.u2(); nm=r.u2(); ds=r.u2()
        attrs=[]
        for _ in range(r.u2()):
            an=r.u2(); al=r.u4(); attrs.append((cpstr(cp,an), r.take(al)))
        name=cpstr(cp,nm); desc=cpstr(cp,ds)
        if want and want not in name: continue
        print(f"\n=== METHOD {name}{desc} (access 0x{acc:x}) ===")
        for an,ab in attrs:
            if an!="Code": continue
            cr=Reader(ab)
            cr.u2(); cr.u2()
            clen=cr.u4(); code=cr.take(clen)
            for pc,mn,arg in disasm(code,cp):
                print(f"  {pc:5d}: {mn:16s} {arg}")

main()
