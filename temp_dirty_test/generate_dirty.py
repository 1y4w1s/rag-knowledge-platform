"""生成测试脏数据文件"""
import os
import random
import string

DIR = r"D:\MyPrograms\rag-knowledge-platform\temp_dirty_test"
os.makedirs(DIR, exist_ok=True)

# === KB1: 重复与空文档 ===

normal = "这是一份正常的测试文档。\n人工智能（AI）是计算机科学的一个重要分支。\n深度学习是机器学习的一个子集。\n"
with open(os.path.join(DIR, "normal_doc.txt"), "w", encoding="utf-8") as f:
    f.write(normal)

# 完全相同的副本
import shutil
shutil.copy(
    os.path.join(DIR, "normal_doc.txt"),
    os.path.join(DIR, "normal_doc_副本.txt")
)

# 只改了一个字的伪重复
near_dup = normal.replace("一个", "xx个")
with open(os.path.join(DIR, "normal_doc_微改.txt"), "w", encoding="utf-8") as f:
    f.write(near_dup)

# 空文件
open(os.path.join(DIR, "empty_file.txt"), "w").close()

# 只有空白
with open(os.path.join(DIR, "only_whitespace.txt"), "w", encoding="utf-8") as f:
    f.write("   \n\n  \t\t  \n\n    ")

# 一行hello
with open(os.path.join(DIR, "one_liner.txt"), "w", encoding="utf-8") as f:
    f.write("hello world")

print("KB1 OK")

# === KB2: 编码与乱码 ===

# GB2312 (用gbk编码)
with open(os.path.join(DIR, "gb2312_text.txt"), "w", encoding="gbk") as f:
    f.write("你好世界，这是一段GB2312编码的中文测试。")

# UTF-8 with BOM
content = "这是一段带BOM的UTF-8文本。\n用于测试解析器能否正确处理。"
with open(os.path.join(DIR, "utf8_bom.txt"), "w", encoding="utf-8-sig") as f:
    f.write(content)

# 混合正常和乱码（直接写字节）
mixed = b"Normal text mixed with \xc3\xa9\xc3\xa7 latin-1 garbage bytes \xff\xfe\xc0\xc1\xc2 and more \x80\x81\x82\x83"
with open(os.path.join(DIR, "mixed_encoding.txt"), "wb") as f:
    f.write(mixed)

# emoji和奇怪unicode
weird = "emoji测试：🦄🌈🚀✨\n零宽空格：\u200b\u200b\u200b（你看不见我）\nRTL：\u0633\u0644\u0627\u0645\n数学：∑∏∫√∞≠≈\n下标：H₂O 上标：E=mc²"
with open(os.path.join(DIR, "unicode_weird.txt"), "w", encoding="utf-8") as f:
    f.write(weird)

# 二进制垃圾
garbage = bytes(random.randint(0, 255) for _ in range(500))
with open(os.path.join(DIR, "binary_garbage.txt"), "wb") as f:
    f.write(garbage)

print("KB2 OK")

# === KB3: 长文本与格式滥用 ===

# 超长行
long_line = "这是没有换行的长文本。" + "人工智能机器学习。" * 600
with open(os.path.join(DIR, "very_long_line.txt"), "w", encoding="utf-8") as f:
    f.write(long_line)

# 超长文件名
long_name = "a" * 30 + "_" + "b" * 30 + "_" + "中文_" + "x" * 50 + ".txt"
with open(os.path.join(DIR, long_name), "w", encoding="utf-8") as f:
    f.write("超长文件名文档，内容正常。")

# 特殊字符文件名
special_name = "file_with_特殊_符号_!@#$%^&().txt"
with open(os.path.join(DIR, special_name), "w", encoding="utf-8") as f:
    f.write("特殊文件名测试内容。")

# 纯数字符号
nums = "12345 67890 00000 11111 22222\n!@#$%^&*()_+-=[]{}|;':\",./<>?\n§±~¡™£¢∞§¶•ªº–≠\n" * 5
with open(os.path.join(DIR, "numbers_and_symbols.txt"), "w", encoding="utf-8") as f:
    f.write(nums)

# 大文件 (~5MB, 不要10MB以免撑爆)
large = "这是一个约5MB的大文件，测试系统对大文件的处理能力。\n" * 100000
with open(os.path.join(DIR, "5mb_large_file.txt"), "w", encoding="utf-8") as f:
    f.write(large)

# HTML混入
html_text = "<html><body><h1>标题</h1><p>HTML标签混入文本。</p><script>alert('xss')</script></body></html>\n正常段落。"
with open(os.path.join(DIR, "html_in_text.txt"), "w", encoding="utf-8") as f:
    f.write(html_text)

# Markdown
md = "# 一级标题\n## 二级标题\n**粗体** *斜体*\n- 列表项1\n- 列表项2\n| 表格 | 测试 |\n|------|------|\n| A | B |\n"
with open(os.path.join(DIR, "markdown_doc.md"), "w", encoding="utf-8") as f:
    f.write(md)

print("KB3 OK")

# List files
for fn in sorted(os.listdir(DIR)):
    fp = os.path.join(DIR, fn)
    size = os.path.getsize(fp)
    print(f"  {size:>8,}B  {fn}")
