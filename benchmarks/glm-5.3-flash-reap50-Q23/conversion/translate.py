"""Translate the lighttransport-Strata GLM-5.3-Flash REAP-50 GGUF to upstream llama.cpp (b12165) names.
Metadata: rename hc/kda/swiglu keys, add indexer kpool keys from zai-org/GLM-5.3-Flash config.json.
Tensors: blk.N.hc_{attn,ffn}_{fn,base,scale} -> +.weight; blk.N.indexer.kpool_{gate,ape} -> indexer_compressor_*.weight.
Tensor data is copied byte for byte."""
import sys, re
sys.path.insert(0, '/home/nipuna/llama.cpp/gguf-py')
import gguf
from gguf import GGUFReader, GGUFWriter, GGUFValueType as T
src, dst = sys.argv[1], sys.argv[2]
r = GGUFReader(src)
A = 'glm5-next'
f = {k: v for k, v in r.fields.items()}
def val(k): return f[k].contents()
nblk = int(val(f'{A}.block_count'))
rename_kv = {f'{A}.attention.hc.mult': f'{A}.hyper_connection.count',
             f'{A}.attention.hc.sinkhorn_iters': f'{A}.hyper_connection.sinkhorn_iterations',
             f'{A}.attention.hc.eps': f'{A}.hyper_connection.epsilon',
             f'{A}.ssm.gate_lower_bound': f'{A}.kda.gate_lower_bound'}
# v2: take every model/tokenizer key that upstream's converter (unsloth GLM-5.3-Flash shard 1)
# writes and this file lacks or differs on -- value_length 0 vs 512 broke attention in v1 --
# except expert_count (REAP-50 keeps 144 of 288).
ref = GGUFReader(sys.argv[3])
SKIP = ('general.', 'split.', 'quantize.', 'GGUF.')
override = {}
for k, fld in ref.fields.items():
    if k.startswith(SKIP) or k == f'{A}.expert_count': continue
    if k.startswith('tokenizer.ggml.') and fld.types[0] == T.ARRAY: continue
    override[k] = fld
w = GGUFWriter(dst, arch=A)
written = set()
for k, fld in f.items():
    if k == gguf.Keys.General.ARCHITECTURE or k.startswith('GGUF.'): continue
    k2 = rename_kv.get(k, k)
    src_fld = override.get(k2, fld)
    vt = src_fld.types[0]; st = src_fld.types[-1] if vt == T.ARRAY else None
    if src_fld is not fld and src_fld.contents() != fld.contents(): print('changed', k2, fld.contents(), '->', src_fld.contents())
    w.add_key_value(k2, src_fld.contents(), vt, sub_type=st); written.add(k2)
for k, fld in override.items():
    if k in written or k in (f'{A}.attention.indexer.kpool', f'{A}.swiglu_clamp_exp', f'{A}.swiglu_clamp_shexp'): continue
    vt = fld.types[0]; st = fld.types[-1] if vt == T.ARRAY else None
    print('added', k, fld.contents() if vt != T.ARRAY else f'array[{len(fld.data)}]')
    w.add_key_value(k, fld.contents(), vt, sub_type=st); written.add(k)
if f'{A}.attention.indexer.kpool' not in written: w.add_uint32(f'{A}.attention.indexer.kpool', 4)
if f'{A}.attention.indexer.kpool_select_tail' not in written: w.add_bool(f'{A}.attention.indexer.kpool_select_tail', True)
lim = float(val(f'{A}.swiglu_limit'))
if f'{A}.swiglu_clamp_exp' not in written: w.add_array(f'{A}.swiglu_clamp_exp', [lim] * nblk)
if f'{A}.swiglu_clamp_shexp' not in written: w.add_array(f'{A}.swiglu_clamp_shexp', [lim] * nblk)
def newname(n):
    n2 = re.sub(r'^(blk\.\d+\.)indexer\.kpool_(gate|ape)$', r'\1indexer_compressor_\2.weight', n)
    n2 = re.sub(r'^(blk\.\d+\.hc_(?:attn|ffn)_(?:fn|base|scale))$', r'\1.weight', n2)
    return n2
cnt = 0
for t in r.tensors:
    nn = newname(t.name); cnt += nn != t.name
    w.add_tensor_info(nn, t.data.shape, t.data.dtype, t.data.nbytes, t.tensor_type)
print('renamed tensors:', cnt, 'of', len(r.tensors), flush=True)
w.write_header_to_file(); w.write_kv_data_to_file(); w.write_ti_data_to_file()
done = 0; tot = sum(t.n_bytes for t in r.tensors)
# v3: the fork stores ssm_a as +exp(A_log); upstream's converter stores -exp(A_log)
# (conversion/glm.py), checked against unsloth's GGUF: same magnitudes, opposite sign.
import numpy as np
neg = 0
for i, t in enumerate(r.tensors):
    data = t.data
    if re.match(r'^blk\.\d+\.ssm_a$', t.name):
        assert t.tensor_type.name == 'F32' and float(np.max(data)) > 0, t.name
        data = (-np.asarray(data, dtype=np.float32)).reshape(t.data.shape); neg += 1
    w.write_tensor_data(data, tensor_endianess=r.endianess); done += t.n_bytes
    if i % 100 == 0: print(f'{done/1e9:.1f}/{tot/1e9:.1f} GB', flush=True)
w.close(); print('negated ssm_a tensors:', neg); print('TRANSLATE-DONE', flush=True)
