"""用 DeepSeek 为每份文档生成 L1-L4 分层 QA 对。"""
import asyncio
import json
import random
from pathlib import Path

FIXTURES = Path("/app/tests/fixtures")
QA_PATH = FIXTURES / "enterprise_qa.json"

# 每份文档的出题配置
DOC_QA_CONFIG = [
    {
        "filename": "acme_产品规格书.md",
        "tags_base": ["product", "spec"],
        "l1_questions": [
            "AcmeCloud 企业版最新的版本号是多少？",
            "基础版的价格是多少？",
            "企业版支持的最大并发用户数是多少？",
        ],
        "l1_expect": [{"content_contains": v} for v in ["v3.2", "9,800", "10,000"]],
        "l2_questions": [
            "专业版和基础版的功能差异在哪里？",
            "部署集群模式需要什么条件？",
            "哪个 API 接口用于创建用户？",
        ],
        "l3_questions": [
            "如果客户有 500 个用户，推荐哪个版本？为什么？",
            "对比基础版和企业版的 API 调用频率限制。",
        ],
        "l4_questions": [
            "企业版年费比基础版贵多少倍？（需要计算）",
            "pro版最多能创建多少用户？价格是基础版的几倍？",
        ],
    },
    {
        "filename": "acme_框架合同.md",
        "tags_base": ["legal", "contract"],
        "l1_questions": [
            "合同的服务期限是多久？",
            "保密条款中的保密期限是多少年？",
            "SLA 承诺的系统可用性是多少？",
        ],
        "l1_expect": [{"content_contains": v} for v in ["一年", "3 年", "99.9%"]],
        "l2_questions": [
            "如果甲方要续约，需要提前多久通知？",
            "合同约定的争议解决机构是什么？",
            "违约金按未支付金额的多少比例计算？",
        ],
        "l3_questions": [
            "如果乙方连续两个月 SLA 不达标，甲方有什么权利？",
            "合同终止后，乙方需要履行哪些义务？",
        ],
        "l4_questions": [
            "合同总金额是多少？如果甲方提前解约要赔多少？",
            "一份订单的账期是30天还是60天？逾期违约金比例是多少？",
        ],
    },
    {
        "filename": "acme_季度报告.md",
        "tags_base": ["report", "quarterly"],
        "l1_questions": [
            "2026年Q1的总收入是多少？",
            "哪个产品线的收入增长最快？",
            "Q1 的毛利率是多少？",
        ],
        "l1_expect": [{"content_contains": v} for v in ["1,280", "AcmeCloud", "68%"]],
        "l2_questions": [
            "Q1 的净利润率相比去年同期是上升还是下降？",
            "团队在 Q1 增加了多少名工程师？",
            "AcmeData 产品线的收入环比增长了多少？",
        ],
        "l3_questions": [
            "公司 Q1 的总收入同比增长了多少百分比？（需要计算同比增长率）",
            "对比三条产品线的毛利率，哪个最高哪个最低？",
        ],
        "l4_questions": [
            "运营费用占收入的比例是多少？与去年同期相比有什么变化？",
            "按Q1的人均收入计算，公司的人效比去年同期提升了吗？",
        ],
    },
    {
        "filename": "acme_员工手册_英文.md",
        "tags_base": ["hr", "bilingual"],
        "l1_questions": [
            "员工每年有多少天年假？",
            "公司的上班时间是什么？",
            "IT 安全政策要求密码至少多少位？",
        ],
        "l1_expect": [{"content_contains": v} for v in ["15", "9:00", "8"]],
        "l2_questions": [
            "What is the company's policy on personal email usage?",
            "How many sick leave days are employees entitled to per year?",
            "哪位技术团队的负责人？",
        ],
        "l3_questions": [
            "如果员工需要在上班时间处理私人事务，应该怎么做？",
            "Compare the annual leave policy for regular employees vs executives.",
        ],
        "l4_questions": [
            "请用英文描述 dress code 中关于商务休闲装的具体要求",
            "信息安全政策第 7 条说的是什么？",
        ],
    },
    {
        "filename": "acme_操作手册.md",
        "tags_base": ["ops", "manual"],
        "l1_questions": [
            "系统管理后台的默认端口是什么？",
            "数据库全量备份的 cron 表达式是什么？",
            "日志文件的保留天数是多少？",
        ],
        "l1_expect": [{"content_contains": v} for v in ["8443", "0 2", "90"]],
        "l2_questions": [
            "CPU 使用率超过多少时需要告警？",
            "备份策略中，全量备份和增量备份的频率分别是多少？",
            "SSH 默认端口号建议改成什么？",
        ],
        "l3_questions": [
            "如果收到磁盘使用率超过 85% 的告警，应按照什么步骤处理？",
            "MySQL 慢查询日志的阈值是多少？如何开启？",
        ],
        "l4_questions": [
            "防火墙规则中，为什么建议限制 SSH 的源 IP？（需要结合安全配置和最佳实践推理）",
            "如果既需要保留 90 天日志又需要节省存储，应该调整哪些参数？",
        ],
    },
    {
        "filename": "acme_FAQ合集.md",
        "tags_base": ["faq", "knowledge-base"],
        "l1_questions": [
            "如何重置密码？",
            "免费的存储空间是多少？",
            "API 调用频率限制是多少？",
        ],
        "l1_expect": [{"content_contains": v} for v in ["重置", "5GB", "1000"]],
        "l2_questions": [
            "企业版和专业版在用户管理上有什么区别？",
            "如果银行卡扣款失败了怎么办？",
            "数据导出支持哪些格式？",
        ],
        "l3_questions": [
            "从免费版升级到专业版后，原来的数据会丢失吗？",
            "如果同时使用多个 API Key，调用频率是共享还是独立计算？",
        ],
        "l4_questions": [
            "我的月消费大约是 5000 元，选择哪种付款方案最划算？（需要对比不同方案）",
            "我想取消订阅，但已经交了年费——能退款吗？退多少？",
        ],
    },
]


