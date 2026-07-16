"""Add Referrer-Policy: no-referrer to all preview responses"""
path = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\documents\preview.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: The PDF FileResponse with Content-Disposition
old1 = '''        return FileResponse(
            path=file_path,
            media_type=media_type_for_file_type(doc.file_type),
            headers={
                "Content-Disposition": f'inline; filename="{doc.filename}"'
            },
        )'''

new1 = '''        return FileResponse(
            path=file_path,
            media_type=media_type_for_file_type(doc.file_type),
            headers={
                "Content-Disposition": f'inline; filename="{doc.filename}"',
                "Referrer-Policy": "no-referrer",
            },
        )'''

content = content.replace(old1, new1)

# Fix 2: The last FileResponse without headers
old2 = '''    return FileResponse(
        path=file_path,
        media_type=media_type_for_file_type(doc.file_type),
        filename=doc.filename,
    )'''

new2 = '''    return FileResponse(
        path=file_path,
        media_type=media_type_for_file_type(doc.file_type),
        filename=doc.filename,
        headers={"Referrer-Policy": "no-referrer"},
    )'''

content = content.replace(old2, new2)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("OK")
