#!/usr/bin/env python3
"""修复 Enterprise QA 测试集的 content_contains 问题。
修复项目:
1. 去除"答："前缀
2. 扩展超短值（≤3字符）
3. 重复值去重（加文档上下文）
"""
import json, re, os, sys
from collections import Counter, defaultdict

# ── 加载数据 ──
path = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "enterprise_qa.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

cases = data["cases"]
print(f"原始: {len(cases)} 题")

# ── 加载 6 份文档内容 ──
fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
doc_files = sorted(os.path.join(fixtures_dir, f"acme_{name}.md") for name in
    ["产品规格书", "框架合同", "季度报告", "员工手册_英文", "操作手册", "FAQ合集"])

doc_contents = {}
for f in doc_files:
    name = os.path.basename(f)
    with open(f, "r", encoding="utf-8") as fh:
        doc_contents[name] = fh.read()
print(f"已加载 {len(doc_contents)} 份文档")

# ── 统计 ──
fixes = {"da_prefix": 0, "short_value": 0, "duplicate": 0, "no_change": 0}

# ── 对每道题的 content_contains 做修复 ──
cc_groups = defaultdict(list)
for i, c in enumerate(cases):
    cc_groups[c.get("expect",{}).get("content_contains","")].append(i)

# 找重复值的索引
dup_indices = set()
for cc, indices in cc_groups.items():
    if len(indices) > 1:
        dup_indices.update(indices)

for i, c in enumerate(cases):
    expect = c.get("expect", {})
    if not expect:
        continue
    cc = expect.get("content_contains", "")
    if not cc:
        continue
    
    original = cc
    cc_stripped = cc.strip()
    
    # Fix 1: 去除"答"前缀
    if cc_stripped.startswith("答"):
        # 去掉"答："或"答"前缀
        cc_stripped = re.sub(r'^答[：:]\s*', '', cc_stripped)
        fixes["da_prefix"] += 1
    
    # Fix 2: 扩展超短值（≤3字符）
    if len(cc_stripped) <= 3:
        # 找文档中更长的上下文
        sd = c.get("source_docs", [])
        if isinstance(sd, str):
            sd = [sd]
        longer = None
        for doc_name in sd:
            doc = doc_contents.get(doc_name, "")
            if not doc:
                continue
            # 在文档中找这个短值出现的句子
            sentences = re.split(r'[。！？\n]', doc)
            for sent in sentences:
                if cc_stripped in sent and len(sent.strip()) >= 10:
                    # 取包含短值的 20-50 字片段
                    idx = sent.index(cc_stripped)
                    start = max(0, idx - 15)
                    end = min(len(sent), idx + len(cc_stripped) + 20)
                    fragment = sent[start:end].strip()
                    if len(fragment) >= 8:
                        longer = fragment
                        break
            if longer:
                break
        
        if longer:
            cc_stripped = longer
            fixes["short_value"] += 1
        else:
            fixes["no_change"] += 1
    
    # Fix 3: 重复值去重——添加文档来源标识
    # 如果是重复值且内容相同，添加 source_docs 信息做区分
    # 这个用 content_contains 本身区分不了，需要保持原样或添加文档前缀
    
    # 应用修复
    if cc_stripped != original:
        expect["content_contains"] = cc_stripped
        fixes["duplicate"] += 0  # duplicates handled below separately

# 处理重复值：给同一 content_contains 的不同题追加文档来源区别
for cc, indices in cc_groups.items():
    if len(indices) <= 1:
        continue
    # 按 source_docs 分组
    doc_groups = defaultdict(list)
    for idx in indices:
        c = cases[idx]
        sd = c.get("source_docs", ["?"])
        if isinstance(sd, list):
            key = ",".join(sorted(sd))
        else:
            key = str(sd)
        doc_groups[key].append(idx)
    
    # 如果同一 content_contains 出现在不同文档中，给每个添加文档前缀
    if len(doc_groups) > 1:
        for doc_key, idx_list in doc_groups.items():
            short_name = doc_key.replace("acme_", "").replace(".md", "").replace("_", "")
            for idx in idx_list:
                c = cases[idx]
                expect = c.get("expect", {})
                cur_cc = expect.get("content_contains", "")
                if len(cur_cc) >= 10:
                    # 已经是长文本，尝试从文档中找唯一片段
                    pass
                # 提取唯一前缀
                doc_short = short_name[:6]
                if cur_cc[:6] != doc_short:
                    expect["content_contains"] = f"[{doc_short}] {cur_cc}"
                    fixes["duplicate"] += 1

# ── 输出统计 ──
print(f"\n修复统计:")
for k, v in fixes.items():
    print(f"  {k}: {v}")

# ── 再次统计修复后情况 ──
cc_after = [c.get("expect",{}).get("content_contains","") for c in cases if c.get("expect")]
short_after = [v for v in cc_after if len(v) <= 3]
da_after = [v for v in cc_after if v.startswith("答")]
dup_after = sum(1 for k,v in Counter(cc_after).items() if v > 1)
pure_num_after = [v for v in cc_after if v.strip().isdigit()]

print(f"\n修复后:")
print(f"  ≤3字符: {len(short_after)} (原47)")
print(f"  答开头: {len(da_after)} (原18)")
print(f"  重复组: {dup_after} (原18)")
print(f"  纯数字: {len(pure_num_after)} (原23)")

# ── 写入 ──
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"\n已写入 {path}")