async def generate_qa_from_doc(doc_config: dict, doc_content: str) -> list[dict]:
    """为一份文档生成 QA 对。"""
    from app.services.rag.generation import stream_deepseek_tokens

    filename = doc_config["filename"]
    tags_base = doc_config["tags_base"]
    cases = []
    case_id_counter = [0]

    # L1: 简单事实型
    if doc_config.get("l1_questions"):
        for i, q in enumerate(doc_config["l1_questions"]):
            case_id_counter[0] += 1
            expect = doc_config["l1_expect"][i] if i < len(doc_config["l1_expect"]) else {}
            cases.append({
                "case_id": f"ENT-{case_id_counter[0]:03d}",
                "query": q,
                "source": "md",
                "difficulty": "L1",
                "tags": tags_base + ["simple"],
                "expect": expect,
                "source_docs": [filename],
            })

    # L2-L4: 让 DeepSeek 根据文档内容出题
    level_configs = [
        ("L2", doc_config.get("l2_questions", []), "medium"),
        ("L3", doc_config.get("l3_questions", []), "hard"),
        ("L4", doc_config.get("l4_questions", []), "challenge"),
    ]

    for level, questions, tag in level_configs:
        for q in questions:
            case_id_counter[0] += 1
            # 用 DeepSeek 提取预期答案
            prompt = f"""你是一个 QA 工程师。请根据以下文档内容，回答用户的问题。

文档（{filename}）的摘要片段：
{doc_content[:2000]}

用户问题：{q}

请提取文档中的相关片段，只输出最相关的 1-3 个关键词或短语作为答案。
如果文档中不包含该信息，输出"无相关信息"。

答案关键词："""
            try:
                parts = []
                async for token in stream_deepseek_tokens(
                    [{"role": "user", "content": prompt}]
                ):
                    parts.append(token)
                answer = "".join(parts).strip()
                if "无相关信息" in answer:
                    continue
                # 取第一行作为 content_contains
                answer_key = answer.split("\n")[0].strip().strip('"').strip("'").strip("- ")
                cases.append({
                    "case_id": f"ENT-{case_id_counter[0]:03d}",
                    "query": q,
                    "source": "md",
                    "difficulty": level,
                    "tags": tags_base + [tag],
                    "expect": {"content_contains": answer_key[:100]},
                    "source_docs": [filename],
                })
            except Exception as e:
                print(f"  [跳过] {filename} {level} {q[:30]}: {e}")

    return cases


async def main():
    all_cases = []

    for doc_config in DOC_QA_CONFIG:
        path = FIXTURES / doc_config["filename"]
        if not path.exists():
            print(f"  [跳过] {path.name} 不存在")
            continue

        content = path.read_text(encoding="utf-8")
        print(f"\n[出题] {path.name} ({len(content)} 字)...")
        cases = await generate_qa_from_doc(doc_config, content)
        print(f"  [完成] {len(cases)} 题")
        all_cases.extend(cases)

    # 打乱顺序
    random.seed(42)
    random.shuffle(all_cases)

    qa_data = {
        "version": "1.0",
        "description": "睿阁 Enterprise QA 验收集 v1.0 — 6 份模拟企业文档，L1-L4 分层",
        "hit_k": 3,
        "cases": all_cases,
    }

    QA_PATH.write_text(json.dumps(qa_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # 统计
    by_level = {}
    for c in all_cases:
        l = c.get("difficulty", "L1")
        by_level[l] = by_level.get(l, 0) + 1
    by_tag = {}
    for c in all_cases:
        for t in c.get("tags", []):
            by_tag[t] = by_tag.get(t, 0) + 1

    print(f"\n{'='*60}")
    print(f"Enterprise QA 验收集生成完毕！")
    print(f"{'='*60}")
    print(f"总数: {len(all_cases)} 题")
    print(f"按难度: {', '.join(f'{k}={v}' for k, v in sorted(by_level.items()))}")
    print(f"已保存: {QA_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
