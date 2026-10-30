"""Auditable batch-one inference for the pinned ChatTS implementation."""
import time
from dataclasses import dataclass
from pathlib import Path
import torch

@dataclass
class Prepared:
    embeddings: torch.Tensor
    attention_mask: torch.Tensor
    position_ids: torch.Tensor
    input_tokens: int

def synchronize(device):
    if torch.device(device).type == "cuda":
        torch.cuda.synchronize(device)

def expand_inputs(model, batch):
    if batch["input_ids"].shape[0] != 1:
        raise ValueError("This latency protocol is explicitly batch=1")
    ids=batch["input_ids"]
    mask=batch["attention_mask"]
    embeddings=model.get_input_embeddings()(ids)
    if "timeseries" in batch:
        features,counts=model.ts_encoder(batch["timeseries"].to(embeddings.dtype))
        embeddings,mask,positions,_,_=model._merge_input_ids_with_time_series_features(
            features,embeddings,ids,mask,None,counts)
    else:
        positions=mask.long().cumsum(-1)-1
    return Prepared(embeddings,mask,positions,int(ids.shape[1]))

@torch.inference_mode()
def prefill(model, prepared, use_cache=True):
    outputs=model.model(inputs_embeds=prepared.embeddings,
        attention_mask=prepared.attention_mask,position_ids=prepared.position_ids,
        use_cache=use_cache,return_dict=True)
    logits=model.lm_head(outputs.last_hidden_state[:,-1:,:])
    return logits,outputs.past_key_values

@torch.inference_mode()
def decode(model, prepared, max_new_tokens=32, eos_ids=(), use_cache=True):
    """Return greedy tokens and synchronized phase durations; no answer constraints."""
    if max_new_tokens < 1: raise ValueError("At least one output token is required")
    device=prepared.embeddings.device
    synchronize(device); start=time.perf_counter()
    logits,cache=prefill(model,prepared,use_cache=use_cache)
    synchronize(device); prefill_seconds=time.perf_counter()-start
    ids=[]; token=logits[:,-1,:].argmax(-1,keepdim=True)
    mask=prepared.attention_mask
    base=prepared.embeddings
    for i in range(max_new_tokens):
        value=int(token.item())
        ids.append(value)
        if value in eos_ids or i+1 == max_new_tokens: break
        mask=torch.cat((mask,torch.ones((1,1),dtype=mask.dtype,device=device)),dim=-1)
        if use_cache:
            pos=torch.tensor([[mask.shape[-1]-1]],device=device)
            outputs=model.model(input_ids=token,attention_mask=mask,position_ids=pos,
                past_key_values=cache,use_cache=True,return_dict=True)
            cache=outputs.past_key_values
        else:
            base=torch.cat((base,model.get_input_embeddings()(token)),dim=1)
            outputs=model.model(inputs_embeds=base,attention_mask=mask,
                position_ids=torch.arange(mask.shape[-1],device=device)[None,:],
                use_cache=False,return_dict=True)
        logits=model.lm_head(outputs.last_hidden_state[:,-1:,:])
        token=logits[:,-1,:].argmax(-1,keepdim=True)
    synchronize(device)
    return {"tokens":ids,"prefill_ms":prefill_seconds*1000,
            "decode_ms":(time.perf_counter()-start-prefill_seconds)*1000,
            "stopped_on_eos":bool(ids[-1] in eos_ids),"use_cache":use_cache}

def load_local(model_dir, device="cuda:0", dtype=torch.float16, fp32_head=False):
    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoProcessor
    path=Path(model_dir).resolve()
    if not (path/"relay-manifest.json").exists():
        raise ValueError("Expected a verified local model with relay manifest")
    model=AutoModelForCausalLM.from_pretrained(str(path),trust_remote_code=True,
        local_files_only=True,torch_dtype=dtype,attn_implementation="sdpa",
        device_map={"":device},weights_only=True).eval()
    if fp32_head:
        model.lm_head.float()
        model.lm_head.register_forward_pre_hook(lambda module, inputs: (inputs[0].float(),))
    tokenizer=AutoTokenizer.from_pretrained(str(path),trust_remote_code=True,local_files_only=True)
    processor=AutoProcessor.from_pretrained(str(path),trust_remote_code=True,
        local_files_only=True,tokenizer=tokenizer)
    return model,tokenizer,processor

def render_prompt(tokenizer, content):
    return tokenizer.apply_chat_template(
        [{"role":"system","content":"You are a helpful assistant."},
         {"role":"user","content":content}],
        tokenize=False,add_generation_prompt=True,enable_thinking=False)
