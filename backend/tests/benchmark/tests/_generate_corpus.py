"""用 DeepSeek 生成 6 份模拟企业文档（语料合成）。"""
import asyncio
import json
from pathlib import Path

FIXTURES = Path("/app/tests/fixtures")
FIXTURES.mkdir(parents=True, exist_ok=True)

# 6 份文档的定义
DOCUMENTS = [
    {
        "filename": "acme_产品规格书.md",
        "prompt": """生成一份名为 "AcmeCloud 企业版 v3.2 产品规格书" 的中文技术文档，包含以下内容：
1. 产品概述（200字）
2. 核心功能列表（15项功能，每项含简要说明）
3. 系统要求（服务器、客户端、网络）
4. 部署架构（单机/集群）
5. API 接口说明（5个关键接口，含端点、参数、返回值）
6. 定价方案（基础版/专业版/企业版，含价格和功能差异）
7. 常见问题（5个FAQ）

要求：Markdown 格式，包含数字、版本号、URL、表格。约 3000-4000 字。""",
    },
    {
        "filename": "acme_框架合同.md",
        "prompt": """生成一份名为 "AcmeCloud 企业服务框架合同" 的中文法律文档，包含以下内容：
1. 合同双方信息（甲方：星辰科技有限公司，乙方：北京云端技术有限公司）
2. 服务范围与内容（5项具体服务）
3. 服务期限与续约条款
4. 服务费用与结算方式（含金额、账期、违约金比例）
5. 知识产权条款
6. 保密条款（含保密期限3年）
7. 违约责任（含具体赔偿金额）
8. 争议解决（约定北京仲裁委员会）
9. 合同变更与终止条件
10. 附录A：SLA 服务等级协议（含可用性99.9%、响应时间等具体数字）

要求：正式合同用语，至少出现 15 个不同的数字/金额/日期。约 4000-5000 字。""",
    },
    {
        "filename": "acme_季度报告.md",
        "prompt": """生成一份名为 "星辰科技 2026年Q1 业务季度报告" 的中文报告文档，格式为 Markdown。
包含以下内容：
1. 执行摘要（150字）
2. 核心业务数据表格（收入、用户数、毛利率等，同比环比数据）
3. 产品线表现分析（3条产品线，含具体数字）
4. 项目里程碑（5个重点项目，含完成百分比和日期）
5. 团队规模与人员变动
6. 财务摘要（收入、成本、利润等具体数字）
7. 下季度展望（3个目标，含具体指标）
8. 附录：技术指标对比表

要求：包含至少 3 个表格、至少 20 个具体数字、日期范围覆盖 2026年1月-3月。约 3000-4000 字。""",
    },
    {
        "filename": "acme_员工手册_英文.md",
        "prompt": """Generate a bilingual (Chinese-English) employee handbook titled "AcmeCloud Employee Handbook / 星辰科技员工手册".
Include the following sections:
1. Welcome Message (双语)
2. Company Overview (双语)
3. Code of Conduct (English only, 5 key policies)
4. Working Hours and Attendance Policy (双语, with specific times: 9:00-18:00)
5. Leave Policy (双语: annual leave 15 days, sick leave 10 days, personal leave)
6. Dress Code (English only)
7. IT Security Policy (English only, 8 specific rules)
8. 附录: Organization Chart (中文, 3 departments with team leads)

About 3000-4000 words total. Mix of Chinese and English paragraphs.""",
    },
    {
        "filename": "acme_操作手册.md",
        "prompt": """生成一份名为 "AcmeCloud 运维操作手册 v2.1" 的中文技术操作文档。
包含以下内容：
1. 系统登录与访问（含 URL、端口号、默认账号）
2. 日常巡检清单（15项检查项，含正常值范围）
3. 备份操作步骤（含 cron 表达式、备份策略：全量/增量）
4. 常见故障处理（8个故障场景，含错误码、原因、解决步骤）
5. 监控告警配置（5个关键告警规则，含阈值、级别）
6. 日志管理（日志路径、轮转策略、保留天数）
7. 安全配置（防火墙端口列表、访问控制列表）

要求：步骤清晰、包含大量数字（IP地址、端口号、阈值、时间间隔）。约 4000-5000 字。""",
    },
    {
        "filename": "acme_FAQ合集.md",
        "prompt": """生成一份名为 "AcmeCloud 客户常见问题 FAQ" 的中文问答合集。
包含 60 个常见问题，分为以下类别，每类 10 题：
1. 账号与登录类
2. 计费与付款类
3. 产品功能类
4. 技术支持类
5. 数据安全类
6. 集成与API类

每个问题包含：问题 + 答案。答案要详细但不超过 150 字。
涉及具体数字（价格、时间、次数、容量等）。
覆盖：简单事实型、条件型、流程型、对比型问题。
约 5000-6000 字。""",
    },
]

async def generate_document(doc: dict):
    """调用 DeepSeek 生成文档内容并保存。"""
    from app.services.rag.generation import stream_deepseek_tokens

    path = FIXTURES / doc["filename"]
    if path.exists():
        print(f"  [跳过] {doc['filename']} 已存在")
        return

    print(f"  [生成] {doc['filename']} ...")
    try:
        parts = []
        async for token in stream_deepseek_tokens(
            [{"role": "user", "content": doc["prompt"]}]
        ):
            parts.append(token)
        content = "".join(parts)
        path.write_text(content, encoding="utf-8")
        size = len(content)
        print(f"  [完成] {doc['filename']} ({size} 字)")
    except Exception as e:
        print(f"  [失败] {doc['filename']}: {e}")


async def main():
    print(f"开始生成 {len(DOCUMENTS)} 份文档...\n")
    for doc in DOCUMENTS:
        await generate_document(doc)
    print(f"\n生成完成！文件保存在 {FIXTURES}")
    print("文件列表：")
    for p in sorted(FIXTURES.glob("acme_*")):
        print(f"  {p.name}  ({len(p.read_text(encoding='utf-8'))} 字)")


if __name__ == "__main__":
    asyncio.run(main())
