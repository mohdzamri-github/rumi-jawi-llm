"""Shared evaluation harness: deterministic train/test split + exact-match accuracy."""
import re, importlib, sys

def load_rows(path='rumi-jawi-unicode.csv'):
    rows=[]
    with open(path, encoding='utf-8') as f:
        for line in f:
            line=line.rstrip('\n')
            if not line: continue
            p=line.split(',')
            if len(p)!=2: continue
            rows.append((p[0],p[1]))
    return rows

LAT_OK=re.compile(r'^[a-z]+$')
def jawi_clean(s):
    return len(s)>0 and all(0x0600<=ord(c)<=0x06FF or 0x0750<=ord(c)<=0x077F for c in s)

def clean_rows(rows):
    return [(r,j) for r,j in rows if LAT_OK.match(r) and jawi_clean(j)]

def split(rows, frac=0.2, seed=12345):
    # deterministic pseudo-random split by hash of rumi word
    test=[]; train=[]
    for r,j in rows:
        h=0
        for c in r: h=(h*131+ord(c))&0xffffffff
        (test if (h%100)<frac*100 else train).append((r,j))
    return train,test

def evaluate(convert, rows, show_fail=0):
    ok=0; fails=[]
    for r,j in rows:
        out=convert(r)
        if out==j: ok+=1
        elif len(fails)<show_fail or show_fail<0: fails.append((r,j,out))
    acc=ok/len(rows) if rows else 0
    return acc, fails

if __name__=='__main__':
    mod=importlib.import_module(sys.argv[1] if len(sys.argv)>1 else 'translit')
    convert=mod.convert
    rows=clean_rows(load_rows())
    train,test=split(rows)
    acctr,_=evaluate(convert,train)
    acc,fails=evaluate(convert,test,show_fail=30)
    print("clean rows: %d  train: %d  test: %d"%(len(rows),len(train),len(test)))
    print("TRAIN acc: %.2f%%"%(acctr*100))
    print("TEST  acc: %.2f%%"%(acc*100))
    print("\nsample failures (rumi -> gold | pred):")
    for r,g,p in fails:
        print("  %-16s %-14s | %s"%(r,g,p))
